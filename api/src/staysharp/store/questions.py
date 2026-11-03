"""Read daily sets (A1) and question versions (A2).

A missing daily set is a normal state ("Today's set is not ready yet", Story 7 scenario 2): it is
returned as ``NotReady``, never raised. A daily set that points at a missing question version is
a publishing fault and raises ``StoreError``.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from staysharp.domain.models import DailySet, Level, Question
from staysharp.store import table

_KEYS = ("PK", "SK")


@dataclass(frozen=True)
class NotReady:
    day: dt.date
    level: Level


def _strip(item: dict[str, Any]) -> dict[str, Any]:
    return {name: value for name, value in item.items() if name not in _KEYS}


def daily_set(day: dt.date, level: Level) -> DailySet | NotReady:
    item = table.get(table.daily_key(day, level))
    if item is None:
        return NotReady(day, level)
    try:
        return DailySet.model_validate(_strip(item))
    except ValidationError as error:
        raise StoreError(f"daily set {day} {level} is malformed") from error


def question(qid: str, version: int) -> Question:
    item = table.get(table.question_key(qid, version))
    if item is None:
        raise StoreError(f"question {qid} v{version} is missing")
    try:
        return Question.model_validate(_strip(item))
    except ValidationError as error:
        raise StoreError(f"question {qid} v{version} is malformed") from error


def question_item(question_: Question) -> dict[str, Any]:
    """The stored item for a question version (used by seed and publish)."""
    data = question_.model_dump(by_alias=True, exclude_none=True, mode="json")
    key = table.question_key(question_.qid, question_.version)
    return {"PK": key["PK"]["S"], "SK": key["SK"]["S"], **data}


def daily_set_item(daily: DailySet) -> dict[str, Any]:
    data = daily.model_dump(by_alias=True, exclude_none=True, mode="json")
    key = table.daily_key(daily.date, daily.level)
    return {"PK": key["PK"]["S"], "SK": key["SK"]["S"], **data}


StoreError = table.StoreError
