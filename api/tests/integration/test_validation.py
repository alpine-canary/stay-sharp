"""Invalid submissions are refused with a clear code and store nothing (T055, FR-032)."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

from staysharp.store import table
from tests.events import body, call
from tests.integration.game import TODAY, Game, game  # noqa: F401 - fixture

pytestmark = pytest.mark.integration


def _answers_stored(g: Game) -> list[dict[str, Any]]:
    return table.query_all(
        {
            "KeyConditionExpression": "PK = :pk AND begins_with(SK, :ans)",
            "ExpressionAttributeValues": {
                ":pk": {"S": f"P#{g.player}"},
                ":ans": {"S": "ANS#"},
            },
        }
    )


def _graded(g: Game) -> list[dict[str, Any]]:
    return [item for item in _answers_stored(g) if "grade" in item]


def _refused(result: dict[str, Any], status: int = 400, code: str = "invalid_request") -> None:
    assert result["statusCode"] == status, result
    assert body(result)["code"] == code


def test_question_not_in_the_set(game: Game) -> None:  # noqa: F811
    game.start()
    _refused(game.answer(5, game.right(0)))
    _refused(game.open(7))
    assert _graded(game) == []


def test_a_future_date(game: Game) -> None:  # noqa: F811
    future = Game(now=game.now, day=TODAY + dt.timedelta(days=1))
    _refused(future.start(mode="replay"))
    _refused(future.start())
    assert _answers_stored(game) == []


def test_an_unopened_question(game: Game) -> None:  # noqa: F811
    game.start()  # opens question 0 only
    game.answer(0, game.right(0))
    _refused(game.answer(1, game.right(1)))
    assert len(_graded(game)) == 1


def test_opening_ahead_of_the_first_unanswered(game: Game) -> None:  # noqa: F811
    game.start()
    _refused(game.open(2), 409, "conflict")


@pytest.mark.parametrize(
    "payload",
    [
        {"choiceId": "ZZZZZZZZ", "line": 1},
        {"choiceId": "abc"},
        {"choiceId": 12},
        {},
        {"choiceId": "ZZZZZZZZ", "extra": True},
    ],
)
def test_an_invalid_choice(game: Game, payload: dict[str, Any]) -> None:  # noqa: F811
    game.start()
    _refused(game.answer(0, payload))
    assert _graded(game) == []


def test_line_rules(game: Game) -> None:  # noqa: F811
    game.start()
    spot = game.question(0)
    lines = len((spot.code or "").splitlines())
    choice = spot.answer_choice_id
    _refused(game.answer(0, {"choiceId": choice}))
    if lines < 30:
        _refused(game.answer(0, {"choiceId": choice, "line": lines + 1}))
    _refused(game.answer(0, {"choiceId": choice, "line": 0}))
    _refused(game.answer(0, {"choiceId": choice, "line": 31}))
    assert _graded(game) == []

    game.answer(0, game.right(0))
    game.open(1)
    _refused(game.answer(1, {**game.right(1), "line": 1}))
    assert len(_graded(game)) == 1


def test_a_body_over_2_kb(game: Game) -> None:  # noqa: F811
    game.start()
    big = '{"choiceId": "' + "A" * 3000 + '"}'
    result = game.answer(0, big)
    assert result["statusCode"] == 413
    assert body(result)["code"] == "invalid_request"
    assert _graded(game) == []


@pytest.mark.parametrize(
    "player",
    [
        None,
        "",
        "not-a-uuid",
        "9F1C2B3A-4D5E-4F60-8A7B-1C2D3E4F5A6B",
        "9f1c2b3a-4d5e-1f60-8a7b-1c2d3e4f5a6b",
    ],
)
def test_a_malformed_player_id(game: Game, player: str | None) -> None:  # noqa: F811
    result = call("POST", "/api/v1/plays", body={"level": "senior", "mode": "daily"}, player=player)
    _refused(result)
    assert _answers_stored(game) == []


def test_unknown_play_and_bad_play_id(game: Game) -> None:  # noqa: F811
    _refused(game.get(), 404, "not_found")
    _refused(call("GET", "/api/v1/plays/today", player=game.player))


def test_an_unknown_body_field_on_start(game: Game) -> None:  # noqa: F811
    _refused(game.start(cheat=True))


def test_not_ready_is_a_typed_answer(game: Game) -> None:  # noqa: F811
    game.now += dt.timedelta(days=10)
    game.day = TODAY + dt.timedelta(days=10)
    result = game.start()
    assert result["statusCode"] == 404
    assert body(result)["code"] == "not_ready"
    assert "not ready yet" in body(result)["message"]


def test_a_daily_closes_after_the_next_day(game: Game) -> None:  # noqa: F811
    game.start()
    game.now += dt.timedelta(days=1)
    game.answer(0, game.right(0))  # D+1: still allowed
    game.open(1)
    game.now += dt.timedelta(days=1)
    _refused(game.answer(1, game.right(1)))
    _refused(game.open(1))
