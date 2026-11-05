"""Play routes against contracts/openapi.yaml, including the 409 and 503 bodies (T056).

Runs on DynamoDB Local with the fixture seed, so the responses are the real ones. Every response
is validated by the ``checked`` harness (strict schemas: an answer field leaking into a question
view fails here).
"""

from __future__ import annotations

from typing import Any

import pytest

from staysharp.store import answers
from tests.contract.conftest import Checked
from tests.events import body
from tests.integration.conftest import ddb, table  # noqa: F401 - fixtures
from tests.integration.game import Game, game  # noqa: F401 - fixture

pytestmark = pytest.mark.integration

BASE = "/api/v1/plays"


def _path(g: Game, tail: str = "") -> str:
    return f"{BASE}/{g.play_id}{tail}"


def test_start_returns_201_then_200_with_the_first_question(
    game: Game,  # noqa: F811
    checked: Checked,
) -> None:
    payload = {"level": "senior", "mode": "daily"}
    first = checked("POST", BASE, body=payload, player=game.player)
    assert first["statusCode"] == 201
    state = body(first)
    assert state["question"]["index"] == 0
    assert state["grades"] == [None] * 5
    again = checked("POST", BASE, body=payload, player=game.player)
    assert again["statusCode"] == 200


def test_get_relaxed_open_and_answer(game: Game, checked: Checked) -> None:  # noqa: F811
    game.start()
    assert checked("GET", _path(game), player=game.player)["statusCode"] == 200
    view = checked("POST", _path(game, "/questions/0/open"), player=game.player)
    assert body(view)["index"] == 0

    result = checked(
        "POST", _path(game, "/questions/0/answer"), body=game.right(0), player=game.player
    )
    answered = body(result)
    assert answered["grade"] == 1
    assert answered["correctLines"]

    relaxed = checked("POST", _path(game, "/relaxed"), player=game.player)
    assert body(relaxed)["relaxed"] is True


def test_news_answer_carries_its_source(game: Game, checked: Checked) -> None:  # noqa: F811
    game.start()
    for index in range(4):
        game.open(index)
        game.answer(index, game.right(index))
    checked("POST", _path(game, "/questions/4/open"), player=game.player)
    result = body(
        checked("POST", _path(game, "/questions/4/answer"), body=game.right(4), player=game.player)
    )
    assert result["sourceUrl"].startswith("https://")
    assert result["sourceDate"]


def test_conflict_body(game: Game, checked: Checked) -> None:  # noqa: F811
    game.start()
    game.answer(0, game.right(0))
    result = checked(
        "POST", _path(game, "/questions/0/answer"), body=game.wrong(0), player=game.player
    )
    assert result["statusCode"] == 409
    assert set(body(result)) == {"code", "recorded"}


def test_unavailable_body(
    game: Game,  # noqa: F811
    checked: Checked,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    game.start()

    def broken(*_args: Any, **_kwargs: Any) -> answers.Graded:
        raise answers.ScoringFailure("drill")

    monkeypatch.setattr(answers, "answer", broken)
    result = checked(
        "POST", _path(game, "/questions/0/answer"), body=game.right(0), player=game.player
    )
    assert result["statusCode"] == 503
    assert body(result)["code"] == "unavailable"


def test_errors_use_the_error_schema(game: Game, checked: Checked) -> None:  # noqa: F811
    missing = checked("GET", _path(game), player=game.player)
    assert missing["statusCode"] == 404
    bad = checked("POST", BASE, body={"level": "expert", "mode": "daily"}, player=game.player)
    assert bad["statusCode"] == 400
