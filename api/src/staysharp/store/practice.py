"""Practice (A5): past questions only, graded once per attempt (task T110, FR-021, C4, R2).

``next`` reads the pool ``POOL#<level>#<deck>`` with ``SK < today`` and picks a question from
that result only. A preferred id is honoured when it is in the result; anything else (a future
id, an unknown one, another level's) is ignored, never looked up as a ``Q#`` key. Each pick
counts against the player's 200 a day (``PRACOUNT#<date>``, conditional ``ADD``) and creates an
attempt ``PRA#<attemptId>`` with ``servedAt``; ``answer`` grades it with the same once-only
transaction as the daily, on that one item.
"""

from __future__ import annotations

import base64
import datetime as dt
import secrets
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError

from staysharp import aws
from staysharp.domain import calendar, cancellation, grading
from staysharp.domain.cancellation import Outcome
from staysharp.domain.grading import Submission
from staysharp.domain.models import DECKS, Deck, Level
from staysharp.store import answers, table
from staysharp.store.answers import ANSWER_CONDITION, Graded, ScoringFailure, Served

ATTEMPT_DAYS = 14
DAILY_LIMIT = 200
COUNT_DAYS = 2


class Limited(Exception):
    """More than ``DAILY_LIMIT`` practice questions today."""


class Empty(Exception):
    """No past question in that level and deck yet."""


@dataclass(frozen=True)
class Picked:
    attempt_id: str
    served: Served


def new_attempt_id() -> str:
    """16 random base32 characters (80 bits)."""
    return base64.b32encode(secrets.token_bytes(10)).decode()


def _count(player_id: str, today: dt.date, now: dt.datetime) -> None:
    try:
        aws.dynamodb().update_item(
            TableName=table.table_name(),
            Key=table.practice_count_key(player_id, today),
            UpdateExpression="ADD n :one SET expiresAt = :exp",
            ConditionExpression="attribute_not_exists(n) OR n < :limit",
            ExpressionAttributeValues={
                ":one": {"N": "1"},
                ":limit": {"N": str(DAILY_LIMIT)},
                ":exp": {"N": str(table.epoch_seconds(now + dt.timedelta(days=COUNT_DAYS)))},
            },
        )
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            raise Limited from error
        raise


def _pool(level: Level, decks: Sequence[Deck], today: dt.date) -> dict[str, tuple[Deck, int]]:
    """qid -> (deck, version), from the past pool only (C4)."""
    found: dict[str, tuple[Deck, int]] = {}
    for deck in decks:
        for item in table.query_all(table.pool_query(level, deck, today)):
            sk = str(item["SK"])
            day, _, qid = sk.partition("#")
            if not qid or dt.date.fromisoformat(day) >= today:
                raise table.StoreError("pool entry outside the past pool")
            found[qid] = (deck, int(item["version"]))
    return found


def pick(
    player_id: str,
    level: Level,
    deck: Deck | None,
    prefer: Sequence[str],
    now: dt.datetime,
) -> Picked:
    """Count the attempt, pick a past question and record ``servedAt``."""
    today = calendar.zurich_today(now)
    pool = _pool(level, [deck] if deck else DECKS[level], today)
    if not pool:
        raise Empty(level)
    _count(player_id, today, now)
    qid = next((q for q in prefer if q in pool), None)
    if qid is None:
        qid = secrets.choice(sorted(pool))
    chosen_deck, version = pool[qid]
    served = Served(
        index=0,
        qid=qid,
        version=version,
        deck=chosen_deck,
        target_seconds=0,
        served_at=now,
    )
    attempt_id = new_attempt_id()
    item = {
        "qid": qid,
        "version": version,
        "deck": chosen_deck,
        "targetSeconds": 0,
        "servedAt": table.iso_ms(now),
        "expiresAt": table.epoch_seconds(now + dt.timedelta(days=ATTEMPT_DAYS)),
    }
    aws.dynamodb().put_item(
        TableName=table.table_name(),
        Item={**table.practice_key(player_id, attempt_id), **table.serialize(item)},
        ConditionExpression="attribute_not_exists(PK)",
    )
    return Picked(attempt_id, served)


def read(player_id: str, attempt_id: str, now: dt.datetime) -> Served | None:
    item = table.get(table.practice_key(player_id, attempt_id), consistent=True)
    if item is None or table.expired(item, now):
        return None
    return answers.served_from(0, item)


def answer(
    player_id: str,
    attempt_id: str,
    served: Served,
    submission: Submission,
    key: grading.AnswerKey,
    now: dt.datetime,
) -> Graded:
    """Grade once (R2 on one item). Practice has no speed bonus: it is scored as relaxed."""
    if served.graded:
        same = served.choice_id == submission.choice_id and served.line == submission.line
        return Graded(served, Outcome.DUPLICATE if same else Outcome.CONFLICT)
    elapsed_ms = max(0, int((now - served.served_at).total_seconds() * 1000))
    scored = grading.score(
        served.deck, key, submission, relaxed=True, elapsed_ms=elapsed_ms, target_seconds=0
    )
    values: dict[str, Any] = {
        ":c": submission.choice_id,
        ":g": scored.grade,
        ":b": scored.bonus,
        ":at": table.iso_ms(now),
        ":e": elapsed_ms,
    }
    update = "SET choiceId = :c, grade = :g, bonus = :b, answeredAt = :at, elapsedMs = :e"
    if submission.line is not None:
        update += ", line = :l"
        values[":l"] = submission.line
    items: Any = [
        {
            "Update": {
                "TableName": table.table_name(),
                "Key": table.practice_key(player_id, attempt_id),
                "UpdateExpression": update,
                "ConditionExpression": ANSWER_CONDITION,
                "ExpressionAttributeValues": table.serialize(values),
                "ReturnValuesOnConditionCheckFailure": "ALL_OLD",
            }
        }
    ]
    client = aws.dynamodb()
    last: Exception | None = None
    for attempt in range(answers.ATTEMPTS):
        if attempt:
            answers.sleep(answers.backoff(attempt))
        try:
            client.transact_write_items(TransactItems=items)
        except ClientError as error:
            last = error
            if error.response.get("Error", {}).get("Code") != "TransactionCanceledException":
                continue
            reasons = answers.cancellation_reasons(error)
            outcome = cancellation.classify(reasons, submission)
            if outcome is Outcome.RETRY:
                continue
            if outcome is Outcome.NOT_OPENED:
                raise answers.NotOpened from error
            stored = reasons[cancellation.ANSWER_POSITION].item
            if stored is None or outcome not in (Outcome.DUPLICATE, Outcome.CONFLICT):
                raise ScoringFailure(f"unexpected outcome {outcome}") from error
            return Graded(answers.served_from(0, stored), outcome)
        except BotoCoreError as error:
            last = error
            continue
        graded = Served(
            index=0,
            qid=served.qid,
            version=served.version,
            deck=served.deck,
            target_seconds=0,
            served_at=served.served_at,
            choice_id=submission.choice_id,
            line=submission.line,
            grade=scored.grade,
            bonus=scored.bonus,
            elapsed_ms=elapsed_ms,
        )
        return Graded(graded, None, scored.suspiciously_fast)
    raise ScoringFailure("practice answer not stored after retries") from last
