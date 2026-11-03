"""Sample content is valid and can never be scheduled (FR-024b, FR-024c, T037)."""

import json
from collections import Counter
from pathlib import Path
from typing import Any

import jsonschema
import pytest
import yaml

from staysharp.domain.models import DECKS, code_line_count
from staysharp.tools.content import question_files, schedule_files, to_question

ROOT = Path(__file__).resolve().parents[3]
SAMPLES = ROOT / "content" / "samples"
CONTRACTS = ROOT / "specs" / "001-m1-web-app" / "contracts"
QUESTION_SCHEMA = json.loads((CONTRACTS / "question.schema.json").read_text())
SCHEDULE_SCHEMA = json.loads((CONTRACTS / "schedule.schema.json").read_text())

FILES = list(question_files(SAMPLES))


def load(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data


def test_there_is_one_sample_per_deck_for_both_levels() -> None:
    decks = {(q["level"], q["deck"]) for q in map(load, FILES)}
    for level, level_decks in DECKS.items():
        for deck in level_decks:
            assert (level, deck) in decks


def test_prototype_has_14_days_of_5_questions() -> None:
    (schedule,) = list(schedule_files(SAMPLES))
    days = load(schedule)["days"]
    assert len(days) == 14
    assert all(len(qids) == 5 for qids in days.values())


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_sample_matches_the_schema_and_is_never_schedulable(path: Path) -> None:
    data = load(path)
    jsonschema.validate(data, QUESTION_SCHEMA, format_checker=jsonschema.FormatChecker())
    assert data["id"] == path.stem
    assert data["sample"] is True
    assert data["daily_eligible"] is False
    lines = data["answer"].get("lines", [])
    assert all(1 <= n <= code_line_count(data.get("code")) for n in lines)


@pytest.mark.parametrize("path", list(schedule_files(SAMPLES)), ids=lambda p: p.parent.name)
def test_schedule_matches_the_schema_and_names_known_questions(path: Path) -> None:
    data = load(path)
    jsonschema.validate(data, SCHEDULE_SCHEMA)
    known = {p.stem for p in FILES}
    for qids in data["days"].values():
        assert set(qids) <= known


def test_conversion_is_deterministic_and_keeps_the_answer() -> None:
    for path in FILES:
        authored = load(path)
        first, second = to_question(authored), to_question(authored)
        assert first == second
        right_text = authored["choices"][authored["answer"]["choice"]]
        (right,) = [c for c in first.choices if c.id == first.answer_choice_id]
        assert right.text == right_text


def test_shuffle_does_not_keep_the_right_answer_in_one_place() -> None:
    positions = Counter(
        [c.id for c in q.choices].index(q.answer_choice_id)
        for q in (to_question(load(p)) for p in FILES)
    )
    # 80 questions over 4 positions: no position may hold more than half of them.
    assert max(positions.values()) <= len(FILES) / 2
    assert len(positions) == 4
