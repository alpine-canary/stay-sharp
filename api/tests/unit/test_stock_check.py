"""Stock check: future days with a complete set, per level (T092, FR-026, R11, W8)."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

from staysharp.handlers import stock_check

TODAY = dt.date(2026, 12, 1)
NOON = dt.datetime(2026, 12, 1, 11, 0, tzinfo=dt.UTC)


def days(*offsets: int) -> list[str]:
    return [(TODAY + dt.timedelta(days=n)).isoformat() for n in offsets]


def test_counts_days_in_a_row_from_tomorrow() -> None:
    assert stock_check.days_ahead(days(1, 2, 3), TODAY) == 3
    assert stock_check.days_ahead([], TODAY) == 0


def test_a_gap_ends_the_count() -> None:
    """Ten sets next month do not help if tomorrow is missing."""
    assert stock_check.days_ahead(days(2, 3, 4, 5, 6, 7, 8, 9), TODAY) == 0
    assert stock_check.days_ahead(days(1, 2, 4, 5), TODAY) == 2


def test_today_and_the_past_never_count() -> None:
    assert stock_check.days_ahead(days(-1, 0, 1), TODAY) == 1


class Recorder:
    def __init__(self) -> None:
        self.emitted: list[tuple[str, float, tuple[str, str] | None]] = []

    def __call__(
        self, name: str, value: float = 1, *, dimension: tuple[str, str] | None = None
    ) -> None:
        self.emitted.append((name, value, dimension))


def test_the_handler_emits_one_value_per_level(monkeypatch: pytest.MonkeyPatch) -> None:
    stored = {"senior": days(1, 2, 3, 4, 5, 6, 7, 8), "starter": days(1, 2)}
    queries: list[dict[str, Any]] = []

    def query_all(query: dict[str, Any], **_: Any) -> list[dict[str, Any]]:
        queries.append(query)
        level = query["ExpressionAttributeValues"][":pk"]["S"].removeprefix("STOCK#")
        return [{"PK": f"STOCK#{level}", "SK": d} for d in stored[level]]

    recorder = Recorder()
    monkeypatch.setattr(stock_check.table, "query_all", query_all)
    monkeypatch.setattr(stock_check, "emit", recorder)
    monkeypatch.setattr(stock_check.clock, "now", lambda: NOON)
    monkeypatch.setenv("STAGE", "dev")

    result = stock_check.run()

    assert result == {"senior": 8, "starter": 2}
    assert recorder.emitted == [
        ("StockDaysAhead", 8, ("Level", "senior")),
        ("StockDaysAhead", 2, ("Level", "starter")),
    ]
    # Only STOCK# keys, strictly after today (the role allows nothing else).
    assert all(q["ExpressionAttributeValues"][":today"]["S"] == "2026-12-01" for q in queries)


def test_a_store_error_is_raised_not_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(*_: Any, **__: Any) -> list[dict[str, Any]]:
        raise stock_check.table.StoreError("query returned no item list")

    monkeypatch.setattr(stock_check.table, "query_all", broken)
    monkeypatch.setattr(stock_check, "emit", Recorder())
    with pytest.raises(stock_check.table.StoreError):
        stock_check.run()
