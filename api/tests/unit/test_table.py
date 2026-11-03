"""Store keys and expiry checks (data-model.md A1 to A8)."""

import datetime as dt
from decimal import Decimal

import pytest

from staysharp.store import table

DAY = dt.date(2026, 11, 20)


def test_keys_follow_the_access_patterns() -> None:
    assert table.daily_key(DAY, "senior") == {
        "PK": {"S": "DAILY#2026-11-20#senior"},
        "SK": {"S": "SET"},
    }
    assert table.question_key("abc", 2)["SK"] == {"S": "V#2"}
    assert table.play_key("p1", "2026-11-20.senior.daily")["SK"] == {
        "S": "PLAY#2026-11-20.senior.daily"
    }
    assert table.answer_key("p1", "2026-11-20.senior.daily", 3)["SK"] == {
        "S": "ANS#2026-11-20.senior.daily#3"
    }
    assert table.practice_key("p1", "x")["SK"] == {"S": "PRA#x"}
    assert table.practice_count_key("p1", DAY)["SK"] == {"S": "PRACOUNT#2026-11-20"}
    assert table.challenge_meta_key("C" * 12)["SK"] == {"S": "META"}
    assert table.challenge_result_key("C" * 12, "h")["SK"] == {"S": "R#h"}
    assert table.pool_key("senior", "spot", DAY, "q1")["SK"] == {"S": "2026-11-20#q1"}
    assert table.stock_key("starter", DAY) == {
        "PK": {"S": "STOCK#starter"},
        "SK": {"S": "2026-11-20"},
    }


def test_pool_query_reads_strictly_before_today() -> None:
    query = table.pool_query("senior", "news", DAY)
    assert query["KeyConditionExpression"] == "PK = :pk AND SK < :today"
    assert query["ExpressionAttributeValues"][":today"] == {"S": "2026-11-20"}


def test_stock_query_reads_strictly_after_today() -> None:
    assert "SK > :today" in table.stock_query("senior", DAY)["KeyConditionExpression"]


NOW = dt.datetime(2026, 11, 20, 12, 0, tzinfo=dt.UTC)


@pytest.mark.parametrize(
    ("item", "is_expired"),
    [
        ({}, False),
        ({"expiresAt": Decimal(int(NOW.timestamp()) + 1)}, False),
        ({"expiresAt": Decimal(int(NOW.timestamp()))}, True),
        ({"expiresAt": int(NOW.timestamp()) - 3600}, True),
    ],
)
def test_expired_compares_with_now(item: dict[str, object], is_expired: bool) -> None:
    assert table.expired(item, NOW) is is_expired


def test_expired_refuses_a_bad_value() -> None:
    with pytest.raises(table.StoreError):
        table.expired({"expiresAt": "soon"}, NOW)


def test_iso_ms_is_utc_with_milliseconds() -> None:
    zurich = dt.datetime(2026, 11, 20, 9, 0, 0, 123456, tzinfo=dt.timezone(dt.timedelta(hours=1)))
    assert table.iso_ms(zurich) == "2026-11-20T08:00:00.123Z"


def test_round_trip_keeps_numbers_exact() -> None:
    data = {"PK": "P#x", "score": Decimal("4.6"), "answered": {"0", "1"}}
    assert table.deserialize(table.serialize(data)) == data


def test_table_name_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TABLE_NAME", raising=False)
    with pytest.raises(table.StoreError, match="TABLE_NAME"):
        table.table_name()
