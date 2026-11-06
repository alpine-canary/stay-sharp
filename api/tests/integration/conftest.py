"""DynamoDB Local fixtures: one fresh table per test, same key schema as the real table."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import TYPE_CHECKING

import pytest

from staysharp import aws

if TYPE_CHECKING:
    from mypy_boto3_dynamodb import DynamoDBClient

ENDPOINT = "http://localhost:8000"


@pytest.fixture
def ddb(monkeypatch: pytest.MonkeyPatch) -> Iterator[DynamoDBClient]:
    monkeypatch.setenv("DYNAMODB_ENDPOINT", ENDPOINT)
    monkeypatch.setenv("AWS_REGION", "eu-central-2")
    # DynamoDB Local accepts any credentials; never use real ones here.
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "local")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "local")
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.delenv("AWS_SESSION_TOKEN", raising=False)
    aws.reset()
    yield aws.dynamodb()
    aws.reset()


@pytest.fixture
def table(ddb: DynamoDBClient, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    name = f"staysharp-test-{uuid.uuid4().hex[:12]}"
    ddb.create_table(
        TableName=name,
        BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
            {"AttributeName": "lastActiveMonth", "AttributeType": "S"},
        ],
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        # As infra/stacks/data_stack.py (M2): sparse, account items only.
        GlobalSecondaryIndexes=[
            {
                "IndexName": "GSI_INACTIVE",
                "KeySchema": [{"AttributeName": "lastActiveMonth", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "KEYS_ONLY"},
            }
        ],
    )
    monkeypatch.setenv("TABLE_NAME", name)
    yield name
    ddb.delete_table(TableName=name)
