"""Inactive accounts and unfinished sign-ups (task T243, FR-120, research A8).

An account last used in month ``M`` (``lastActiveMonth``, written at most once a month) counts as
inactive from the first day of ``M + 1``, which gives the player the benefit of the doubt. Then:

- 23 months later: one plain-text warning e-mail, and ``warnedAt`` is set. Any activity
  (``accounts.touch``) clears it.
- 24 months later, and never sooner than 30 days after the warning: the account is deleted with
  the same steps as "Delete my account" (``deletion.delete_account``).

A sign-up that was never confirmed has no account here but its e-mail address sits in the sign-in
service: it is removed there after 7 days.

Accounts are found through the sparse index ``GSI_INACTIVE``, one partition per month, from the
first possible month to the newest month due. Logs carry counts and hashed account ids only.
"""

from __future__ import annotations

import datetime as dt
import os
import time
from collections.abc import Callable, Iterable

from botocore.exceptions import ClientError

from staysharp import aws
from staysharp.obs import account_hash, logger
from staysharp.store import accounts, deletion, table

WARN_AFTER_MONTHS = 23
DELETE_AFTER_MONTHS = 24
NOTICE = dt.timedelta(days=30)
UNCONFIRMED_AFTER = dt.timedelta(days=7)
RUN_BUDGET = dt.timedelta(minutes=3)
# No account is older than this month (accounts started in M2, November 2026).
FIRST_MONTH = "2026-01"

Send = Callable[[str, str, str], None]
EmailOf = Callable[[str], "str | None"]
DeleteUser = Callable[[str], None]

SUBJECT = "Your Stay Sharp account will be deleted in 30 days"


def warning_text(delete_on: dt.date, site: str) -> str:
    day = f"{delete_on.day} {delete_on:%B %Y}"
    return (
        "You have not used your Stay Sharp account for almost two years.\n\n"
        f"We keep data only while it is used, so on {day} we will delete the account and "
        "everything kept with it: your e-mail address, your games and your progress.\n\n"
        f"To keep it, sign in once before then: {site}/account\n\n"
        "If you do nothing, the account is deleted. You can still play without an account.\n"
    )


def add_months(when: dt.datetime, months: int) -> dt.datetime:
    """``when`` plus whole months, on the last day of a shorter month when needed."""
    index = when.year * 12 + when.month - 1 + months
    year, month0 = divmod(index, 12)
    month = month0 + 1
    next_first = dt.date(year + (month == 12), month % 12 + 1, 1)
    last_day = (next_first - dt.timedelta(days=1)).day
    return when.replace(year=year, month=month, day=min(when.day, last_day))


def inactive_since(month: str) -> dt.datetime:
    """The first day after month ``YYYY-MM``, at midnight UTC."""
    first = dt.datetime.strptime(f"{month}-01", "%Y-%m-%d").replace(tzinfo=dt.UTC)
    return add_months(first, 1)


def _months(first: str, last: str) -> list[str]:
    result: list[str] = []
    current = inactive_since(first) - dt.timedelta(days=1)
    end = dt.datetime.strptime(f"{last}-01", "%Y-%m-%d").replace(tzinfo=dt.UTC)
    while current.replace(day=1) <= end:
        result.append(current.strftime("%Y-%m"))
        current = add_months(current.replace(day=1), 1)
    return result


def _due_months(now: dt.datetime) -> list[str]:
    """Months whose accounts are at least 23 months inactive at ``now``."""
    return [
        m
        for m in _months(FIRST_MONTH, accounts.month(now))
        if add_months(inactive_since(m), WARN_AFTER_MONTHS) <= now
    ]


def _subs_of(month: str) -> list[str]:
    # No cap: a month may hold many accounts. Keys only (the index projects nothing else).
    found = table.query_all(
        {
            "IndexName": "GSI_INACTIVE",
            "KeyConditionExpression": "lastActiveMonth = :m",
            "ExpressionAttributeValues": {":m": {"S": month}},
        },
        limit=10_000_000,
    )
    return sorted(str(key["PK"]).removeprefix("ACC#") for key in found)


