"""Delete an account and all its data (task T232, FR-114, FR-115, research A7).

Steps, each safe to run again:

1. Mark the account ``deleting`` (and move it to ``lastActiveMonth = DELETING`` in the sparse
   index, so the job finds it). From now on it refuses everything but deletion.
2. For every player id of the account (primary and merged): challenge results recorded under
   its hash are kept as a "deleted player" (re-keyed to a random id, so the colleague's view
   still adds up), challenges it created lose their owner, then every ``P#<id>`` item (plays,
   answers, practice) and the player link are deleted.
3. The progress copy, merge records and the account item's other rows go; a ``GONE`` row is
   written for two hours, so a token still held by another device cannot recreate it.
4. The Cognito user is deleted (``AdminDeleteUser``; already gone is fine).
5. The account item itself, last: while it exists, the job can finish the work.

``delete_account`` returns only when everything is gone; any failure raises, the caller
answers 503 and a retry (or the job) continues.
"""

from __future__ import annotations

import datetime as dt
import random
import secrets
import time
from collections.abc import Callable
from typing import Any

from botocore.exceptions import ClientError

from staysharp import aws
from staysharp.obs import player_hash
from staysharp.store import accounts, table

DELETING_MONTH = "DELETING"
DELETED_OWNER = "deleted"
BATCH = 25
GONE_FOR = dt.timedelta(hours=2)

DeleteUser = Callable[[str], None]


def _mark(sub: str, now: dt.datetime) -> accounts.Account | None:
    try:
        response = aws.dynamodb().update_item(
            TableName=table.table_name(),
            Key=accounts.account_key(sub),
            UpdateExpression=(
                "SET #st = :d, lastActiveMonth = :m,"
                " deletingSince = if_not_exists(deletingSince, :now)"
            ),
            ConditionExpression="attribute_exists(PK)",
            ExpressionAttributeNames={"#st": "state"},
            ExpressionAttributeValues={
                ":d": {"S": "deleting"},
                ":m": {"S": DELETING_MONTH},
                ":now": {"S": table.iso_ms(now)},
            },
            ReturnValues="ALL_NEW",
        )
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            return None
        raise
    return accounts._from_item(sub, table.deserialize(response["Attributes"]))  # noqa: SLF001


def _partition(pk: str) -> list[dict[str, Any]]:
    return table.query_all(
        {
            "KeyConditionExpression": "PK = :pk",
            "ExpressionAttributeValues": {":pk": {"S": pk}},
            "ConsistentRead": True,
        },
        limit=50_000,
    )


def _delete_keys(keys: list[table.Key]) -> None:
    for start in range(0, len(keys), BATCH):
        requests: list[Any] = [{"DeleteRequest": {"Key": k}} for k in keys[start : start + BATCH]]
        pending: dict[str, Any] = {table.table_name(): requests}
        for attempt in range(5):
            response = aws.dynamodb().batch_write_item(RequestItems=pending)
            pending = response.get("UnprocessedItems") or {}
            if not pending:
                break
            time.sleep(min(0.05 * 2**attempt, 1.0) * random.random())  # noqa: S311 - jitter
        if pending:
            raise table.StoreError("batch delete left items behind")


def _as_deleted_player(challenge_id: str, hashed: str) -> None:
    old = table.challenge_result_key(challenge_id, hashed)
    found = table.get(old, consistent=True)
    if found is None:
        return
    attributes = {k: v for k, v in found.items() if k not in ("PK", "SK")}
    new = table.key(f"CH#{challenge_id}", f"R#deleted-{secrets.token_hex(8)}")
    try:
        _move_result(new, attributes, old)
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") != "TransactionCanceledException":
            raise  # cancelled: another deletion already moved it


def _move_result(new: table.Key, attributes: dict[str, Any], old: table.Key) -> None:
    aws.dynamodb().transact_write_items(
        TransactItems=[
            {
                "Put": {
                    "TableName": table.table_name(),
                    "Item": {**new, **table.serialize(attributes)},
                }
            },
            # Only if still there: two deletions at once must not count it twice.
            {
                "Delete": {
                    "TableName": table.table_name(),
                    "Key": old,
                    "ConditionExpression": "attribute_exists(PK)",
                }
            },
        ]
    )


def _disown(challenge_id: str, hashed: str) -> None:
    try:
        aws.dynamodb().update_item(
            TableName=table.table_name(),
            Key=table.challenge_meta_key(challenge_id),
            UpdateExpression="SET ownerHash = :gone",
            ConditionExpression="ownerHash = :me",
            ExpressionAttributeValues={":gone": {"S": DELETED_OWNER}, ":me": {"S": hashed}},
        )
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
            raise


def clear_player(player_id: str) -> None:
    hashed = player_hash(player_id)
    items = _partition(f"P#{player_id}")
    for item in items:
        if str(item["SK"]).startswith("PLAY#"):
            if item.get("challengeId"):
                _as_deleted_player(str(item["challengeId"]), hashed)
            if item.get("createdChallengeId"):
                _disown(str(item["createdChallengeId"]), hashed)
    keys = [table.key(str(i["PK"]), str(i["SK"])) for i in items]
    _delete_keys([*keys, accounts.link_key(hashed)])


def delete_account(sub: str, now: dt.datetime, delete_user: DeleteUser) -> bool:
    """Delete everything of ``sub``. ``True`` when done; raises when a step failed."""
    account = _mark(sub, now)
    if account is not None:
        for player_id in sorted(account.players | {account.primary_player}):
            clear_player(player_id)
        rows = [i for i in _partition(f"ACC#{sub}") if i["SK"] not in ("META", "GONE")]
        _delete_keys([table.key(str(i["PK"]), str(i["SK"])) for i in rows])
    # Kept while another device's access token may still be used (an hour), so that token
    # cannot create the account again; it expires by itself.
    aws.dynamodb().put_item(
        TableName=table.table_name(),
        Item={
            **accounts.gone_key(sub),
            **table.serialize({"expiresAt": table.epoch_seconds(now + GONE_FOR)}),
        },
    )
    delete_user(sub)
    if account is not None:
        _delete_keys([accounts.account_key(sub)])
    return True


def cognito_delete_user(user_pool_id: str) -> DeleteUser:
    def run(sub: str) -> None:
        try:
            aws.cognito().admin_delete_user(UserPoolId=user_pool_id, Username=sub)
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") != "UserNotFoundException":
                raise

    return run


def stuck(
    now: dt.datetime, older_than: dt.timedelta = dt.timedelta(0)
) -> list[tuple[str, dt.datetime]]:
    """Accounts marked ``deleting`` for longer than ``older_than``: (sub, since)."""
    found = table.query_all(
        {
            "IndexName": "GSI_INACTIVE",
            "KeyConditionExpression": "lastActiveMonth = :m",
            "ExpressionAttributeValues": {":m": {"S": DELETING_MONTH}},
        }
    )
    result: list[tuple[str, dt.datetime]] = []
    for key in found:
        sub = str(key["PK"]).removeprefix("ACC#")
        item = table.get(accounts.account_key(sub), consistent=True)
        if item is None or "deletingSince" not in item:
            continue
        since = dt.datetime.fromisoformat(str(item["deletingSince"]))
        if now - since >= older_than:
            result.append((sub, since))
    return sorted(result)
