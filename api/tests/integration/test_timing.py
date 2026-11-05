"""Server-side time, speed bonus and relaxed mode (T052, FR-005a to FR-005c, V4)."""

from __future__ import annotations

import pytest

from tests.events import body
from tests.integration.game import Game, game  # noqa: F401 - fixture

pytestmark = pytest.mark.integration


def _target(g: Game, index: int) -> int:
    view = body(g.open(index))
    return int(view["targetSeconds"])


def test_bonus_only_for_a_right_answer_within_target(game: Game) -> None:  # noqa: F811
    game.start()
    target = _target(game, 0)
    game.later(target - 1)
    right_fast = body(game.answer(0, game.right(0)))
    assert (right_fast["grade"], right_fast["bonus"]) == (1, 0.2)
    assert right_fast["elapsedMs"] == (target - 1) * 1000

    target = _target(game, 1)
    game.later(target + 1)
    right_slow = body(game.answer(1, game.right(1)))
    assert (right_slow["grade"], right_slow["bonus"]) == (1, 0)

    _target(game, 2)
    game.later(4)
    wrong_fast = body(game.answer(2, game.wrong(2)))
    assert (wrong_fast["grade"], wrong_fast["bonus"]) == (0, 0)


def test_exactly_on_target_still_earns_the_bonus(game: Game) -> None:  # noqa: F811
    game.start()
    target = _target(game, 0)
    game.later(target)
    assert body(game.answer(0, game.right(0)))["bonus"] == 0.2


def test_relaxed_mid_play_stops_bonuses_from_that_question_on(game: Game) -> None:  # noqa: F811
    game.start()
    game.open(0)
    game.later(5)
    assert body(game.answer(0, game.right(0)))["bonus"] == 0.2

    game.open(1)
    state = body(game.relax())
    assert state["relaxed"] is True
    game.later(5)
    assert body(game.answer(1, game.right(1)))["bonus"] == 0

    view = body(game.open(2))
    assert "targetSeconds" not in view
    game.later(5)
    assert body(game.answer(2, game.right(2)))["bonus"] == 0

    final = body(game.get())
    assert final["bonus"] == pytest.approx(0.2)
    assert final["relaxed"] is True


def test_relaxed_is_one_way(game: Game) -> None:  # noqa: F811
    game.start()
    assert body(game.relax())["relaxed"] is True
    assert body(game.relax())["relaxed"] is True
    assert body(game.start(relaxed=False))["relaxed"] is True


def test_relaxed_from_the_start_hides_the_target(game: Game) -> None:  # noqa: F811
    started = body(game.start(relaxed=True))
    assert started["relaxed"] is True
    assert "targetSeconds" not in started["question"]


def test_reopening_does_not_reset_served_at(game: Game) -> None:  # noqa: F811
    game.start()
    first = body(game.open(0))
    game.later(30)
    again = body(game.open(0))
    assert again["servedAt"] == first["servedAt"]
    game.later(5)
    assert body(game.answer(0, game.right(0)))["elapsedMs"] == 35_000


def test_start_twice_serves_the_first_question_once(game: Game) -> None:  # noqa: F811
    first = body(game.start())
    game.later(20)
    resumed = game.start()
    assert resumed["statusCode"] == 200
    assert body(resumed)["question"]["servedAt"] == first["question"]["servedAt"]
