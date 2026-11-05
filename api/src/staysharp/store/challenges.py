"""Challenges (A6): create once per play, read, record a colleague's result (task T104, W4).

``CH#<challengeId>`` / ``META`` holds the date, level and game number of the set, the owner's
``ownerHash`` = HMAC(pepper, playerId) (never the raw id), the owner's snapshot, the ``results``
count and ``expiresAt`` (30 days, compared with now on every read: TTL deletion lags).
``CH#<challengeId>`` / ``R#<playerHash>`` holds one colleague's snapshot.

The id is 12 random base32 characters, stored on the owner's play as ``createdChallengeId``
(the play's own ``challengeId`` means "started from that link"). Creating it is one transaction:
the ``META`` put and the play update, both conditional, so two clicks never make two challenges.
"""

from __future__ import annotations

import base64
import datetime as dt
import secrets
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from botocore.exceptions import ClientError

from staysharp import aws
from staysharp.domain.models import Level, ResultSnapshot
from staysharp.obs import player_hash
from staysharp.store import table
from staysharp.store.plays import QUESTIONS, Play

CHALLENGE_DAYS = 30
MAX_RESULTS = 50
RESULT_PREFIX = "R#"


class NotFinished(Exception):
    """A challenge needs a finished play."""


class Unknown(Exception):
    """No such challenge."""


class Expired(Exception):
    """The challenge is past its ``expiresAt``."""


@dataclass(frozen=True)
class Challenge:
    challenge_id: str
    date: dt.date
    level: Level
    game_number: int
    owner_hash: str
    owner: ResultSnapshot
    results: int
    expires_at: int


def new_id() -> str:
    """12 random base32 characters (60 bits)."""
    return base64.b32encode(secrets.token_bytes(8)).decode()[:12]


def snapshot(play: Play) -> ResultSnapshot:
    if not play.finished:
        raise NotFinished(play.play_id)
    return ResultSnapshot(
        grades=[float(play.grades[i]) for i in range(QUESTIONS)],
        score=float(play.score),
        bonus=float(play.bonus),
        elapsed_ms=play.elapsed_ms,
        relaxed=play.relaxed,
    )


def _snapshot_item(snap: ResultSnapshot) -> dict[str, Any]:
    return {
        "grades": [Decimal(str(g)) for g in snap.grades],
        "score": Decimal(str(snap.score)),
        "bonus": Decimal(str(snap.bonus)),
        "elapsedMs": snap.elapsed_ms,
        "relaxed": snap.relaxed,
    }


def _snapshot_from(item: dict[str, Any]) -> ResultSnapshot:
    return ResultSnapshot(
        grades=[float(g) for g in item["grades"]],
        score=float(item["score"]),
        bonus=float(item["bonus"]),
        elapsed_ms=int(item["elapsedMs"]),
        relaxed=bool(item["relaxed"]),
    )


