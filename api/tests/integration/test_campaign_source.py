"""Campaign source (2026-11): plays and challenges are also counted per network.

The site sends ``X-Source`` (from ``utm_source``) when the visit came from a campaign link. The
API adds a ``<Metric>BySource`` count with the ``Source`` dimension: an aggregate, no player id.
Unknown values are ignored, so a made-up header changes nothing.
"""

from __future__ import annotations

from typing import Any

import pytest

from staysharp import metrics
from tests.events import body, call
from tests.integration.conftest import ddb, table  # noqa: F401 - fixtures
from tests.integration.game import Game, game  # noqa: F401 - fixture

pytestmark = pytest.mark.integration

COLLEAGUE = "2b7e1516-28ae-4d2a-a6d2-abf7158809cf"


@pytest.fixture
def emitted(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, Any]]:
    seen: list[tuple[str, Any]] = []
    real = metrics.emit

    def spy(name: str, value: float = 1, *, dimension: tuple[str, str] | None = None) -> None:
        seen.append((name, dimension))
        real(name, value, dimension=dimension)

    monkeypatch.setattr(metrics, "emit", spy)
    return seen


def by_source(seen: list[tuple[str, Any]]) -> list[tuple[str, str]]:
    return [(name, dim[1]) for name, dim in seen if name.endswith("BySource")]


def test_a_linkedin_play_is_counted_for_linkedin(
    game: Game,  # noqa: F811
    emitted: list[tuple[str, Any]],
) -> None:
    game.source = "linkedin"
    game.play_all()
    assert by_source(emitted) == [
        ("PlaysStartedBySource", "linkedin"),
        ("PlaysFinishedBySource", "linkedin"),
    ]
    assert ("PlaysStarted", None) in emitted
    assert ("PlaysFinished", None) in emitted


@pytest.mark.parametrize("source", [None, "facebook", "LinkedIn"])
def test_no_or_unknown_source_counts_the_total_only(
    game: Game,  # noqa: F811
    emitted: list[tuple[str, Any]],
    source: str | None,
) -> None:
    game.source = source
    game.play_all()
    assert by_source(emitted) == []
    assert ("PlaysFinished", None) in emitted


def test_challenges_are_counted_per_source(
    game: Game,  # noqa: F811
    emitted: list[tuple[str, Any]],
) -> None:
    game.play_all()
    created = call(
        "POST",
        "/api/v1/challenges",
        body={"playId": game.play_id},
        player=game.player,
        headers={"x-source": "x"},
    )
    assert created["statusCode"] == 200, created
    challenge_id = body(created)["challengeId"]

    colleague = Game(now=game.now, player=COLLEAGUE, source="hn")
    opened = call(
        "GET", f"/api/v1/challenges/{challenge_id}", player=COLLEAGUE, headers=colleague.headers
    )
    assert opened["statusCode"] == 200, opened
    assert colleague.start(challengeId=challenge_id)["statusCode"] == 201
    for index in range(5):
        colleague.open(index)
        colleague.later(3)
        assert colleague.answer(index, colleague.wrong(index))["statusCode"] == 200

    assert by_source(emitted) == [
        ("ChallengesCreatedBySource", "x"),
        ("ChallengesOpenedBySource", "hn"),
        ("PlaysStartedBySource", "hn"),
        ("ChallengesFinishedBySource", "hn"),
        ("PlaysFinishedBySource", "hn"),
    ]
