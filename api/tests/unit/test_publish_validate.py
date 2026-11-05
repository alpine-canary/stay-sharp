"""Publish validation: every invalid batch is refused whole, with id and reason (T085, V7).

``fixtures/publish/valid/`` is a complete batch (two days per level, a sample and an unscheduled
draft). Each file in ``fixtures/publish/invalid/`` changes that batch in one place and names the
problem it must cause.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest
import yaml

from staysharp.domain.models import Question
from staysharp.publish import validate
from staysharp.publish.validate import Content, Problem
from staysharp.tools.content import to_question

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "publish"
VALID = FIXTURES / "valid"
CASES = sorted((FIXTURES / "invalid").glob("*.yaml"))


def _set(data: Any, path: list[Any], value: Any) -> None:
    for step in path[:-1]:
        data = data[step]
    data[path[-1]] = value


def _delete(data: Any, path: list[Any]) -> None:
    for step in path[:-1]:
        data = data[step]
    del data[path[-1]]


def _apply(content: Content, case: dict[str, Any]) -> Content:
    questions = [copy.deepcopy(q) for q in content.questions]
    schedules = [copy.deepcopy(s) for s in content.schedules]
    for change in case["patch"]:
        if "question" in change:
            matches = [q for q in questions if q.data["id"] == change["question"]]
            target = matches[0]
        else:
            target = next(s for s in schedules if s.data["level"] == change["schedule"])
        if change["op"] == "set":
            _set(target.data, change["path"], change["value"])
        elif change["op"] == "delete":
            _delete(target.data, change["path"])
        elif change["op"] == "copy":
            twin = copy.deepcopy(target)
            _set(twin.data, change["path"], change["value"])
            questions.append(validate.Authored(twin.data, f"{twin.path}.copy"))
        else:
            raise AssertionError(f"unknown op {change['op']}")
    return Content(questions, schedules)


def _existing(content: Content, case: dict[str, Any]) -> dict[str, Question]:
    stored: dict[str, Question] = {}
    for change in case.get("existing", []):
        original = next(q for q in content.questions if q.data["id"] == change["question"])
        authored = copy.deepcopy(original)
        _set(authored.data, change["path"], change["value"])
        stored[change["question"]] = to_question(authored.data)
    return stored


@pytest.fixture(scope="module")
def valid() -> Content:
    return validate.load(VALID)


def test_the_valid_batch_has_no_problem(valid: Content) -> None:
    assert validate.validate(valid) == []


def test_the_valid_batch_loads_every_file(valid: Content) -> None:
    assert len(valid.questions) == 22
    assert sorted(s.data["level"] for s in valid.schedules) == ["senior", "starter"]


def test_an_unscheduled_draft_is_not_a_problem(valid: Content) -> None:
    assert "sen_fail_draft" in {q.data["id"] for q in valid.questions}
    assert validate.validate(valid) == []


def test_an_unchanged_question_needs_no_change_reason(valid: Content) -> None:
    stored = {q.data["id"]: to_question(q.data) for q in valid.questions}
    assert validate.validate(valid, existing=stored) == []


@pytest.mark.parametrize("case_path", CASES, ids=[p.stem for p in CASES])
def test_each_invalid_batch_is_refused_with_id_and_reason(valid: Content, case_path: Path) -> None:
    case = yaml.safe_load(case_path.read_text(encoding="utf-8"))
    problems = validate.validate(_apply(valid, case), existing=_existing(valid, case))
    expected = case["expect"]
    matching = [p for p in problems if p.id == expected["id"] and expected["reason"] in p.reason]
    assert matching, f"expected {expected} in {problems}"


def test_every_r4_check_has_a_case() -> None:
    names = {p.stem for p in CASES}
    assert names >= {
        "wrong_deck_order",
        "wrong_level",
        "qid_on_two_dates",
        "sample_in_schedule",
        "not_daily_eligible_in_schedule",
        "line_outside_code",
        "missing_target",
        "starter_without_second_reader",
        "new_version_without_change_reason",
        "draft_in_schedule",
        "date_like_id",
        "missing_answer",
        "duplicate_id",
        "wrong_number_of_choices",
    }


def test_reasons_never_quote_question_text(valid: Content) -> None:
    """Reasons go to CI logs: they name fields and rules, never prompts, choices or answers."""
    case = yaml.safe_load((FIXTURES / "invalid" / "wrong_number_of_choices.yaml").read_text())
    broken = _apply(valid, case)
    for q in broken.questions:
        _set(q.data, ["explanation"], "")
    texts = {"one", "two", "three"} | {c for q in valid.questions for c in q.data["choices"]}
    for problem in validate.validate(broken):
        assert not any(text in problem.reason for text in texts if len(text) > 2), problem


@pytest.mark.parametrize(
    "qid",
    ["q_2026_12_01", "news_20261201", "spot_dec_12", "acr_monday", "bet_w49", "x_day3", "y_2027"],
)
def test_date_like_ids_are_refused(qid: str) -> None:
    assert validate.date_like(qid)


@pytest.mark.parametrize(
    "qid", ["sen_spot_amber", "proto_acr01", "retry_backoff", "monitor_alarm", "sta_words_bug"]
)
def test_ordinary_ids_pass(qid: str) -> None:
    assert not validate.date_like(qid)


def test_problems_are_sorted_and_unique(valid: Content) -> None:
    case = yaml.safe_load((FIXTURES / "invalid" / "duplicate_id.yaml").read_text())
    problems = validate.validate(_apply(valid, case))
    assert problems == sorted(set(problems))
    assert all(isinstance(p, Problem) for p in problems)


def test_the_packaged_schemas_match_the_contracts() -> None:
    contracts = Path(__file__).resolve().parents[3] / "specs" / "001-m1-web-app" / "contracts"
    for name in ("question.schema.json", "schedule.schema.json"):
        assert validate.schema_text(name) == (contracts / name).read_text(encoding="utf-8")
