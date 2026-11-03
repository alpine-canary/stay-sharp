"""The question view is the only way a question leaves the server (R1, S2, scenario V2).

The field list follows the contract's ``QuestionView`` (``index``, not the question id: the qid
is only returned by practice, next to the view).
"""

import json
from typing import Any

import pytest

from staysharp.domain import views

SECRET_VALUES = {
    "answerChoiceId": "CCCCCCCC",
    "answerLines": [7],
    "explanation": "SECRET-EXPLANATION the null check is missing",
    "sourceUrl": "https://example.com/SECRET-SOURCE",
    "sourceDate": "2026-10-30",
    "approvedBy": "SECRET-APPROVER",
    "approvedAt": "2026-10-31T10:00:00.000Z",
    "secondReader": "SECRET-READER",
    "changeReason": "SECRET-REASON",
}


def full_item() -> dict[str, Any]:
    return {
        "PK": "Q#null_check_missing",
        "SK": "V#2",
        "qid": "null_check_missing",
        "version": 2,
        "level": "senior",
        "deck": "spot",
        "prompt": "Where is the bug?",
        "code": "def f(x):\n    return x.y\n",
        "language": "python",
        "choices": [
            {"id": "AAAAAAAA", "text": "Off by one"},
            {"id": "BBBBBBBB", "text": "Wrong operator"},
            {"id": "CCCCCCCC", "text": "Missing null check", "correct": True},
            {"id": "DDDDDDDD", "text": "Race condition"},
        ],
        "dailyEligible": False,
        **SECRET_VALUES,
    }


def test_view_has_exactly_the_allowlisted_fields() -> None:
    view = views.question_view(
        full_item(), index=0, served_at="2026-11-20T08:00:00.000Z", target_seconds=60
    )
    assert set(view) == {
        "index",
        "deck",
        "prompt",
        "code",
        "language",
        "choices",
        "targetSeconds",
        "servedAt",
    }
    assert view["index"] == 0
    assert view["targetSeconds"] == 60
    assert view["servedAt"] == "2026-11-20T08:00:00.000Z"


def test_choices_carry_only_id_and_text() -> None:
    view = views.question_view(
        full_item(), index=0, served_at="2026-11-20T08:00:00.000Z", target_seconds=60
    )
    assert view["choices"] == [
        {"id": "AAAAAAAA", "text": "Off by one"},
        {"id": "BBBBBBBB", "text": "Wrong operator"},
        {"id": "CCCCCCCC", "text": "Missing null check"},
        {"id": "DDDDDDDD", "text": "Race condition"},
    ]


def test_no_secret_value_appears_anywhere_in_the_output() -> None:
    view = views.question_view(
        full_item(), index=0, served_at="2026-11-20T08:00:00.000Z", target_seconds=60
    )
    text = json.dumps(view)
    for field in SECRET_VALUES:
        assert field not in text
    for value in ("SECRET", "example.com", "2026-10-30", "correct", "PK", "null_check_missing"):
        assert value not in text


def test_relaxed_play_has_no_target() -> None:
    view = views.question_view(
        full_item(), index=3, served_at="2026-11-20T08:00:00.000Z", target_seconds=None
    )
    assert "targetSeconds" not in view


def test_question_without_code_has_no_code_fields() -> None:
    item = full_item()
    del item["code"], item["language"]
    view = views.question_view(
        item, index=1, served_at="2026-11-20T08:00:00.000Z", target_seconds=20
    )
    assert "code" not in view
    assert "language" not in view


def test_a_question_without_four_choices_is_refused() -> None:
    item = full_item()
    item["choices"] = item["choices"][:3]
    with pytest.raises(ValueError, match="4 choices"):
        views.question_view(item, index=0, served_at="2026-11-20T08:00:00.000Z", target_seconds=60)
