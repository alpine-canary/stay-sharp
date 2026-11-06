"""Helpers for the account tests: plays and answers written straight into DynamoDB Local."""

from __future__ import annotations

import datetime as dt
from typing import Any

from staysharp import aws
from staysharp.store import table

NOW = dt.datetime(2026, 11, 20, 11, 0, tzinfo=dt.UTC)
A = "11111111-1111-4111-8111-111111111111"  # the account's primary id
B = "22222222-2222-4222-8222-222222222222"  # another browser, anonymous
SUB = "sub-0001"


def put_play(
    player: str,
    play_id: str,
    *,
    answered: int = 5,
    started: str = "2026-11-18T08:00:00.000Z",
    score: float = 4,
    extra: dict[str, Any] | None = None,
) -> None:
    day, level, mode = play_id.split(".")
    item: dict[str, Any] = {
        "date": day,
        "level": level,
        "mode": mode,
        "gameNumber": 3,
        "relaxed": False,
        "startedAt": started,
        "expiresAt": table.epoch_seconds(NOW + dt.timedelta(days=60)),
        "grades": {str(i): 1 for i in range(answered)},
        "score": score,
        "bonus": 0,
        "elapsedMs": 1000,
        **(extra or {}),
    }
    if answered:
        item["answered"] = {str(i) for i in range(answered)}
    aws.dynamodb().put_item(
        TableName=table.table_name(),
        Item={**table.play_key(player, play_id), **table.serialize(item)},
    )
    for index in range(answered):
        answer = {
            "qid": f"q_{index}",
            "version": 1,
            "deck": "spot",
            "grade": 1,
            "servedAt": started,
        }
        aws.dynamodb().put_item(
            TableName=table.table_name(),
            Item={**table.answer_key(player, play_id, index), **table.serialize(answer)},
        )


def items_of(player: str) -> dict[str, dict[str, Any]]:
    found = table.query_all(
        {
            "KeyConditionExpression": "PK = :pk",
            "ExpressionAttributeValues": {":pk": {"S": f"P#{player}"}},
        }
    )
    return {str(i["SK"]): i for i in found}
