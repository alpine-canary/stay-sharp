"""Copy a restored table back into the live one (task T118, research R17).

Puts every item of the restored snapshot into the live table: items lost or damaged since the
restore point come back; items written after it and absent from the snapshot stay. Dry run by
default; prints counts only.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest

from staysharp import aws
from staysharp.tools import restore_copy
from tests.integration.conftest import ddb  # noqa: F401 - fixture

pytestmark = pytest.mark.integration


def make(name: str) -> None:
    aws.dynamodb().create_table(
        TableName=name,
        BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
        ],
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
    )


@pytest.fixture
def tables(ddb: object) -> Iterator[tuple[str, str]]:  # noqa: F811
    live, snapshot = (f"staysharp-test-{uuid.uuid4().hex[:8]}" for _ in range(2))
    make(live)
    make(snapshot)
    yield live, snapshot
    for name in (live, snapshot):
        aws.dynamodb().delete_table(TableName=name)


def put(name: str, pk: str, sk: str, value: str) -> None:
    aws.dynamodb().put_item(
        TableName=name, Item={"PK": {"S": pk}, "SK": {"S": sk}, "v": {"S": value}}
    )


def value(name: str, pk: str, sk: str) -> str | None:
    item = aws.dynamodb().get_item(TableName=name, Key={"PK": {"S": pk}, "SK": {"S": sk}})
    return item.get("Item", {}).get("v", {}).get("S")


def test_dry_run_writes_nothing_then_copy_restores_and_keeps_newer(
    tables: tuple[str, str], capsys: pytest.CaptureFixture[str]
) -> None:
    live, snapshot = tables
    for i in range(30):
        put(snapshot, f"P#{i}", "PLAY#x", "good")
    put(live, "P#0", "PLAY#x", "damaged")
    put(live, "P#new", "PLAY#y", "newer")

    assert restore_copy.main(["--source", snapshot, "--target", live]) == 0
    assert value(live, "P#0", "PLAY#x") == "damaged"
    assert "dry run: 30 items would be written" in capsys.readouterr().out

    assert restore_copy.main(["--source", snapshot, "--target", live, "--write"]) == 0
    assert value(live, "P#0", "PLAY#x") == "good"
    assert value(live, "P#29", "PLAY#x") == "good"
    assert value(live, "P#new", "PLAY#y") == "newer"
    out = capsys.readouterr().out
    assert "30 items written" in out
    assert "P#" not in out


def test_refuses_the_same_table_twice(tables: tuple[str, str]) -> None:
    live, _ = tables
    assert restore_copy.main(["--source", live, "--target", live, "--write"]) == 2