def _from_item(challenge_id: str, item: dict[str, Any]) -> Challenge:
    try:
        return Challenge(
            challenge_id=challenge_id,
            date=dt.date.fromisoformat(item["date"]),
            level=item["level"],
            game_number=int(item["gameNumber"]),
            owner_hash=str(item["ownerHash"]),
            owner=_snapshot_from(item["owner"]),
            results=int(item.get("results", 0)),
            expires_at=int(item["expiresAt"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise table.StoreError("challenge item is malformed") from error


def get(challenge_id: str, now: dt.datetime) -> Challenge:
    """Raise ``Unknown`` or ``Expired``; otherwise the challenge."""
    item = table.get(table.challenge_meta_key(challenge_id), consistent=True)
    if item is None:
        raise Unknown(challenge_id)
    challenge = _from_item(challenge_id, item)
    if challenge.expires_at <= table.epoch_seconds(now):
        raise Expired(challenge_id)
    return challenge


def create(player_id: str, play: Play, now: dt.datetime) -> str:
    """Return the play's challenge id, creating it the first time."""
    snap = snapshot(play)
    if play.created_challenge_id is not None:
        return play.created_challenge_id
    challenge_id = new_id()
    meta: dict[str, Any] = {
        "date": play.ref.date.isoformat(),
        "level": play.ref.level,
        "gameNumber": play.game_number,
        "ownerHash": player_hash(player_id),
        "owner": _snapshot_item(snap),
        "results": 0,
        "createdAt": table.iso_ms(now),
        "expiresAt": table.epoch_seconds(now + dt.timedelta(days=CHALLENGE_DAYS)),
    }
    name = table.table_name()
    try:
        aws.dynamodb().transact_write_items(
            TransactItems=[
                {
                    "Put": {
                        "TableName": name,
                        "Item": {**table.challenge_meta_key(challenge_id), **table.serialize(meta)},
                        "ConditionExpression": "attribute_not_exists(PK)",
                    }
                },
                {
                    "Update": {
                        "TableName": name,
                        "Key": table.play_key(player_id, play.play_id),
                        "UpdateExpression": "SET createdChallengeId = :id",
                        "ConditionExpression": (
                            "attribute_exists(PK) AND attribute_not_exists(createdChallengeId)"
                        ),
                        "ExpressionAttributeValues": {":id": {"S": challenge_id}},
                    }
                },
            ]
        )
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") != "TransactionCanceledException":
            raise
        # Lost a race with a second click: the play now names the challenge that won.
        item = table.get(table.play_key(player_id, play.play_id), consistent=True)
        existing = None if item is None else item.get("createdChallengeId")
        if not isinstance(existing, str):
            raise table.StoreError("challenge create cancelled without a winner") from error
        return existing
    return challenge_id


def result(challenge_id: str, player_id: str) -> ResultSnapshot | None:
    item = table.get(
        table.challenge_result_key(challenge_id, player_hash(player_id)), consistent=True
    )
    return None if item is None else _snapshot_from(item)


def results(challenge_id: str) -> list[ResultSnapshot]:
    """Every colleague who finished, oldest first."""
    items = table.query_all(
        {
            "KeyConditionExpression": "PK = :pk AND begins_with(SK, :r)",
            "ExpressionAttributeValues": {
                ":pk": {"S": f"CH#{challenge_id}"},
                ":r": {"S": RESULT_PREFIX},
            },
            "ConsistentRead": True,
        },
        limit=MAX_RESULTS + 5,
    )
    items.sort(key=lambda item: str(item.get("finishedAt", "")))
    return [_snapshot_from(item) for item in items]


def result_items(
    challenge_id: str, player_id: str, snap: ResultSnapshot, now: dt.datetime, name: str
) -> list[dict[str, Any]]:
    """Transaction items 2 and 3 (research R2): the result put and the capped counter."""
    item = {
        **_snapshot_item(snap),
        "finishedAt": table.iso_ms(now),
        # Never longer than the challenge itself, which lives at most 30 days from now.
        "expiresAt": table.epoch_seconds(now + dt.timedelta(days=CHALLENGE_DAYS)),
    }
    return [
        {
            "Put": {
                "TableName": name,
                "Item": {
                    **table.challenge_result_key(challenge_id, player_hash(player_id)),
                    **table.serialize(item),
                },
                "ConditionExpression": "attribute_not_exists(PK)",
            }
        },
        {
            "Update": {
                "TableName": name,
                "Key": table.challenge_meta_key(challenge_id),
                "UpdateExpression": "ADD results :one",
                "ConditionExpression": "attribute_exists(PK) AND results < :cap",
                "ExpressionAttributeValues": {
                    ":one": {"N": "1"},
                    ":cap": {"N": str(MAX_RESULTS)},
                },
            }
        },
    ]


def record(challenge_id: str, player_id: str, snap: ResultSnapshot, now: dt.datetime) -> bool:
    """Write a colleague's result outside an answer (Story 4, 3a). ``False`` when the cap is
    reached or it already exists; nothing is written then."""
    try:
        items: Any = result_items(challenge_id, player_id, snap, now, table.table_name())
        aws.dynamodb().transact_write_items(TransactItems=items)
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") != "TransactionCanceledException":
            raise
        reasons = error.response.get("CancellationReasons") or []
        codes = {r.get("Code") for r in reasons if isinstance(r, dict)}
        if codes <= {"None", "ConditionalCheckFailed"}:
            return False
        raise
    return True
