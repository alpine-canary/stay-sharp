"""Plays (A3): start or resume, read, switch to relaxed (task T060, data-model Play).

``playId`` is ``<date>.<level>.<mode>`` under the player's key, so starting twice is the same
item: the put is conditional and a lost race simply reads the existing play. Score fields are
only ever changed by the answer transaction with ``ADD`` (store/answers.py).

A play past its ``expiresAt`` counts as absent even before TTL deletes it, and starting again
replaces it.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from botocore.exceptions import ClientError

from staysharp import aws
from staysharp.domain.models import Level, Mode
from staysharp.store import table

PLAY_DAYS = 90
QUESTIONS = 5


class ReplayLocked(Exception):
    """``mode=replay`` for a day whose daily play is not finished (C3)."""


@dataclass(frozen=True)
class PlayRef:
    date: dt.date
    level: Level
    mode: Mode

    @property
    def play_id(self) -> str:
        return f"{self.date.isoformat()}.{self.level}.{self.mode}"

    @classmethod
    def parse(cls, play_id: str) -> PlayRef:
        """Parse a ``playId`` already checked against the contract pattern."""
        day, level, mode = play_id.split(".")
        if level not in ("senior", "starter") or mode not in ("daily", "replay"):
            raise ValueError("malformed play id")
        return cls(dt.date.fromisoformat(day), level, mode)  # type: ignore[arg-type]


@dataclass(frozen=True)
class Play:
    ref: PlayRef
    game_number: int
    relaxed: bool
    relaxed_from: int | None
    started_at: dt.datetime
    expires_at: int
    grades: dict[int, Decimal] = field(default_factory=dict)
    answered: frozenset[int] = frozenset()
    score: Decimal = Decimal(0)
    bonus: Decimal = Decimal(0)
    elapsed_ms: int = 0
    challenge_id: str | None = None
    # The challenge this play created (store/challenges.py), not the one it was started from.
    created_challenge_id: str | None = None

    @property
    def play_id(self) -> str:
        return self.ref.play_id

    @property
    def finished(self) -> bool:
        return len(self.answered) == QUESTIONS

    @property
    def next_index(self) -> int | None:
        """First unanswered question (FR-008), ``None`` when finished."""
        return next((i for i in range(QUESTIONS) if i not in self.answered), None)


def _number(item: dict[str, Any], name: str) -> Decimal:
    value = item.get(name, 0)
    if not isinstance(value, (int, Decimal)):
        raise table.StoreError(f"play field {name} is not a number")
    return Decimal(value)


def from_item(item: dict[str, Any]) -> Play:
    try:
        ref = PlayRef(dt.date.fromisoformat(item["date"]), item["level"], item["mode"])
        if f"PLAY#{ref.play_id}" != item["SK"]:
            raise table.StoreError("play item does not match its key")
        grades_raw = item.get("grades", {})
        answered_raw = item.get("answered", set())
        if not isinstance(grades_raw, dict) or not isinstance(answered_raw, set):
            raise table.StoreError("play grades or answered have the wrong type")
        relaxed_from = item.get("relaxedFrom")
        return Play(
            ref=ref,
            game_number=int(item["gameNumber"]),
            relaxed=bool(item.get("relaxed", False)),
            relaxed_from=None if relaxed_from is None else int(relaxed_from),
            started_at=dt.datetime.fromisoformat(item["startedAt"]),
            expires_at=int(item["expiresAt"]),
            grades={int(i): Decimal(g) for i, g in grades_raw.items()},
            answered=frozenset(int(i) for i in answered_raw),
            score=_number(item, "score"),
            bonus=_number(item, "bonus"),
            elapsed_ms=int(_number(item, "elapsedMs")),
            challenge_id=item.get("challengeId"),
            created_challenge_id=item.get("createdChallengeId"),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise table.StoreError("play item is malformed") from error


def get(player_id: str, ref: PlayRef, now: dt.datetime) -> Play | None:
    item = table.get(table.play_key(player_id, ref.play_id), consistent=True)
    if item is None or table.expired(item, now):
        return None
    return from_item(item)


def start(
    player_id: str,
    ref: PlayRef,
    *,
    game_number: int,
    relaxed: bool,
    lock_replay: bool,
    now: dt.datetime,
    challenge_id: str | None = None,
) -> tuple[Play, bool]:
    """Create the play, or return the existing one. ``True`` when created.

    ``lock_replay`` is set by the caller while the daily of that date can still be answered: a
    replay then needs the daily play to be finished first (C3), so a replay can never be used
    to read answers before playing. A challenge replay of a past day is locked only while that
    day's daily play exists unfinished: with no daily play, that day can no longer be started.
    """
    existing = get(player_id, ref, now)
    if existing is not None:
        return existing, False
    if ref.mode == "replay" and lock_replay:
        daily = get(player_id, PlayRef(ref.date, ref.level, "daily"), now)
        if daily is None and challenge_id is None:
            raise ReplayLocked(ref.play_id)
        if daily is not None and not daily.finished:
            raise ReplayLocked(ref.play_id)

    item: dict[str, Any] = {
        "date": ref.date.isoformat(),
        "level": ref.level,
        "mode": ref.mode,
        "gameNumber": game_number,
        "relaxed": relaxed,
        "startedAt": table.iso_ms(now),
        "expiresAt": table.epoch_seconds(now + dt.timedelta(days=PLAY_DAYS)),
        "grades": {},
        "score": 0,
        "bonus": 0,
        "elapsedMs": 0,
    }
    if relaxed:
        item["relaxedFrom"] = 0
    if challenge_id is not None:
        item["challengeId"] = challenge_id
    key = table.play_key(player_id, ref.play_id)
    try:
        aws.dynamodb().put_item(
            TableName=table.table_name(),
            Item={**key, **table.serialize(item)},
            ConditionExpression="attribute_not_exists(PK) OR expiresAt <= :now",
            ExpressionAttributeValues={":now": {"N": str(table.epoch_seconds(now))}},
        )
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
            raise
        # Another request created it first: same play, not a new one.
        raced = get(player_id, ref, now)
        if raced is None:
            raise table.StoreError("play vanished after a lost create race") from error
        return raced, False
    return from_item({"PK": key["PK"]["S"], "SK": key["SK"]["S"], **item}), True


def relax(player_id: str, play: Play) -> Play:
    """One-way switch (FR-005c): bonuses stop from the next unanswered question on."""
    if play.relaxed:
        return play
    first = play.next_index if play.next_index is not None else QUESTIONS
    response = aws.dynamodb().update_item(
        TableName=table.table_name(),
        Key=table.play_key(player_id, play.play_id),
        UpdateExpression="SET relaxed = :t, relaxedFrom = if_not_exists(relaxedFrom, :i)",
        ConditionExpression="attribute_exists(PK)",
        ExpressionAttributeValues={":t": {"BOOL": True}, ":i": {"N": str(first)}},
        ReturnValues="ALL_NEW",
    )
    attributes = response.get("Attributes")
    if not attributes:
        raise table.StoreError("relax returned no item")
    return from_item(table.deserialize(attributes))
