"""Limits on code e-mails (FR-117; runbook docs/runbooks/accounts.md section 4).

Sign-up and sign-in calls go to Cognito directly, outside the web ACL, so the sender function
counts what it sends: at most ``PER_HOUR`` an hour and ``PER_DAY`` a day to one address, and
``ALL_PER_HOUR`` an hour in all. Over a limit, nothing is sent; the player can ask again later.

Counters live in the main table under a keyed hash of the address (HMAC with the pepper, the
address lower-cased), never the address, and expire with the table's TTL after two days:

- ``MAIL#<hash>`` / ``H#<hour>`` and ``D#<day>``
- ``MAIL#ALL`` / ``H#<hour>``

The three counters move together in one transaction, so a refused send counts nowhere.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac

from botocore.exceptions import ClientError

from staysharp import aws
from staysharp.obs import pepper
from staysharp.store import table

PER_HOUR = 5
PER_DAY = 10
ALL_PER_HOUR = 300
KEEP = dt.timedelta(days=2)


def address_hash(address: str) -> str:
    return hmac.new(
        pepper(), f"mail:{address.strip().lower()}".encode(), hashlib.sha256
    ).hexdigest()


def _count(key: table.Key, limit: int, expires: int) -> dict[str, object]:
    return {
        "Update": {
            "TableName": table.table_name(),
            "Key": key,
            "UpdateExpression": "ADD sent :one SET expiresAt = :exp",
            "ConditionExpression": "attribute_not_exists(sent) OR sent < :limit",
            "ExpressionAttributeValues": {
                ":one": {"N": "1"},
                ":limit": {"N": str(limit)},
                ":exp": {"N": str(expires)},
            },
        }
    }


def allow(address: str, now: dt.datetime) -> bool:
    """Count one e-mail to ``address``; ``False`` (and nothing counted) when over a limit."""
    when = now.astimezone(dt.UTC)
    hour = when.strftime("H#%Y-%m-%dT%H")
    day = when.strftime("D#%Y-%m-%d")
    mine = f"MAIL#{address_hash(address)}"
    expires = table.epoch_seconds(now + KEEP)
    try:
        aws.dynamodb().transact_write_items(
            TransactItems=[
                _count(table.key(mine, hour), PER_HOUR, expires),  # type: ignore[list-item]
                _count(table.key(mine, day), PER_DAY, expires),  # type: ignore[list-item]
                _count(table.key("MAIL#ALL", hour), ALL_PER_HOUR, expires),  # type: ignore[list-item]
            ]
        )
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") == "TransactionCanceledException":
            return False
        raise
    return True
