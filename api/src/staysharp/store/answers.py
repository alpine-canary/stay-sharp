"""Answers (A4): open a question, grade an answer once (task T061, research R2, W1).

``open`` creates the answer item and writes ``servedAt`` the first time only, with the question
id, version, deck and target copied from the daily set, so the answer path needs no daily-set
read. ``answer`` runs one transaction:

0. the answer item, condition ``attribute_exists(servedAt) AND attribute_not_exists(grade)``,
   ``ReturnValuesOnConditionCheckFailure=ALL_OLD``;
1. the play item, purely additive (``ADD`` and ``SET grades.#i``), no condition;
2. and 3., only on the fifth answer of a play started from a challenge link: the colleague's
   result item (``attribute_not_exists``) and the challenge counter (``results < 50``). When only
   those fail (cap reached, or the result was already written from the finished play), the
   transaction is sent again without them: the answer is still graded.

Item 0 alone makes an answer once-only. A cancelled transaction is classified by
``domain/cancellation.py``; temporary failures are retried up to three times with backoff and
jitter, then raised as ``ScoringFailure`` (503). A temporary error is never read as a duplicate.
"""

from __future__ import annotations

import datetime as dt
import random
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError

from staysharp import aws
from staysharp.domain import cancellation, grading
from staysharp.domain.cancellation import Outcome, Reason
from staysharp.domain.grading import Submission
from staysharp.domain.models import DailyItem, Deck, ResultSnapshot
from staysharp.store import challenges, table
from staysharp.store.plays import QUESTIONS, Play

ATTEMPTS = 3
BASE_DELAY_S = 0.05
MAX_DELAY_S = 0.4

ANSWER_CONDITION = "attribute_exists(servedAt) AND attribute_not_exists(grade)"

# Replaced in tests so retries do not slow the suite down.
sleep: Callable[[float], None] = time.sleep


class ScoringFailure(Exception):
    """The answer could not be stored after retries. Nothing partial was written."""


class NotOpened(Exception):
    """The question was never opened for this play (or its item expired)."""


@dataclass(frozen=True)
class Served:
    """The answer item as written by ``open``, plus the grade once answered."""

    index: int
    qid: str
    version: int
    deck: Deck
    target_seconds: int
    served_at: dt.datetime
    choice_id: str | None = None
    line: int | None = None
    grade: Decimal | None = None
    bonus: Decimal | None = None
    elapsed_ms: int | None = None

    @property
    def graded(self) -> bool:
        return self.grade is not None


@dataclass(frozen=True)
class Graded:
    """The result of ``answer``: the stored answer and how it came to be."""

    served: Served
    outcome: Outcome | None  # None: newly graded; DUPLICATE or CONFLICT otherwise
    suspiciously_fast: bool = False
    finished_play: bool = False
    challenge_recorded: bool = False


