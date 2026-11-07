"""Writes that race "Delete my account" (T249 review): nothing may survive or revive it."""

from __future__ import annotations

import datetime as dt

import pytest

from staysharp.store import accounts, deletion, merge, table
from tests.integration.accounts_world import NOW, SUB, A, B, items_of, put_play

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def local(monkeypatch: pytest.MonkeyPatch, table: str) -> None:  # noqa: F811
    monkeypatch.setenv("STAGE", "local")


def broken(_: str) -> None:
    raise RuntimeError("cognito down")


def marked_deleting() -> None:
    """An account whose deletion has started but not finished."""
    accounts.adopt(SUB, A, NOW)
    with pytest.raises(RuntimeError):
        deletion.delete_account(SUB, NOW, broken)


def test_activity_never_pulls_an_account_out_of_the_deletion_queue() -> None:
    marked_deleting()
    accounts.touch(SUB, NOW + dt.timedelta(days=40), known="2026-11")
    item = table.get(accounts.account_key(SUB), consistent=True)
    assert item is not None
    assert item["lastActiveMonth"] == deletion.DELETING_MONTH


def test_no_progress_copy_is_written_once_deletion_started() -> None:
    marked_deleting()
    with pytest.raises(accounts.Deleting):
        accounts.put_progress(SUB, 0, accounts.fresh_body(), NOW)
    assert table.get(accounts.progress_key(SUB), consistent=True) is None


def test_a_merge_racing_a_deletion_says_deleting_and_leaves_nothing() -> None:
    accounts.adopt(SUB, A, NOW)
    put_play(B, "2026-11-19.senior.daily")
    real_merge = merge.merge

    def merge_then_delete_starts(primary: str, other: str, now: dt.datetime) -> object:
        result = real_merge(primary, other, now)
        with pytest.raises(RuntimeError):
            deletion.delete_account(SUB, NOW, broken)  # starts while the merge was running
        return result

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(merge, "merge", merge_then_delete_starts)
        with pytest.raises(accounts.Deleting):
            accounts.adopt(SUB, B, NOW)
    assert items_of(A) == {}
    deletion.delete_account(SUB, NOW, lambda _s: None)
    assert items_of(A) == {}


def test_a_deleted_account_is_not_created_again_by_an_old_token() -> None:
    accounts.adopt(SUB, A, NOW)
    deletion.delete_account(SUB, NOW, lambda _s: None)
    assert accounts.get(SUB) is None
    # Another device still holds an access token (valid up to an hour) and opens /account.
    with pytest.raises(accounts.Deleting):
        accounts.adopt(SUB, B, NOW + dt.timedelta(minutes=30))
    assert accounts.get(SUB) is None


def test_two_deletions_at_once_count_each_challenge_result_once() -> None:
    from staysharp.obs import player_hash

    hashed = player_hash(A)
    key = table.challenge_result_key("CHALLENGE01", hashed)
    from staysharp import aws

    aws.dynamodb().put_item(
        TableName=table.table_name(), Item={**key, **table.serialize({"score": 3})}
    )
    found = table.get(key, consistent=True)
    assert found is not None
    real_get = table.get
    # Both deletions read the result before either moves it.
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(table, "get", lambda k, consistent=False: found)
        deletion._as_deleted_player("CHALLENGE01", hashed)  # noqa: SLF001
        deletion._as_deleted_player("CHALLENGE01", hashed)  # noqa: SLF001
    del real_get
    rows = [k for k in items_of_challenge("CHALLENGE01") if k.startswith("R#")]
    assert len(rows) == 1


def items_of_challenge(challenge_id: str) -> list[str]:
    from staysharp import aws

    found = aws.dynamodb().query(
        TableName=table.table_name(),
        KeyConditionExpression="PK = :pk",
        ExpressionAttributeValues={":pk": {"S": f"CH#{challenge_id}"}},
    )["Items"]
    return [str(i["SK"]["S"]) for i in found]