def _mark_warned(sub: str, month: str, now: dt.datetime) -> bool:
    """Set ``warnedAt`` unless the account moved on (activity, deletion) in the meantime."""
    try:
        aws.dynamodb().update_item(
            TableName=table.table_name(),
            Key=accounts.account_key(sub),
            UpdateExpression="SET warnedAt = :now",
            ConditionExpression=(
                "attribute_exists(PK) AND lastActiveMonth = :m AND attribute_not_exists(warnedAt)"
            ),
            ExpressionAttributeValues={":now": {"S": now.isoformat()}, ":m": {"S": month}},
        )
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            return False
        raise
    return True


def site_url() -> str:
    return os.environ.get("SITE_URL", "https://stay-sharp.lumineth.com").rstrip("/")


def run(
    now: dt.datetime,
    *,
    send: Send,
    email_of: EmailOf,
    delete_user: DeleteUser,
    budget: dt.timedelta = RUN_BUDGET,
) -> dict[str, int]:
    """Warn and delete what is due. Counts only; failures are counted, the rest goes on.

    Stops after ``budget`` (the function has 5 minutes); the next hourly run goes on from there.
    """
    deadline = time.monotonic() + budget.total_seconds()
    warned = deleted = failed = 0
    for month in _due_months(now):
        since = inactive_since(month)
        try:
            subs = _subs_of(month)
        except Exception as error:  # noqa: BLE001 - the other months go on, then report
            failed += 1
            logger.warning("inactive month not read", extra={"error_type": type(error).__name__})
            continue
        for sub in subs:
            if time.monotonic() >= deadline:
                logger.info("inactive accounts: time is up, the next run goes on")
                return {"warned": warned, "deleted": deleted, "failed": failed, "unconfirmed": 0}
            item = table.get(accounts.account_key(sub), consistent=True)
            if item is None or item.get("lastActiveMonth") != month:
                continue  # active again, or being deleted: not ours
            try:
                warned_at = item.get("warnedAt")
                if warned_at is None:
                    delete_on = max(add_months(since, DELETE_AFTER_MONTHS), now + NOTICE)
                    address = email_of(sub)
                    if address is not None:
                        send(address, SUBJECT, warning_text(delete_on.date(), site_url()))
                    if _mark_warned(sub, month, now):
                        warned += 1
                    continue
                due = max(
                    add_months(since, DELETE_AFTER_MONTHS),
                    dt.datetime.fromisoformat(str(warned_at)) + NOTICE,
                )
                if now >= due:
                    deletion.delete_account(sub, now, delete_user)
                    deleted += 1
            except Exception as error:  # noqa: BLE001 - try the others, then report
                failed += 1
                logger.warning(
                    "inactive account step failed",
                    extra={"account_hash": account_hash(sub), "error_type": type(error).__name__},
                )
    return {"warned": warned, "deleted": deleted, "failed": failed, "unconfirmed": 0}


def remove_unconfirmed(
    now: dt.datetime,
    pending: Callable[[], Iterable[tuple[str, dt.datetime]]],
    delete_user: DeleteUser,
) -> int:
    """Remove sign-ups never confirmed within 7 days: their address is not kept."""
    removed = 0
    for sub, created in pending():
        if now - created >= UNCONFIRMED_AFTER:
            delete_user(sub)
            removed += 1
    return removed


# --- the sign-in service (Cognito) --------------------------------------------------------


def cognito_email_of(user_pool_id: str) -> EmailOf:
    def lookup(sub: str) -> str | None:
        try:
            user = aws.cognito().admin_get_user(UserPoolId=user_pool_id, Username=sub)
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") == "UserNotFoundException":
                return None
            raise
        for attribute in user.get("UserAttributes", []):
            if attribute.get("Name") == "email":
                return attribute.get("Value")
        return None

    return lookup


def cognito_unconfirmed(user_pool_id: str) -> Callable[[], list[tuple[str, dt.datetime]]]:
    def listing() -> list[tuple[str, dt.datetime]]:
        result: list[tuple[str, dt.datetime]] = []
        pages = aws.cognito().get_paginator("list_users")
        for page in pages.paginate(
            UserPoolId=user_pool_id,
            Filter='cognito:user_status = "UNCONFIRMED"',
            AttributesToGet=[],
        ):
            for user in page.get("Users", []):
                created = user.get("UserCreateDate")
                name = user.get("Username")
                if name and isinstance(created, dt.datetime):
                    result.append((name, created))
        return result

    return listing