def served_from(index: int, item: Mapping[str, Any]) -> Served:
    try:
        grade = item.get("grade")
        bonus = item.get("bonus")
        line = item.get("line")
        elapsed = item.get("elapsedMs")
        return Served(
            index=index,
            qid=str(item["qid"]),
            version=int(item["version"]),
            deck=item["deck"],
            target_seconds=int(item["targetSeconds"]),
            served_at=dt.datetime.fromisoformat(item["servedAt"]),
            choice_id=item.get("choiceId"),
            line=None if line is None else int(line),
            grade=None if grade is None else Decimal(grade),
            bonus=None if bonus is None else Decimal(bonus),
            elapsed_ms=None if elapsed is None else int(elapsed),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise table.StoreError("answer item is malformed") from error


def open_question(player_id: str, play: Play, daily_item: DailyItem, now: dt.datetime) -> Served:
    """Create the answer item or return it; ``servedAt`` is set once (FR-005a).

    An item left by an expired play with the same id (TTL lag) has a different ``expiresAt``
    and is replaced instead of reused.
    """
    key = table.answer_key(player_id, play.play_id, daily_item.index)
    values = table.serialize(
        {
            ":now": table.iso_ms(now),
            ":qid": daily_item.qid,
            ":v": daily_item.version,
            ":deck": daily_item.deck,
            ":t": daily_item.target_seconds,
            ":exp": play.expires_at,
        }
    )
    client = aws.dynamodb()
    try:
        response = client.update_item(
            TableName=table.table_name(),
            Key=key,
            UpdateExpression=(
                "SET servedAt = if_not_exists(servedAt, :now), qid = if_not_exists(qid, :qid), "
                "version = if_not_exists(version, :v), deck = if_not_exists(deck, :deck), "
                "targetSeconds = if_not_exists(targetSeconds, :t), expiresAt = :exp"
            ),
            ConditionExpression="attribute_not_exists(expiresAt) OR expiresAt = :exp",
            ExpressionAttributeValues=values,
            ReturnValues="ALL_NEW",
        )
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
            raise
        fresh = {
            "servedAt": table.iso_ms(now),
            "qid": daily_item.qid,
            "version": daily_item.version,
            "deck": daily_item.deck,
            "targetSeconds": daily_item.target_seconds,
            "expiresAt": play.expires_at,
        }
        client.put_item(
            TableName=table.table_name(),
            Item={**key, **table.serialize(fresh)},
            ConditionExpression="expiresAt <> :exp",
            ExpressionAttributeValues={":exp": {"N": str(play.expires_at)}},
        )
        return served_from(daily_item.index, fresh)
    attributes = response.get("Attributes")
    if not attributes:
        raise table.StoreError("open returned no item")
    return served_from(daily_item.index, table.deserialize(attributes))


def read(player_id: str, play: Play, index: int) -> Served | None:
    item = table.get(table.answer_key(player_id, play.play_id, index), consistent=True)
    if item is None or item.get("expiresAt") != play.expires_at:
        return None
    return served_from(index, item)


def _same(served: Served, submission: Submission) -> bool:
    return served.choice_id == submission.choice_id and served.line == submission.line


def _transaction(
    player_id: str,
    play: Play,
    served: Served,
    submission: Submission,
    scored: grading.Scored,
    elapsed_ms: int,
    now: dt.datetime,
    name: str,
) -> list[dict[str, Any]]:
    answer_set = ["SET choiceId = :c", "grade = :g", "bonus = :b", "answeredAt = :at"]
    answer_set.append("elapsedMs = :e")
    answer_values: dict[str, Any] = {
        ":c": submission.choice_id,
        ":g": scored.grade,
        ":b": scored.bonus,
        ":at": table.iso_ms(now),
        ":e": elapsed_ms,
    }
    if submission.line is not None:
        answer_set.append("line = :l")
        answer_values[":l"] = submission.line
    return [
        {
            "Update": {
                "TableName": name,
                "Key": table.answer_key(player_id, play.play_id, served.index),
                "UpdateExpression": ", ".join(answer_set),
                "ConditionExpression": ANSWER_CONDITION,
                "ExpressionAttributeValues": table.serialize(answer_values),
                "ReturnValuesOnConditionCheckFailure": "ALL_OLD",
            }
        },
        {
            "Update": {
                "TableName": name,
                "Key": table.play_key(player_id, play.play_id),
                "UpdateExpression": (
                    "ADD score :g, bonus :b, elapsedMs :e, answered :i SET grades.#i = :g"
                ),
                "ExpressionAttributeNames": {"#i": str(served.index)},
                "ExpressionAttributeValues": {
                    **table.serialize({":g": scored.grade, ":b": scored.bonus, ":e": elapsed_ms}),
                    ":i": {"SS": [str(served.index)]},
                },
            }
        },
    ]


def _final_snapshot(
    play: Play, index: int, scored: grading.Scored, elapsed_ms: int
) -> ResultSnapshot:
    """The play as it will be once this, its fifth answer, is stored."""
    grades = {**play.grades, index: scored.grade}
    return ResultSnapshot(
        grades=[float(grades[i]) for i in range(QUESTIONS)],
        score=float(play.score + scored.grade),
        bonus=float(play.bonus + scored.bonus),
        elapsed_ms=play.elapsed_ms + elapsed_ms,
        relaxed=play.relaxed,
    )


def cancellation_reasons(error: ClientError) -> list[Reason]:
    raw = error.response.get("CancellationReasons")
    if not isinstance(raw, list):
        return []
    reasons: list[Reason] = []
    for entry in raw:
        item = entry.get("Item") if isinstance(entry, Mapping) else None
        code = entry.get("Code", "") if isinstance(entry, Mapping) else ""
        reasons.append(Reason(str(code), table.deserialize(item) if item else None))
    return reasons


def backoff(attempt: int) -> float:
    """Full jitter: a random delay up to an exponentially growing cap."""
    return random.uniform(0, min(MAX_DELAY_S, BASE_DELAY_S * 2**attempt))  # noqa: S311


def answer(
    player_id: str,
    play: Play,
    served: Served,
    submission: Submission,
    key: grading.AnswerKey,
    now: dt.datetime,
    *,
    client: Any = None,
    table_name: str | None = None,
) -> Graded:
    """Grade and store once. Raises ``NotOpened`` or ``ScoringFailure``.

    ``client`` and ``table_name`` default to the shared client and ``TABLE_NAME``; the self-check
    passes a stub and a dummy name.
    """
    if served.graded:
        outcome = Outcome.DUPLICATE if _same(served, submission) else Outcome.CONFLICT
        return Graded(served, outcome)

    elapsed_ms = max(0, int((now - served.served_at).total_seconds() * 1000))
    scored = grading.score(
        served.deck,
        key,
        submission,
        relaxed=play.relaxed,
        elapsed_ms=elapsed_ms,
        target_seconds=served.target_seconds,
    )
    name = table_name or table.table_name()
    items = _transaction(player_id, play, served, submission, scored, elapsed_ms, now, name)
    finishing = served.index not in play.answered and len(play.answered) == QUESTIONS - 1
    if finishing and play.challenge_id is not None:
        snap = _final_snapshot(play, served.index, scored, elapsed_ms)
        items += challenges.result_items(play.challenge_id, player_id, snap, now, name)
    client = client or aws.dynamodb()
    last: Exception | None = None
    for attempt in range(ATTEMPTS):
        if attempt:
            sleep(backoff(attempt))
        try:
            client.transact_write_items(TransactItems=items)
        except ClientError as error:
            last = error
            if error.response.get("Error", {}).get("Code") != "TransactionCanceledException":
                continue
            reasons = cancellation_reasons(error)
            outcome = cancellation.classify(reasons, submission)
            if outcome is Outcome.CHALLENGE_FULL and len(items) > cancellation.CHALLENGE_FROM:
                # Not a failure: grade the answer without the challenge items, at once.
                items = items[: cancellation.CHALLENGE_FROM]
                try:
                    client.transact_write_items(TransactItems=items)
                except (ClientError, BotoCoreError) as retry_error:
                    last = retry_error
                    continue
                return _graded(served, submission, scored, elapsed_ms, finishing, False)
            if outcome is Outcome.RETRY:
                continue
            if outcome is Outcome.NOT_OPENED:
                raise NotOpened from error
            stored = reasons[cancellation.ANSWER_POSITION].item
            if stored is None or outcome not in (Outcome.DUPLICATE, Outcome.CONFLICT):
                raise ScoringFailure(f"unexpected outcome {outcome}") from error
            return Graded(served_from(served.index, stored), outcome)
        except BotoCoreError as error:
            last = error
            continue
        recorded = len(items) > cancellation.CHALLENGE_FROM
        return _graded(served, submission, scored, elapsed_ms, finishing, recorded)
    raise ScoringFailure("answer not stored after retries") from last


def _graded(
    served: Served,
    submission: Submission,
    scored: grading.Scored,
    elapsed_ms: int,
    finishing: bool,
    challenge_recorded: bool,
) -> Graded:
    stored = Served(
        index=served.index,
        qid=served.qid,
        version=served.version,
        deck=served.deck,
        target_seconds=served.target_seconds,
        served_at=served.served_at,
        choice_id=submission.choice_id,
        line=submission.line,
        grade=scored.grade,
        bonus=scored.bonus,
        elapsed_ms=elapsed_ms,
    )
    return Graded(stored, None, scored.suspiciously_fast, finishing, challenge_recorded)
