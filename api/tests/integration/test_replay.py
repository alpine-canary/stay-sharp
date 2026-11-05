"""Replay is not an answer key (T053, C3, V13)."""

from __future__ import annotations

import datetime as dt

import pytest

from tests.events import body
from tests.integration.game import TODAY, Game, game  # noqa: F401 - fixture

pytestmark = pytest.mark.integration


def test_replay_of_today_is_refused_before_the_daily(game: Game) -> None:  # noqa: F811
    game.mode = "replay"
    refused = game.start()
    assert refused["statusCode"] == 409
    assert body(refused)["code"] == "conflict"


def test_replay_of_today_is_refused_while_the_daily_is_unfinished(game: Game) -> None:  # noqa: F811
    game.start()
    game.open(0)
    game.answer(0, game.right(0))
    replay = Game(now=game.now, mode="replay")
    assert replay.start()["statusCode"] == 409


def test_replay_after_the_daily_is_allowed_and_separate(game: Game) -> None:  # noqa: F811
    game.play_all(right=False)
    daily_before = body(game.get())

    replay = Game(now=game.now, mode="replay")
    started = replay.start()
    assert started["statusCode"] == 201
    assert body(started)["mode"] == "replay"
    for index in range(5):
        replay.open(index)
        assert replay.answer(index, game.right(index))["statusCode"] == 200

    assert body(replay.get())["score"] == 5.0
    assert body(game.get()) == daily_before


def test_yesterdays_daily_locks_its_replay_too(game: Game) -> None:  # noqa: F811
    """Yesterday's daily can still be answered today, so its replay stays locked."""
    game.mode = "replay"
    game.day = TODAY - dt.timedelta(days=1)
    assert game.start()["statusCode"] == 409


def test_an_older_day_can_be_replayed_without_its_daily(game: Game) -> None:  # noqa: F811
    game.now += dt.timedelta(days=2)
    game.mode = "replay"
    started = game.start()
    assert started["statusCode"] == 201
