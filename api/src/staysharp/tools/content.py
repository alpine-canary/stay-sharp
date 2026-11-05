"""Authoring format (``contracts/question.schema.json``) to stored ``Question``.

Choice ids are 8 base32 characters and the choice order is shuffled once. For samples and
fixtures both come from a hash of the qid, so seeding twice gives the same items; real publish
(task T086) draws random ids at the first publish and keeps them.
"""

from __future__ import annotations

import base64
import hashlib
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from staysharp.domain.models import Question

SCHEDULE_FILE = "schedule.yaml"


def _digest(*parts: str) -> bytes:
    return hashlib.sha256("\x1f".join(parts).encode()).digest()


def fixture_choice_id(qid: str, position: int) -> str:
    return base64.b32encode(_digest("choice", qid, str(position))[:5]).decode()


def to_question(authored: Mapping[str, Any], *, version: int = 1) -> Question:
    """Build the stored question from an authored one (deterministic ids and order)."""
    qid = str(authored["id"])
    texts: list[str] = list(authored["choices"])
    choices = [{"id": fixture_choice_id(qid, i), "text": t} for i, t in enumerate(texts)]
    answer_id = choices[int(authored["answer"]["choice"])]["id"]
    shuffled = sorted(choices, key=lambda c: _digest("order", qid, c["id"]))
    source = authored.get("source") or {}
    data: dict[str, Any] = {
        "qid": qid,
        "version": version,
        "level": authored["level"],
        "deck": authored["deck"],
        "prompt": authored["prompt"],
        "code": authored.get("code"),
        "language": authored.get("language"),
        "choices": shuffled,
        "choiceOrder": [c["id"] for c in choices],
        "answerChoiceId": answer_id,
        "answerLines": list(authored["answer"].get("lines", [])),
        "explanation": authored["explanation"],
        "sourceUrl": source.get("url"),
        "sourceDate": source.get("date"),
        "dailyEligible": bool(authored.get("daily_eligible", True)),
        "approvedBy": authored.get("approved_by"),
        "approvedAt": authored.get("approved_at"),
        "secondReader": authored.get("second_reader"),
        "changeReason": authored.get("change_reason"),
    }
    return Question.model_validate({k: v for k, v in data.items() if v is not None})


def question_files(root: Path) -> Iterator[Path]:
    for path in sorted(root.rglob("*.yaml")):
        if path.name != SCHEDULE_FILE:
            yield path


def schedule_files(root: Path) -> Iterator[Path]:
    yield from sorted(root.rglob(SCHEDULE_FILE))
