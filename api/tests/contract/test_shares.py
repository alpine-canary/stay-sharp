"""POST /shares counts a copied or shared result card (campaign 2026-11).

An aggregate count, plus one per campaign network when the visit has one. Nothing is stored and
nothing about the player is recorded; the answer is an empty 204.
"""

from __future__ import annotations

from typing import Any

import pytest

from staysharp import metrics
from tests.contract.conftest import Checked
from tests.events import PLAYER, call


@pytest.fixture
def emitted(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, Any]]:
    monkeypatch.setenv("STAGE", "local")
    seen: list[tuple[str, Any]] = []
    monkeypatch.setattr(
        metrics, "emit", lambda name, value=1, *, dimension=None: seen.append((name, dimension))
    )
    return seen


def test_a_share_is_counted(checked: Checked, emitted: list[tuple[str, Any]]) -> None:
    result = checked("POST", "/api/v1/shares", player=PLAYER)
    assert result["statusCode"] == 204
    assert result["body"] == ""
    assert emitted == [("ResultsShared", None)]


def test_a_share_from_x_is_also_counted_for_x(emitted: list[tuple[str, Any]]) -> None:
    result = call("POST", "/api/v1/shares", player=PLAYER, headers={"x-source": "x"})
    assert result["statusCode"] == 204
    assert emitted == [("ResultsShared", None), ("ResultsSharedBySource", ("Source", "x"))]


def test_an_unknown_source_counts_the_total_only(emitted: list[tuple[str, Any]]) -> None:
    call("POST", "/api/v1/shares", player=PLAYER, headers={"x-source": "myspace"})
    assert emitted == [("ResultsShared", None)]


def test_no_player_id_is_refused_and_not_counted(emitted: list[tuple[str, Any]]) -> None:
    assert call("POST", "/api/v1/shares", player=None)["statusCode"] == 400
    assert emitted == []
