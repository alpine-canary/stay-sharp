"""Offline leak check (research R4 layer 1, SC-002).

Runs the API's own view builder (``domain.views.question_view``, the only way a question leaves
the server before it is answered) over every question scheduled from today to today + ``days``
and fails if what the browser would receive carries a field outside the allowlist, the
explanation, the source link or the answer lines. Choice texts and ids are meant to be shown, so
they are not checked; which choice is correct is not visible because every choice has the same
shape. Problems name ids and fields only.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

from staysharp.domain.views import VIEW_FIELDS, question_view
from staysharp.publish import versions
from staysharp.publish.fingerprints import MIN_WORDS, SHINGLE, normalise, shingles
from staysharp.publish.validate import Content, Problem

__all__ = ["check", "question_view"]

SERVED_AT = "2026-01-01T00:00:00.000Z"
_IDS = ["AAAAAAAA", "BBBBBBBB", "CCCCCCCC", "DDDDDDDD"]


def _contains(view_words: list[str], text: str) -> bool:
    words = normalise(text)
    if len(words) < MIN_WORDS:
        return False
    size = min(SHINGLE, len(words))
    wanted = set(shingles(words, size))
    return any(s in wanted for s in shingles(view_words, size))


def check(content: Content, *, today: dt.date, days: int = 7) -> tuple[int, list[Problem]]:
    """Return how many questions were checked and the problems found."""
    last = today + dt.timedelta(days=days)
    by_id = {q.data.get("id"): q.data for q in content.questions}
    problems: list[Problem] = []
    checked = 0
    for schedule in content.schedules:
        targets: dict[str, int] = schedule.data.get("targets") or {}
        for day, qids in schedule.data.get("days", {}).items():
            if not today <= dt.date.fromisoformat(day) <= last:
                continue
            for index, qid in enumerate(qids):
                problems += _check_one(qid, by_id.get(qid), index, targets)
                checked += 1
    return checked, sorted(set(problems))


def _check_one(
    qid: str, authored: dict[str, Any] | None, index: int, targets: dict[str, int]
) -> list[Problem]:
    if authored is None:
        return [Problem(qid, "scheduled but missing")]
    stored = versions.build(authored, version=1, ids=_IDS, display=[0, 1, 2, 3])
    data = stored.model_dump(by_alias=True, exclude_none=True, mode="json")
    view = question_view(
        data, index=index, served_at=SERVED_AT, target_seconds=targets.get(stored.deck)
    )
    problems: list[Problem] = []
    extra = set(view) - set(VIEW_FIELDS)
    if extra:
        problems.append(Problem(qid, f"view carries fields outside the allowlist: {sorted(extra)}"))
    text = json.dumps(view)
    words = normalise(text)
    if _contains(words, stored.explanation):
        problems.append(Problem(qid, "the explanation reaches the view"))
    if stored.source_url and stored.source_url in text:
        problems.append(Problem(qid, "the source link reaches the view"))
    if any(key in view for key in ("answerChoiceId", "answerLines", "correctChoiceId")):
        problems.append(Problem(qid, "an answer field reaches the view"))
    return problems
