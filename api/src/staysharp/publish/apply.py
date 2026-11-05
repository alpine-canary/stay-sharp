"""Write a validated batch: questions, daily sets, practice pool and stock (R4, FR-024, FR-027).

All-or-nothing per batch: the whole batch is validated and planned (reading the stored versions
and sets) before the first write, and any problem refuses it. Writes then go in transactions of
at most 100 items: new question versions first (``attribute_not_exists``, a version is never
overwritten), then whole days, each day's set, stock marker and pool entries in one transaction,
so a set never exists before its questions. If a write fails, the run stops; running it again
finishes the job, because unchanged questions and days are skipped.

- A new question gets 4 random choice ids and a display order; across the new questions of a
  batch the correct position is spread evenly (S7). Later versions keep both.
- An edit that changes what players see is written as version n+1 with its ``change_reason``;
  stored grades are player items, which publish never reads or writes (FR-027).
- Today and past days cannot change: a schedule entry for them must match what is stored.
  Future days are rewritten when their questions, versions or targets change.
"""

from __future__ import annotations

import base64
import datetime as dt
import random
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, cast

from botocore.exceptions import ClientError
from pydantic import ValidationError

from staysharp import aws
from staysharp.domain import calendar
from staysharp.domain.models import DECKS, DailyItem, DailySet, Deck, Level, Question
from staysharp.publish import versions
from staysharp.publish.validate import Authored, Content, Problem, validate
from staysharp.store import table
from staysharp.store.questions import daily_set_item, question_item

MAX_TRANSACTION = 100


class Refused(Exception):  # noqa: N818 - a refusal, not a crash
    """The batch has problems; nothing was written."""

    def __init__(self, problems: Sequence[Problem]) -> None:
        super().__init__(f"{len(problems)} problem(s); nothing was written")
        self.problems = list(problems)


class WriteFailed(RuntimeError):
    """A transaction failed; earlier ones are written. Run publish again to finish."""


@dataclass(frozen=True)
class DayWrite:
    daily: DailySet
    stored_published_at: str | None
    stored: bool
    # Pool entries of questions taken out of a future set: (qid, deck).
    pool_removed: list[tuple[str, Deck]] = field(default_factory=list)


@dataclass(frozen=True)
class Plan:
    questions: list[Question]
    days: list[DayWrite]
    unchanged_questions: int = 0
    unchanged_days: int = 0
    skipped_drafts: int = 0

    def counts(self) -> dict[str, int]:
        return {
            "question_versions": len(self.questions),
            "days": len(self.days),
            "unchanged_questions": self.unchanged_questions,
            "unchanged_days": self.unchanged_days,
            "skipped_drafts": self.skipped_drafts,
        }


# --- Reading what is stored -------------------------------------------------------------------


def latest_versions(qids: Iterable[str]) -> dict[str, Question]:
    latest: dict[str, Question] = {}
    for qid in sorted(set(qids)):
        items = table.query_all(
            {
                "KeyConditionExpression": "PK = :pk",
                "ExpressionAttributeValues": {":pk": {"S": f"Q#{qid}"}},
            },
            limit=500,
        )
        if not items:
            continue
        item = max(items, key=lambda i: int(str(i["SK"]).removeprefix("V#")))
        try:
            latest[qid] = Question.model_validate(
                {k: v for k, v in item.items() if k not in ("PK", "SK")}
            )
        except ValidationError as error:
            raise table.StoreError(f"stored question {qid} is malformed") from error
    return latest


def _stored_set(day: dt.date, level: Level) -> tuple[DailySet | None, str | None]:
    item = table.get(table.daily_key(day, level), consistent=True)
    if item is None:
        return None, None
    published = item.get("publishedAt")
    try:
        daily = DailySet.model_validate({k: v for k, v in item.items() if k not in ("PK", "SK")})
    except ValidationError as error:
        raise table.StoreError(f"stored set {day} {level} is malformed") from error
    return daily, str(published) if published is not None else None


