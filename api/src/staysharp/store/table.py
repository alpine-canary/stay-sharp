"""Store base: keys for every access pattern (data-model.md A1 to A8) and checked reads.

Every read checks the response shape and raises ``StoreError`` on anything unexpected, so a
broken response is a counted failure, never a silent "not found". TTL deletion can lag by about
two days, so reads that depend on expiry use ``expired``.
"""

from __future__ import annotations

import datetime as dt
import os
from collections.abc import Mapping
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from boto3.dynamodb.types import TypeDeserializer, TypeSerializer

from staysharp import aws
from staysharp.domain.models import Deck, Level

if TYPE_CHECKING:
    from mypy_boto3_dynamodb.type_defs import AttributeValueTypeDef

    Key = dict[str, AttributeValueTypeDef]
else:
    Key = dict[str, Any]

_SERIALIZER = TypeSerializer()
_DESERIALIZER = TypeDeserializer()


class StoreError(RuntimeError):
    """The store answered with something we did not expect."""


def table_name() -> str:
    name = os.environ.get("TABLE_NAME")
    if not name:
        raise StoreError("TABLE_NAME is not set")
    return name


def key(pk: str, sk: str) -> Key:
    return {"PK": {"S": pk}, "SK": {"S": sk}}


# A1
def daily_key(day: dt.date, level: Level) -> Key:
    return key(f"DAILY#{day.isoformat()}#{level}", "SET")


# A2
def question_key(qid: str, version: int) -> Key:
    return key(f"Q#{qid}", f"V#{version}")


# A3
def play_key(player_id: str, play_id: str) -> Key:
    return key(f"P#{player_id}", f"PLAY#{play_id}")


# A4
def answer_key(player_id: str, play_id: str, index: int) -> Key:
    return key(f"P#{player_id}", f"ANS#{play_id}#{index}")


# A5
def practice_key(player_id: str, attempt_id: str) -> Key:
    return key(f"P#{player_id}", f"PRA#{attempt_id}")


def practice_count_key(player_id: str, day: dt.date) -> Key:
    return key(f"P#{player_id}", f"PRACOUNT#{day.isoformat()}")


# A6
def challenge_meta_key(challenge_id: str) -> Key:
    return key(f"CH#{challenge_id}", "META")


def challenge_result_key(challenge_id: str, player_hash: str) -> Key:
    return key(f"CH#{challenge_id}", f"R#{player_hash}")


# A7
def pool_key(level: Level, deck: Deck, day: dt.date, qid: str) -> Key:
    return key(f"POOL#{level}#{deck}", f"{day.isoformat()}#{qid}")


def pool_query(level: Level, deck: Deck, today: dt.date) -> dict[str, Any]:
    """Past questions of a deck only: ``SK < today`` (research R1, C4)."""
    return {
        "KeyConditionExpression": "PK = :pk AND SK < :today",
        "ExpressionAttributeValues": {
            ":pk": {"S": f"POOL#{level}#{deck}"},
            ":today": {"S": today.isoformat()},
        },
    }


# A8
def stock_key(level: Level, day: dt.date) -> Key:
    return key(f"STOCK#{level}", day.isoformat())


def stock_query(level: Level, today: dt.date) -> dict[str, Any]:
    """Days strictly after today with a complete set (R11)."""
    return {
        "KeyConditionExpression": "PK = :pk AND SK > :today",
        "ExpressionAttributeValues": {
            ":pk": {"S": f"STOCK#{level}"},
            ":today": {"S": today.isoformat()},
        },
    }


# --- Conversion and checked reads ------------------------------------------------------------


def serialize(data: Mapping[str, Any]) -> dict[str, Any]:
    return {name: _SERIALIZER.serialize(value) for name, value in data.items()}


def deserialize(item: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(item, Mapping):
        raise StoreError("item is not a map")
    return {name: _DESERIALIZER.deserialize(value) for name, value in item.items()}


def _check_key(item: Mapping[str, Any], wanted: Key) -> None:
    if item.get("PK") != wanted["PK"] or item.get("SK") != wanted["SK"]:
        raise StoreError("item key does not match the requested key")


def get(wanted: Key, *, consistent: bool = False) -> dict[str, Any] | None:
    response = aws.dynamodb().get_item(
        TableName=table_name(), Key=wanted, ConsistentRead=consistent
    )
    if not isinstance(response, Mapping):
        raise StoreError("get_item returned no map")
    raw = response.get("Item")
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise StoreError("get_item returned an item that is not a map")
    _check_key(raw, wanted)
    return deserialize(raw)


def query_all(query: Mapping[str, Any], *, limit: int = 1_000) -> list[dict[str, Any]]:
    """Run a key query, following pages, and stop with an error past ``limit`` items."""
    items: list[dict[str, Any]] = []
    start: Mapping[str, Any] | None = None
    while True:
        kwargs: dict[str, Any] = {"TableName": table_name(), **query}
        if start is not None:
            kwargs["ExclusiveStartKey"] = start
        response = aws.dynamodb().query(**kwargs)
        page = response.get("Items")
        if not isinstance(page, list):
            raise StoreError("query returned no item list")
        items.extend(deserialize(raw) for raw in page)
        if len(items) > limit:
            raise StoreError(f"query returned more than {limit} items")
        start = response.get("LastEvaluatedKey")
        if not start:
            return items


def epoch_seconds(moment: dt.datetime) -> int:
    if moment.tzinfo is None:
        raise ValueError("moment must carry a time zone")
    return int(moment.timestamp())


def expired(item: Mapping[str, Any], now: dt.datetime) -> bool:
    """True when ``expiresAt`` has passed, even if TTL has not deleted the item yet."""
    value = item.get("expiresAt")
    if value is None:
        return False
    if not isinstance(value, (int, Decimal)):
        raise StoreError("expiresAt is not a number")
    return int(value) <= epoch_seconds(now)


def iso_ms(moment: dt.datetime) -> str:
    """UTC ISO 8601 with milliseconds, the format of every stored timestamp."""
    if moment.tzinfo is None:
        raise ValueError("moment must carry a time zone")
    return moment.astimezone(dt.UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
