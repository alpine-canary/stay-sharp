"""Monthly return rate (task T117, SC-010): aggregate counts only, read-only."""

from __future__ import annotations

from typing import Any

import pytest

from staysharp import aws
from staysharp.store import table as store
from staysharp.tools import return_rate
from tests.integration.conftest import ddb, table  # noqa: F401 - fixtures

pytestmark = pytest.mark.integration

A = "11111111-1111-4111-8111-111111111111"
B = "22222222-2222-4222-8222-222222222222"
C = "33333333-3333-4333-8333-333333333333"


def put(item: dict[str, Any]) -> None:
    aws.dynamodb().put_item(TableName=store.table_name(), Item=store.serialize(item))


def play(player: str, day: str, *, mode: str = "daily", answered: int = 5) -> None:
    item: dict[str, Any] = {
        "PK": f"P#{player}",
        "SK": f"PLAY#{day}.senior.{mode}",
        "date": day,
        "level": "senior",
        "mode": mode,
    }
    if answered:
        item["answered"] = {str(i) for i in range(answered)}
    put(item)


def challenge(cid: str, created: str, results: int) -> None:
    put({"PK": f"CH#{cid}", "SK": "META", "createdAt": created, "results": results})


def test_counts_returning_players_and_challenges(
    table: str,  # noqa: F811
    capsys: pytest.CaptureFixture[str],
) -> None:
    play(A, "2026-11-02")
    play(A, "2026-11-05")
    play(A, "2026-11-05", mode="replay")
    play(B, "2026-11-03")
    play(B, "2026-11-04", answered=3)  # not finished: not a second day
    play(C, "2026-10-30")  # another month
    play(C, "2026-11-01", mode="replay")  # a replay is not a daily
    challenge("AAAAAAAAAAAA", "2026-11-03T10:00:00.000Z", 2)
    challenge("BBBBBBBBBBBB", "2026-11-04T10:00:00.000Z", 0)
    challenge("CCCCCCCCCCCC", "2026-10-31T10:00:00.000Z", 1)

    counts = return_rate.count("2026-11")
    assert counts == {
        "month": "2026-11",
        "players": 2,
        "returning": 1,
        "challenges": 2,
        "challengesFinished": 1,
    }

    assert return_rate.main(["--month", "2026-11", "--stage", "local"]) == 0
    out = capsys.readouterr().out
    assert "returning 1 of 2 players" in out
    for player in (A, B, C):
        assert player not in out


def test_refuses_a_bad_month(table: str) -> None:  # noqa: F811
    assert return_rate.main(["--month", "November", "--stage", "local"]) == 2
