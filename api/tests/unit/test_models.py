"""Strict models: content rules, set order, request bodies, player id (T025)."""

from typing import Any

import pytest
from pydantic import ValidationError

from staysharp.domain import models


def question(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "qid": "null_check_missing",
        "version": 1,
        "level": "senior",
        "deck": "spot",
        "prompt": "Where is the bug?",
        "code": "a = 1\nb = None\nprint(b.x)\n",
        "language": "python",
        "choices": [
            {"id": "AAAAAAAA", "text": "One"},
            {"id": "BBBBBBBB", "text": "Two"},
            {"id": "CCCCCCCC", "text": "Three"},
            {"id": "DDDDDDDD", "text": "Four"},
        ],
        "answerChoiceId": "CCCCCCCC",
        "answerLines": [3],
        "explanation": "b is None.",
        "dailyEligible": False,
    }
    base.update(overrides)
    return base


def test_valid_question() -> None:
    q = models.Question.model_validate(question())
    assert q.answer_lines == [3]


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"deck": "logic"}, "not a senior deck"),
        ({"answerChoiceId": "EEEEEEEE"}, "one of the choices"),
        ({"answerLines": [4]}, "within the code"),
        ({"answerLines": []}, "needs code and answer_lines"),
        ({"version": 2}, "change reason"),
        ({"qid": "Bad-Id"}, "pattern"),
        ({"surprise": 1}, "Extra inputs"),
        ({"deck": "news", "answerLines": []}, "source_url"),
    ],
)
def test_question_rules(overrides: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        models.Question.model_validate(question(**overrides))


def test_starter_daily_question_needs_a_second_reader() -> None:
    data = question(
        level="starter",
        deck="words",
        code=None,
        language=None,
        answerLines=[],
        dailyEligible=True,
    )
    with pytest.raises(ValidationError, match="second reader"):
        models.Question.model_validate(data)
    assert models.Question.model_validate({**data, "secondReader": "a reader"})


def daily_set(decks: list[str]) -> dict[str, Any]:
    return {
        "date": "2026-11-20",
        "level": "senior",
        "gameNumber": 5,
        "items": [
            {"index": i, "deck": d, "qid": f"q_{i}", "version": 1, "targetSeconds": 30}
            for i, d in enumerate(decks)
        ],
    }


def test_daily_set_follows_the_deck_order() -> None:
    ok = models.DailySet.model_validate(daily_set(["spot", "better", "fail", "acronym", "news"]))
    assert ok.items[4].deck == "news"
    with pytest.raises(ValidationError, match="order"):
        models.DailySet.model_validate(daily_set(["better", "spot", "fail", "acronym", "news"]))


def test_answer_request_is_strict() -> None:
    assert models.AnswerRequest.model_validate({"choiceId": "AAAAAAAA", "line": 3}).line == 3
    for bad in (
        {"choiceId": "aaaaaaaa"},
        {"choiceId": "AAAAAAAA", "line": 31},
        {"choiceId": "AAAAAAAA", "x": 1},
    ):
        with pytest.raises(ValidationError):
            models.AnswerRequest.model_validate(bad)


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "not-a-uuid",
        "123e4567-e89b-12d3-a456-426614174000",  # version 1
        "9F1C2B3A-4D5E-4F60-8A7B-1C2D3E4F5A6B",  # upper case
        " 9f1c2b3a-4d5e-4f60-8a7b-1c2d3e4f5a6b",
    ],
)
def test_player_id_must_be_a_uuid4(value: str | None) -> None:
    with pytest.raises(ValueError, match="UUIDv4"):
        models.parse_player_id(value)


def test_player_id_accepts_a_uuid4() -> None:
    assert models.parse_player_id("9f1c2b3a-4d5e-4f60-8a7b-1c2d3e4f5a6b").version == 4


def test_responses_serialize_in_camel_case_without_empty_fields() -> None:
    result = models.AnswerResult(
        grade=1,
        bonus=0.2,
        elapsed_ms=1200,
        correct_choice_id="AAAAAAAA",
        explanation="x",
        duplicate=False,
    )
    assert result.model_dump(by_alias=True, exclude_none=True, mode="json") == {
        "grade": 1,
        "bonus": 0.2,
        "elapsedMs": 1200,
        "correctChoiceId": "AAAAAAAA",
        "explanation": "x",
        "duplicate": False,
    }