# --- Planning ---------------------------------------------------------------------------------


def _fresh_ids(rng: random.Random) -> list[str]:
    while True:
        ids = [base64.b32encode(rng.randbytes(5)).decode() for _ in range(4)]
        if len(set(ids)) == 4:
            return ids


def _balanced_positions(count: int, rng: random.Random) -> list[int]:
    """Correct positions for ``count`` new questions: each of 0..3 used within one of the others."""
    offset = rng.randrange(4)
    positions = [(offset + i) % 4 for i in range(count)]
    rng.shuffle(positions)
    return positions


def _first_version(
    authored: Mapping[str, Any], position: int, rng: random.Random, now: dt.datetime
) -> Question:
    correct = int(authored["answer"]["choice"])
    others = [i for i in range(4) if i != correct]
    rng.shuffle(others)
    display = others[:position] + [correct] + others[position:]
    return versions.build(
        authored, version=1, ids=_fresh_ids(rng), display=display, published_at=now
    )


def _plan_questions(
    approved: Sequence[Authored],
    existing: Mapping[str, Question],
    rng: random.Random,
    now: dt.datetime,
) -> tuple[list[Question], dict[str, int], int]:
    written: list[Question] = []
    current: dict[str, int] = {}
    unchanged = 0
    new = [q for q in approved if q.data["id"] not in existing]
    for q, position in zip(new, _balanced_positions(len(new), rng), strict=True):
        version = _first_version(q.data, position, rng, now)
        written.append(version)
        current[version.qid] = 1
    for q in approved:
        latest = existing.get(q.data["id"])
        if latest is None:
            continue
        nxt = versions.next_version(q.data, latest, published_at=now)
        if nxt is None:
            unchanged += 1
            current[latest.qid] = latest.version
        else:
            written.append(nxt)
            current[nxt.qid] = nxt.version
    return written, current, unchanged


def _plan_days(
    schedules: Sequence[Authored],
    current: Mapping[str, int],
    *,
    today: dt.date,
    launch: dt.date,
    now: dt.datetime,
) -> tuple[list[DayWrite], int, list[Problem]]:
    days: list[DayWrite] = []
    unchanged = 0
    problems: list[Problem] = []
    for schedule in schedules:
        level = cast(Level, schedule.data["level"])
        targets: Mapping[str, int] = schedule.data["targets"]
        for day_text, qids in sorted(schedule.data["days"].items()):
            day = dt.date.fromisoformat(day_text)
            owner = f"{level} {day_text}"
            try:
                number = calendar.game_number(day, launch)
            except ValueError:
                problems.append(Problem(owner, f"before the launch day {launch.isoformat()}"))
                continue
            items = [
                DailyItem(
                    index=i,
                    deck=deck,
                    qid=qid,
                    version=current[qid],
                    target_seconds=targets[deck],
                )
                for i, (deck, qid) in enumerate(zip(DECKS[level], qids, strict=True))
            ]
            daily = DailySet(
                date=day, level=level, game_number=number, items=items, published_at=now
            )
            stored, stored_at = _stored_set(day, level)
            if day <= today:
                if stored is None or [i.qid for i in stored.items] != list(qids):
                    problems.append(Problem(owner, "today or a past day cannot change"))
                else:
                    unchanged += 1
                continue
            if stored is not None and stored.model_copy(
                update={"published_at": None}
            ) == daily.model_copy(update={"published_at": None}):
                unchanged += 1
                continue
            removed = [(i.qid, i.deck) for i in stored.items if i.qid not in qids] if stored else []
            days.append(DayWrite(daily, stored_at, stored is not None, removed))
    return days, unchanged, problems


