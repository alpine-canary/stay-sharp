"""Spike (W15): does DynamoDB Local return the ALL_OLD item inside CancellationReasons?

The answer path (research R2) reads the stored answer from the cancellation reason instead of a
second read. If DynamoDB Local did not return it, the duplicate and conflict tests would have to
run against the dev table instead.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from botocore.exceptions import ClientError

if TYPE_CHECKING:
    from mypy_boto3_dynamodb import DynamoDBClient

pytestmark = pytest.mark.integration

KEY = {"PK": {"S": "P#spike"}, "SK": {"S": "ANS#2026-11-20.senior.daily#0"}}
CONDITION = "attribute_exists(servedAt) AND attribute_not_exists(grade)"
PLAY_KEY = {"PK": {"S": "P#spike"}, "SK": {"S": "PLAY#2026-11-20.senior.daily"}}


def answer(ddb: DynamoDBClient, table: str, choice: str) -> None:
    ddb.transact_write_items(
        TransactItems=[
            {
                "Update": {
                    "TableName": table,
                    "Key": KEY,
                    "UpdateExpression": "SET choiceId = :c, grade = :g",
                    "ConditionExpression": CONDITION,
                    "ExpressionAttributeValues": {":c": {"S": choice}, ":g": {"N": "1"}},
                    "ReturnValuesOnConditionCheckFailure": "ALL_OLD",
                }
            },
            {
                "Update": {
                    "TableName": table,
                    "Key": PLAY_KEY,
                    "UpdateExpression": "ADD score :g",
                    "ExpressionAttributeValues": {":g": {"N": "1"}},
                }
            },
        ]
    )


def cancellation(error: ClientError) -> list[dict[str, Any]]:
    reasons: list[dict[str, Any]] = error.response.get("CancellationReasons", [])  # type: ignore[assignment]
    return reasons


def test_all_old_item_is_returned_on_condition_failure(ddb: DynamoDBClient, table: str) -> None:
    ddb.put_item(TableName=table, Item={**KEY, "servedAt": {"S": "2026-11-20T08:00:00.000Z"}})
    answer(ddb, table, "AAAAAAAA")

    with pytest.raises(ClientError) as caught:
        answer(ddb, table, "AAAAAAAA")

    assert caught.value.response["Error"]["Code"] == "TransactionCanceledException"
    reasons = cancellation(caught.value)
    assert [r["Code"] for r in reasons] == ["ConditionalCheckFailed", "None"]
    old = reasons[0]["Item"]
    assert old["choiceId"] == {"S": "AAAAAAAA"}
    assert old["grade"] == {"N": "1"}
    assert old["servedAt"] == {"S": "2026-11-20T08:00:00.000Z"}


def test_missing_item_gives_a_reason_without_item(ddb: DynamoDBClient, table: str) -> None:
    with pytest.raises(ClientError) as caught:
        answer(ddb, table, "AAAAAAAA")
    reasons = cancellation(caught.value)
    assert reasons[0]["Code"] == "ConditionalCheckFailed"
    assert "Item" not in reasons[0]
