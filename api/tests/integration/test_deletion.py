"""Delete an account and all its data (T231, FR-114, FR-115, SC-104, A10)."""

from __future__ import annotations

from typing import Any

import pytest

from staysharp import aws
from staysharp.obs import player_hash
from staysharp.store import accounts, deletion, table
from tests.integration.accounts_world import NOW, SUB, A, B, items_of, put_play

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def local(monkeypatch: pytest.MonkeyPatch, table: str) -> None:  # noqa: F811
    monkeypatch.setenv("STAGE", "local")


class Users:
    """A stand-in for Cognito's AdminDeleteUser: idempotent, can be made to fail."""

    def __init__(self) -> None:
        self.deleted: list[str] = []
        self.fail = False

    def __call__(self, sub: str) -> None:
        if self.fail:
            raise RuntimeError("cognito down")
        self.deleted.append(sub)


def everything() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    start = None
    while True:
        kwargs: dict[str, Any] = {"TableName": table.table_name()}
        if start:
            kwargs["ExclusiveStartKey"] = start
        page = aws.dynamodb().scan(**kwargs)
        items += [table.deserialize(i) for i in page["Items"]]
        start = page.get("LastEvaluatedKey")
        if not start:
            return items


def account_with_history() -> None:
    accounts.adopt(SUB, A, NOW)
    put_play(A, "2026-11-18.senior.daily", extra={"challengeId": "AAAAAAAAAAAA"})
    put_play(B, "2026-11-19.senior.daily", extra={"createdChallengeId": "BBBBBBBBBBBB"})
    put = aws.dynamodb().put_item
    name = table.table_name()
    put(
        TableName=name,
        Item={
            **table.challenge_meta_key("AAAAAAAAAAAA"),
            **table.serialize({"ownerHash": "someone-else"}),
        },
    )
    put(
        TableName=name,
        Item={
            **table.challenge_result_key("AAAAAAAAAAAA", player_hash(A)),
            **table.serialize({"score": 3}),
        },
    )
    put(
        TableName=name,
        Item={
            **table.challenge_meta_key("BBBBBBBBBBBB"),
            **table.serialize({"ownerHash": player_hash(B)}),
        },
    )
    put(TableName=name, Item={**table.practice_key(A, "ATTEMPT"), **table.serialize({"qid": "q"})})
    accounts.adopt(SUB, B, NOW)  # merges B into A
    accounts.put_progress(SUB, 0, accounts.fresh_body(), NOW)


def test_delete_removes_every_item_of_the_account_and_its_players() -> None:
    account_with_history()
    users = Users()
    assert deletion.delete_account(SUB, NOW, users) is True
    assert users.deleted == [SUB]
    assert accounts.get(SUB) is None
    assert items_of(A) == {} and items_of(B) == {}
    hashes = {player_hash(A), player_hash(B)}
    for item in everything():
        text = repr(item)
        assert SUB not in text, item
        assert not any(h in text for h in hashes), item
        assert A not in text and B not in text, item


def test_challenge_results_stay_as_a_deleted_player() -> None:
    account_with_history()
    deletion.delete_account(SUB, NOW, Users())
    results = table.query_all(
        {
            "KeyConditionExpression": "PK = :pk AND begins_with(SK, :r)",
            "ExpressionAttributeValues": {":pk": {"S": "CH#AAAAAAAAAAAA"}, ":r": {"S": "R#"}},
        }
    )
    assert len(results) == 1
    assert str(results[0]["SK"]).startswith("R#deleted-")
    assert results[0]["score"] == 3
    owned = table.get(table.challenge_meta_key("BBBBBBBBBBBB"))
    assert owned is not None and owned["ownerHash"] == deletion.DELETED_OWNER


def test_a_failure_leaves_it_deleting_and_a_retry_finishes() -> None:
    account_with_history()
    users = Users()
    users.fail = True
    with pytest.raises(RuntimeError):
        deletion.delete_account(SUB, NOW, users)
    account = accounts.get(SUB)
    assert account is not None and account.state == "deleting"
    with pytest.raises(accounts.Deleting):
        accounts.adopt(SUB, A, NOW)
    users.fail = False
    assert deletion.delete_account(SUB, NOW, users) is True
    assert accounts.get(SUB) is None


def test_deleting_again_is_done_and_still_deletes_the_sign_in() -> None:
    account_with_history()
    users = Users()
    deletion.delete_account(SUB, NOW, users)
    assert deletion.delete_account(SUB, NOW, users) is True
    assert users.deleted == [SUB, SUB]


def test_marked_deleting_accounts_are_found_for_the_job() -> None:
    account_with_history()
    users = Users()
    users.fail = True
    with pytest.raises(RuntimeError):
        deletion.delete_account(SUB, NOW, users)
    assert deletion.stuck(NOW) == [(SUB, NOW)]
