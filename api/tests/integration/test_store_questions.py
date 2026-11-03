"""Daily sets and questions read back from DynamoDB Local after a fixture seed (T035, T036)."""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

import pytest

from staysharp.store import questions, table
from staysharp.tools import seed

if TYPE_CHECKING:
    from mypy_boto3_dynamodb import DynamoDBClient

pytestmark = pytest.mark.integration

TODAY = dt.date(2026, 11, 20)


@pytest.fixture
def seeded(table: str) -> str:
    seed.seed(seed.SAMPLES, today=TODAY, days=2, launch=TODAY - dt.timedelta(days=1))
    return table


def test_daily_set_and_its_questions(seeded: str) -> None:
    daily = questions.daily_set(TODAY, "senior")
    assert not isinstance(daily, questions.NotReady)
    assert daily.game_number == 2
    assert [item.deck for item in daily.items] == ["spot", "better", "fail", "acronym", "news"]
    first = questions.question(daily.items[0].qid, daily.items[0].version)
    assert first.deck == "spot"
    assert first.answer_lines


def test_missing_set_is_not_ready_not_an_error(seeded: str) -> None:
    later = TODAY + dt.timedelta(days=30)
    assert questions.daily_set(later, "starter") == questions.NotReady(later, "starter")


def test_missing_question_is_a_store_error(seeded: str) -> None:
    with pytest.raises(table.StoreError, match="missing"):
        questions.question("no_such_question", 1)


def test_malformed_set_is_a_store_error(seeded: str, ddb: DynamoDBClient) -> None:
    key = table.daily_key(TODAY, "starter")
    ddb.put_item(TableName=seeded, Item={**key, "date": {"S": "2026-11-20"}})
    with pytest.raises(table.StoreError, match="malformed"):
        questions.daily_set(TODAY, "starter")


def test_pool_holds_past_prototype_days_only(seeded: str) -> None:
    pool = table.query_all(table.pool_query("senior", "news", dt.date(2026, 10, 25)))
    assert [item["SK"] for item in pool] == ["2026-10-23#proto_news01", "2026-10-24#proto_news02"]


def test_stock_counts_days_after_today(seeded: str) -> None:
    stock = table.query_all(table.stock_query("senior", TODAY))
    assert [item["SK"] for item in stock] == ["2026-11-21", "2026-11-22"]
