"""Accounts (M2, data-model.md): account, player links, progress copy (tasks T223).

- ``ACC#<sub>`` / ``META``: primary player id and its hash, display name, ``adult``, created,
  ``lastActiveMonth`` (feeds ``GSI_INACTIVE``), ``state`` (``active`` or ``deleting``).
- ``PLY#<playerHash>`` / ``ACCOUNT``: which account a player id belongs to.
- ``ACC#<sub>`` / ``PROGRESS``: the browser's progress, one versioned JSON copy (64 KB).
- ``ACC#<sub>`` / ``MERGE#<playerHash>``: a finished merge, so a repeated adopt changes nothing.

No e-mail anywhere: Cognito keeps it. ``sub`` is the Cognito user id.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from typing import Any

from botocore.exceptions import ClientError

from staysharp import aws
from staysharp.obs import player_hash
from staysharp.store import merge, table

PROGRESS_LIMIT = 64 * 1024
LEVELS = ("senior", "junior", "starter")
PER_LEVEL = ("days", "freeze", "deckStats", "practice")
MERGE_DAYS = 30


class Deleting(Exception):
    """The account is being deleted: only DELETE /me goes on."""


class OtherAccount(Exception):
    """This player id already belongs to another account."""


class TooLarge(Exception):
    """The progress copy is over 64 KB."""


class BadProgress(Exception):
    """The progress copy does not have the outline of contracts/progress.schema.json."""


@dataclass(frozen=True)
class Account:
    sub: str
    primary_player: str
    players: frozenset[str]
    display_name: str | None
    created_at: str
    state: str
    last_active_month: str | None


@dataclass(frozen=True)
class Adopted:
    primary_player: str
    created: bool
    plays: int
    replays: int


@dataclass(frozen=True)
class ProgressCopy:
    version: int
    body: dict[str, Any]


class VersionConflict(Exception):
    def __init__(self, stored: ProgressCopy) -> None:
        super().__init__("progress changed elsewhere")
        self.stored = stored


def account_key(sub: str) -> table.Key:
    return table.key(f"ACC#{sub}", "META")


def progress_key(sub: str) -> table.Key:
    return table.key(f"ACC#{sub}", "PROGRESS")


def merge_key(sub: str, hashed: str) -> table.Key:
    return table.key(f"ACC#{sub}", f"MERGE#{hashed}")


def link_key(hashed: str) -> table.Key:
    return table.key(f"PLY#{hashed}", "ACCOUNT")


def month(now: dt.datetime) -> str:
    return now.astimezone(dt.UTC).strftime("%Y-%m")


def _from_item(sub: str, item: dict[str, Any]) -> Account:
    try:
        return Account(
            sub=sub,
            primary_player=str(item["primaryPlayer"]),
            players=frozenset(item.get("players") or {item["primaryPlayer"]}),
            display_name=item.get("displayName"),
            created_at=str(item["createdAt"]),
            state=str(item.get("state", "active")),
            last_active_month=item.get("lastActiveMonth"),
        )
    except KeyError as error:
        raise table.StoreError("account item is malformed") from error


def get(sub: str) -> Account | None:
    item = table.get(account_key(sub), consistent=True)
    return None if item is None else _from_item(sub, item)


def linked_sub(player_id: str) -> str | None:
    item = table.get(link_key(player_hash(player_id)), consistent=True)
    return None if item is None else str(item["sub"])


def _cancelled(error: ClientError) -> bool:
    return error.response.get("Error", {}).get("Code") in (
        "TransactionCanceledException",
        "ConditionalCheckFailedException",
    )


def _create(sub: str, player_id: str, now: dt.datetime) -> bool:
    """One transaction: the account and the link of its primary id. ``False`` if it existed."""
    hashed = player_hash(player_id)
    account = {
        "primaryPlayer": player_id,
        "primaryHash": hashed,
        "adult": True,
        "createdAt": table.iso_ms(now),
        "lastActiveMonth": month(now),
        "state": "active",
        # Every player id of this account (primary and merged): deletion clears them all.
        "players": {player_id},
    }
    try:
        aws.dynamodb().transact_write_items(
            TransactItems=[
                {
                    "Put": {
                        "TableName": table.table_name(),
                        "Item": {**account_key(sub), **table.serialize(account)},
                        "ConditionExpression": "attribute_not_exists(PK)",
                    }
                },
                {
                    "Put": {
                        "TableName": table.table_name(),
                        "Item": {**link_key(hashed), **table.serialize({"sub": sub})},
                        "ConditionExpression": "attribute_not_exists(PK)",
                    }
                },
            ]
        )
    except ClientError as error:
        if not _cancelled(error):
            raise
        return False
    return True


def adopt(sub: str, player_id: str, now: dt.datetime) -> Adopted:
    """Create the account from this browser, or merge this browser's history into it.

    Repeating a call gives the same result and changes nothing.
    """
    owner = linked_sub(player_id)
    if owner is not None and owner != sub:
        raise OtherAccount
    account = get(sub)
    if account is None:
        if _create(sub, player_id, now):
            return Adopted(primary_player=player_id, created=True, plays=0, replays=0)
        account = get(sub)
        if account is None:
            raise table.StoreError("account vanished after a lost create race")
    if account.state == "deleting":
        raise Deleting
    if player_id == account.primary_player:
        return Adopted(primary_player=player_id, created=False, plays=0, replays=0)

    hashed = player_hash(player_id)
    done = table.get(merge_key(sub, hashed), consistent=True)
    if done is not None:
        return Adopted(
            primary_player=account.primary_player,
            created=False,
            plays=int(done["moved"]),
            replays=int(done["replays"]),
        )
    result = merge.merge(account.primary_player, player_id, now)
    record = {
        "doneAt": table.iso_ms(now),
        "moved": result.plays,
        "replays": result.replays,
        "expiresAt": table.epoch_seconds(now + dt.timedelta(days=MERGE_DAYS)),
    }
    # The merge record is written last, with the link: a crash before this point re-runs the
    # merge, which only finds what is left.
    try:
        aws.dynamodb().transact_write_items(
            TransactItems=[
                {
                    "Put": {
                        "TableName": table.table_name(),
                        "Item": {**link_key(hashed), **table.serialize({"sub": sub})},
                        "ConditionExpression": "attribute_not_exists(PK) OR #s = :sub",
                        "ExpressionAttributeNames": {"#s": "sub"},
                        "ExpressionAttributeValues": {":sub": {"S": sub}},
                    }
                },
                {
                    "Put": {
                        "TableName": table.table_name(),
                        "Item": {**merge_key(sub, hashed), **table.serialize(record)},
                    }
                },
                {
                    "Update": {
                        "TableName": table.table_name(),
                        "Key": account_key(sub),
                        "UpdateExpression": "ADD players :p",
                        "ConditionExpression": "#st = :active",
                        "ExpressionAttributeNames": {"#st": "state"},
                        "ExpressionAttributeValues": {
                            ":p": {"SS": [player_id]},
                            ":active": {"S": "active"},
                        },
                    }
                },
            ]
        )
    except ClientError as error:
        if _cancelled(error):
            raise OtherAccount from error
        raise
    return Adopted(
        primary_player=account.primary_player,
        created=False,
        plays=result.plays,
        replays=result.replays,
    )


def touch(sub: str, now: dt.datetime, *, known: str | None = None) -> None:
    """Record activity, at most one write a month (inactive accounts, FR-120).

    ``known`` is the month already read with the account: when it is this month, nothing is
    written at all. Any activity also clears an inactivity warning (``warnedAt``).
    """
    current = month(now)
    if known == current:
        return
    try:
        aws.dynamodb().update_item(
            TableName=table.table_name(),
            Key=account_key(sub),
            UpdateExpression="SET lastActiveMonth = :m REMOVE warnedAt",
            ConditionExpression="attribute_exists(PK) AND lastActiveMonth <> :m",
            ExpressionAttributeValues={":m": {"S": current}},
        )
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
            raise


# --- progress copy ------------------------------------------------------------------------


def fresh_body() -> dict[str, Any]:
    """The copy of a browser that has played nothing yet."""
    empty: dict[str, Any] = {level: {} for level in LEVELS}
    return {
        "version": 1,
        "level": None,
        "relaxed": False,
        **{name: dict(empty) for name in PER_LEVEL},
        "longest": {level: 0 for level in LEVELS},
    }


def check_outline(body: Any) -> dict[str, Any]:
    """The outline of contracts/progress.schema.json (the browser checks the details)."""
    expected = {"version", "level", "relaxed", "days", "freeze", "longest", "deckStats", "practice"}
    if not isinstance(body, dict) or set(body) != expected:
        raise BadProgress
    if body["version"] != 1 or body["level"] not in (*LEVELS, None):
        raise BadProgress
    if not isinstance(body["relaxed"], bool):
        raise BadProgress
    for name in PER_LEVEL:
        part = body[name]
        if not isinstance(part, dict) or set(part) != set(LEVELS):
            raise BadProgress
        if not all(isinstance(part[level], dict) for level in LEVELS):
            raise BadProgress
    longest = body["longest"]
    if not isinstance(longest, dict) or set(longest) != set(LEVELS):
        raise BadProgress
    for value in longest.values():
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise BadProgress
    return body


def encode(body: dict[str, Any]) -> str:
    text = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
    if len(text.encode()) > PROGRESS_LIMIT:
        raise TooLarge
    return text


def get_progress(sub: str) -> ProgressCopy:
    item = table.get(progress_key(sub), consistent=True)
    if item is None:
        return ProgressCopy(version=0, body=fresh_body())
    try:
        return ProgressCopy(version=int(item["version"]), body=json.loads(item["body"]))
    except (KeyError, TypeError, ValueError) as error:
        raise table.StoreError("progress item is malformed") from error


def put_progress(sub: str, version: int, body: dict[str, Any], now: dt.datetime) -> ProgressCopy:
    """Store the copy if nobody changed it since ``version``; else ``VersionConflict``."""
    text = encode(check_outline(body))
    stored = {"version": version + 1, "body": text, "updatedAt": table.iso_ms(now)}
    item = {**progress_key(sub), **table.serialize(stored)}
    try:
        if version == 0:
            aws.dynamodb().put_item(
                TableName=table.table_name(),
                Item=item,
                ConditionExpression="attribute_not_exists(PK)",
            )
        else:
            aws.dynamodb().put_item(
                TableName=table.table_name(),
                Item=item,
                ConditionExpression="version = :v",
                ExpressionAttributeValues={":v": {"N": str(version)}},
            )
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
            raise
        raise VersionConflict(get_progress(sub)) from error
    return ProgressCopy(version=version + 1, body=body)


def set_display_name(sub: str, name: str | None) -> None:
    update = "SET displayName = :n" if name is not None else "REMOVE displayName"
    kwargs = {"ExpressionAttributeValues": {":n": {"S": name}}} if name is not None else {}
    aws.dynamodb().update_item(
        TableName=table.table_name(),
        Key=account_key(sub),
        UpdateExpression=update,
        ConditionExpression="attribute_exists(PK)",
        **kwargs,  # type: ignore[arg-type]
    )
