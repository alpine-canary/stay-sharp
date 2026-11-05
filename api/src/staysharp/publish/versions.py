"""Authored question to stored version (data-model.md, FR-027).

Version 1 gets 4 random choice ids and a display order at its first publish (``apply`` draws
them). Every later version keeps those ids and that display order, so a player who saw version 1
and a player who sees version 2 talk about the same choice ids. A version is only written when
what a player sees or is graded on changes; approval metadata alone is not a new version.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from typing import Any

from staysharp.domain.models import Question

# What a player sees or is graded on. A change to any of these is a new version.
CONTENT_FIELDS = (
    "level",
    "deck",
    "prompt",
    "code",
    "language",
    "choices",
    "answer_choice_id",
    "answer_lines",
    "explanation",
    "source_url",
    "source_date",
    "daily_eligible",
)


class VersionError(ValueError):
    """The stored history does not allow a new version (no choice order, level or deck moved)."""


def build(
    authored: Mapping[str, Any],
    *,
    version: int,
    ids: Sequence[str],
    display: Sequence[int],
    published_at: dt.datetime | None = None,
) -> Question:
    """``ids[i]`` is the id of authored choice ``i``; ``display`` lists authored indexes in the
    order the player sees them."""
    texts: list[str] = list(authored["choices"])
    if len(ids) != len(texts) or sorted(display) != list(range(len(texts))):
        raise VersionError("choice ids and display order must cover the 4 choices")
    source = authored.get("source") or {}
    data: dict[str, Any] = {
        "qid": authored["id"],
        "version": version,
        "level": authored["level"],
        "deck": authored["deck"],
        "prompt": authored["prompt"],
        "code": authored.get("code"),
        "language": authored.get("language"),
        "choices": [{"id": ids[i], "text": texts[i]} for i in display],
        "choiceOrder": list(ids),
        "answerChoiceId": ids[int(authored["answer"]["choice"])],
        "answerLines": list(authored["answer"].get("lines", [])),
        "explanation": authored["explanation"],
        "sourceUrl": source.get("url"),
        "sourceDate": source.get("date"),
        "dailyEligible": bool(authored.get("daily_eligible", True)),
        "approvedBy": authored.get("approved_by"),
        "approvedAt": authored.get("approved_at"),
        "secondReader": authored.get("second_reader"),
        "changeReason": authored.get("change_reason") if version > 1 else None,
        "publishedAt": published_at,
    }
    return Question.model_validate({k: v for k, v in data.items() if v is not None})


def same_content(a: Question, b: Question) -> bool:
    return all(getattr(a, name) == getattr(b, name) for name in CONTENT_FIELDS)


def next_version(
    authored: Mapping[str, Any], latest: Question, *, published_at: dt.datetime | None = None
) -> Question | None:
    """The next version if the authored question changed what players see, else ``None``."""
    if authored["level"] != latest.level or authored["deck"] != latest.deck:
        raise VersionError("level and deck cannot change after the first publish")
    if latest.choice_order is None:
        raise VersionError("the stored version has no choice order")
    order = list(latest.choice_order)
    display = [order.index(choice.id) for choice in latest.choices]
    candidate = build(
        {**authored, "change_reason": authored.get("change_reason") or "pending check"},
        version=latest.version + 1,
        ids=order,
        display=display,
        published_at=published_at,
    )
    if same_content(candidate, latest):
        return None
    return candidate.model_copy(update={"change_reason": authored.get("change_reason")})
