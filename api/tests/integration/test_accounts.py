"""Account creation and adoption (T219, US1, FR-109, FR-110)."""

from __future__ import annotations

import pytest

from staysharp.store import accounts
from tests.integration.accounts_world import NOW, SUB, A, B, put_play

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def local(monkeypatch: pytest.MonkeyPatch, table: str) -> None:
    monkeypatch.setenv("STAGE", "local")


def test_first_adopt_creates_the_account_with_this_browser_as_primary() -> None:
    result = accounts.adopt(SUB, A, NOW)
    assert result == accounts.Adopted(primary_player=A, created=True, plays=0, replays=0)
    account = accounts.get(SUB)
    assert account is not None
    assert account.primary_player == A
    assert account.state == "active"
    assert account.last_active_month == "2026-11"
    assert accounts.linked_sub(A) == SUB


def test_second_adopt_from_the_same_browser_changes_nothing() -> None:
    accounts.adopt(SUB, A, NOW)
    again = accounts.adopt(SUB, A, NOW)
    assert again == accounts.Adopted(primary_player=A, created=False, plays=0, replays=0)


def test_another_browser_merges_and_switches_to_the_primary_id() -> None:
    accounts.adopt(SUB, A, NOW)
    put_play(B, "2026-11-19.senior.daily")
    result = accounts.adopt(SUB, B, NOW)
    assert result.primary_player == A
    assert (result.created, result.plays, result.replays) == (False, 1, 0)
    assert accounts.linked_sub(B) == SUB
    # Repeated: the stored result, no new merge.
    assert accounts.adopt(SUB, B, NOW) == result


def test_a_browser_of_another_account_is_refused() -> None:
    accounts.adopt(SUB, A, NOW)
    accounts.adopt("sub-other", B, NOW)
    with pytest.raises(accounts.OtherAccount):
        accounts.adopt(SUB, B, NOW)


def test_a_deleting_account_refuses() -> None:
    from staysharp import aws
    from staysharp.store import table

    accounts.adopt(SUB, A, NOW)
    aws.dynamodb().update_item(
        TableName=table.table_name(),
        Key=accounts.account_key(SUB),
        UpdateExpression="SET #s = :d",
        ExpressionAttributeNames={"#s": "state"},
        ExpressionAttributeValues={":d": {"S": "deleting"}},
    )
    with pytest.raises(accounts.Deleting):
        accounts.adopt(SUB, B, NOW)