def plan(
    content: Content,
    *,
    today: dt.date,
    launch: dt.date,
    now: dt.datetime,
    rng: random.Random | None = None,
) -> Plan:
    """Validate and work out every write, reading the store only. Raises ``Refused``."""
    rng = rng or random.SystemRandom()
    ids = [q.data["id"] for q in content.questions if isinstance(q.data.get("id"), str)]
    existing = latest_versions(ids)
    problems = validate(content, existing=existing)
    if problems:
        raise Refused(problems)

    approved = [q for q in content.questions if q.data.get("status") == "approved"]
    drafts = len(content.questions) - len(approved)
    written, current, unchanged_q = _plan_questions(approved, existing, rng, now)
    days, unchanged_d, day_problems = _plan_days(
        content.schedules, current, today=today, launch=launch, now=now
    )
    if day_problems:
        raise Refused(sorted(set(day_problems)))
    return Plan(written, days, unchanged_q, unchanged_d, drafts)


# --- Writing ----------------------------------------------------------------------------------


def _put(item: Mapping[str, Any], condition: str | None = None, **values: Any) -> dict[str, Any]:
    put: dict[str, Any] = {"TableName": table.table_name(), "Item": table.serialize(item)}
    if condition:
        put["ConditionExpression"] = condition
    if values:
        put["ExpressionAttributeValues"] = {k: {"S": v} for k, v in values.items()}
    return {"Put": put}


def _day_items(day: DayWrite) -> list[dict[str, Any]]:
    daily = day.daily
    if not day.stored:
        guard = "attribute_not_exists(PK)"
        values: dict[str, Any] = {}
    elif day.stored_published_at is None:
        guard = "attribute_exists(PK) AND attribute_not_exists(publishedAt)"
        values = {}
    else:
        guard = "publishedAt = :seen"
        values = {":seen": day.stored_published_at}
    ops = [_put(daily_set_item(daily), guard, **values)]
    stock = table.stock_key(daily.level, daily.date)
    ops.append(_put({"PK": stock["PK"]["S"], "SK": stock["SK"]["S"]}))
    for item in daily.items:
        k = table.pool_key(daily.level, item.deck, daily.date, item.qid)
        ops.append(_put({"PK": k["PK"]["S"], "SK": k["SK"]["S"], "version": item.version}))
    for qid, deck in day.pool_removed:
        ops.append(
            {
                "Delete": {
                    "TableName": table.table_name(),
                    "Key": table.pool_key(daily.level, deck, daily.date, qid),
                }
            }
        )
    return ops


def _transactions(plan_: Plan) -> list[list[dict[str, Any]]]:
    chunks: list[list[dict[str, Any]]] = []
    questions = [_put(question_item(q), "attribute_not_exists(PK)") for q in plan_.questions]
    for start in range(0, len(questions), MAX_TRANSACTION):
        chunks.append(questions[start : start + MAX_TRANSACTION])
    current: list[dict[str, Any]] = []
    for day in plan_.days:
        ops = _day_items(day)
        if len(current) + len(ops) > MAX_TRANSACTION:
            chunks.append(current)
            current = []
        current += ops
    if current:
        chunks.append(current)
    return chunks


def write(plan_: Plan) -> None:
    chunks = _transactions(plan_)
    client = aws.dynamodb()
    for n, chunk in enumerate(chunks, start=1):
        try:
            client.transact_write_items(TransactItems=chunk)  # type: ignore[arg-type]
        except ClientError as error:
            code = error.response.get("Error", {}).get("Code", "unknown")
            reasons = [r.get("Code", "None") for r in error.response.get("CancellationReasons", [])]
            detail = f" ({', '.join(reasons)})" if reasons else ""
            raise WriteFailed(
                f"transaction {n} of {len(chunks)} failed: {code}{detail}; "
                "earlier transactions are written, run publish again to finish"
            ) from error


def publish(
    content: Content,
    *,
    today: dt.date,
    launch: dt.date,
    now: dt.datetime,
    rng: random.Random | None = None,
) -> Plan:
    result = plan(content, today=today, launch=launch, now=now, rng=rng)
    write(result)
    return result
