"""Merging an anonymous id into the primary id (T220, FR-110, FR-112, SC-103)."""

from __future__ import annotations

from typing import Any
from unittest import mock

import pytest
from botocore.exceptions import ClientError

from staysharp import aws
from staysharp.obs import player_hash
from staysharp.store import merge, table
from tests.integration.accounts_world import NOW, A, B, items_of, put_play

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def local(monkeypatch: pytest.MonkeyPatch, table: str) -> None:
    monkeypatch.setenv("STAGE", "local")


def test_days_only_one_side_played_move_over_with_their_answers() -> None:
    put_play(A, "2026-11-18.senior.daily")
    put_play(B, "2026-11-19.senior.daily")
    put_play(B, "2026-11-19.junior.daily", answered=2)
    result = merge.merge(A, B, NOW)
    assert result == merge.Merged(plays=2, replays=0)
    mine = items_of(A)
    assert {
        "PLAY#2026-11-18.senior.daily",
        "PLAY#2026-11-19.senior.daily",
        "PLAY#2026-11-19.junior.daily",
    } <= set(mine)
    assert "ANS#2026-11-19.senior.daily#4" in mine
    assert "ANS#2026-11-19.junior.daily#1" in mine
    assert items_of(B) == {}


def test_same_day_and_level_the_first_finished_daily_keeps_the_score() -> None:
    # The primary id played later; the other browser finished first.
    put_play(A, "2026-11-19.senior.daily", started="2026-11-19T18:00:00.000Z", score=2)
    put_play(B, "2026-11-19.senior.daily", started="2026-11-19T07:00:00.000Z", score=5)
    result = merge.merge(A, B, NOW)
    assert result == merge.Merged(plays=1, replays=1)
    mine = items_of(A)
    assert mine["PLAY#2026-11-19.senior.daily"]["score"] == 5
    replay = mine["PLAY#2026-11-19.senior.replay"]
    assert (replay["score"], replay["mode"]) == (2, "replay")
    assert "ANS#2026-11-19.senior.replay#0" in mine
    assert items_of(B) == {}


def test_a_finished_daily_beats_an_unfinished_one() -> None:
    put_play(A, "2026-11-19.senior.daily", started="2026-11-19T06:00:00.000Z", answered=2)
    put_play(B, "2026-11-19.senior.daily", started="2026-11-19T09:00:00.000Z")
    merge.merge(A, B, NOW)
    mine = items_of(A)
    assert len(mine["PLAY#2026-11-19.senior.daily"]["answered"]) == 5
    assert len(mine["PLAY#2026-11-19.senior.replay"]["answered"]) == 2


def test_two_unfinished_dailies_never_leave_a_replay_beside_an_open_daily() -> None:
    """A replay shows the answers: next to an unfinished scored daily it would be an answer key
    (C3). The play with more answers stays the daily; the other one is dropped."""
    put_play(A, "2026-11-19.senior.daily", started="2026-11-19T09:00:00.000Z", answered=1)
    put_play(B, "2026-11-19.senior.daily", started="2026-11-19T06:00:00.000Z", answered=2)
    merge.merge(A, B, NOW)
    mine = items_of(A)
    assert len(mine["PLAY#2026-11-19.senior.daily"]["answered"]) == 2
    assert "PLAY#2026-11-19.senior.replay" not in mine
    assert not [k for k in mine if k.startswith("ANS#2026-11-19.senior.replay")]
    assert items_of(B) == {}


def test_the_same_both_ways_round() -> None:
    put_play(A, "2026-11-19.senior.daily", started="2026-11-19T06:00:00.000Z", answered=3)
    put_play(B, "2026-11-19.senior.daily", started="2026-11-19T05:00:00.000Z", answered=1)
    merge.merge(A, B, NOW)
    mine = items_of(A)
    assert len(mine["PLAY#2026-11-19.senior.daily"]["answered"]) == 3
    assert "PLAY#2026-11-19.senior.replay" not in mine


def test_first_finished_means_finished_first_not_started_first() -> None:
    # B started earlier but took 3 hours; A started later and finished first.
    put_play(
        A,
        "2026-11-19.senior.daily",
        started="2026-11-19T07:00:00.000Z",
        score=2,
        extra={"elapsedMs": 60_000},
    )
    put_play(
        B,
        "2026-11-19.senior.daily",
        started="2026-11-19T06:00:00.000Z",
        score=5,
        extra={"elapsedMs": 3 * 3_600_000},
    )
    merge.merge(A, B, NOW)
    mine = items_of(A)
    assert mine["PLAY#2026-11-19.senior.daily"]["score"] == 2
    assert mine["PLAY#2026-11-19.senior.replay"]["score"] == 5


def test_the_loser_is_dropped_when_that_day_already_has_a_replay() -> None:
    put_play(A, "2026-11-19.senior.daily", started="2026-11-19T06:00:00.000Z")
    put_play(A, "2026-11-19.senior.replay", started="2026-11-19T06:30:00.000Z", score=1)
    put_play(B, "2026-11-19.senior.daily", started="2026-11-19T09:00:00.000Z", score=3)
    assert merge.merge(A, B, NOW) == merge.Merged(plays=1, replays=1)
    mine = items_of(A)
    assert mine["PLAY#2026-11-19.senior.replay"]["score"] == 1
    assert items_of(B) == {}


def test_challenge_results_and_owned_challenges_follow() -> None:
    put_play(
        B,
        "2026-11-19.senior.daily",
        extra={"challengeId": "AAAAAAAAAAAA", "createdChallengeId": "BBBBBBBBBBBB"},
    )
    put = aws.dynamodb().put_item
    put(
        TableName=table.table_name(),
        Item={
            **table.challenge_result_key("AAAAAAAAAAAA", player_hash(B)),
            **table.serialize({"score": 3}),
        },
    )
    put(
        TableName=table.table_name(),
        Item={
            **table.challenge_meta_key("BBBBBBBBBBBB"),
            **table.serialize({"ownerHash": player_hash(B)}),
        },
    )
    merge.merge(A, B, NOW)
    assert table.get(table.challenge_result_key("AAAAAAAAAAAA", player_hash(A))) is not None
    assert table.get(table.challenge_result_key("AAAAAAAAAAAA", player_hash(B))) is None
    meta = table.get(table.challenge_meta_key("BBBBBBBBBBBB"))
    assert meta is not None and meta["ownerHash"] == player_hash(A)


def test_practice_moves_and_daily_counts_add_up() -> None:
    put = aws.dynamodb().put_item
    put(
        TableName=table.table_name(),
        Item={**table.practice_key(B, "ATTEMPT"), **table.serialize({"qid": "q"})},
    )
    put(
        TableName=table.table_name(),
        Item={**table.practice_count_key(A, NOW.date()), **table.serialize({"n": 3})},
    )
    put(
        TableName=table.table_name(),
        Item={**table.practice_count_key(B, NOW.date()), **table.serialize({"n": 4})},
    )
    merge.merge(A, B, NOW)
    mine = items_of(A)
    assert "PRA#ATTEMPT" in mine
    assert mine[f"PRACOUNT#{NOW.date().isoformat()}"]["n"] == 7
    assert items_of(B) == {}


def test_repeating_a_finished_merge_changes_nothing() -> None:
    put_play(A, "2026-11-19.senior.daily", started="2026-11-19T18:00:00.000Z")
    put_play(B, "2026-11-19.senior.daily", started="2026-11-19T07:00:00.000Z")
    merge.merge(A, B, NOW)
    before = items_of(A)
    assert merge.merge(A, B, NOW) == merge.Merged(plays=0, replays=0)
    assert items_of(A) == before


def test_a_crash_half_way_then_a_retry_gives_the_same_end_state() -> None:
    days = ["2026-11-15", "2026-11-16", "2026-11-17", "2026-11-18"]
    for day in days:
        put_play(B, f"{day}.senior.daily")
    real = aws.dynamodb().transact_write_items
    calls = {"n": 0}

    def flaky(**kwargs: Any) -> Any:
        calls["n"] += 1
        if calls["n"] == 3:
            raise ClientError(
                {"Error": {"Code": "InternalServerError", "Message": "boom"}}, "TransactWriteItems"
            )
        return real(**kwargs)

    with (
        mock.patch.object(aws.dynamodb(), "transact_write_items", side_effect=flaky),
        pytest.raises(ClientError),
    ):
        merge.merge(A, B, NOW)
    merge.merge(A, B, NOW)
    mine = items_of(A)
    assert {f"PLAY#{d}.senior.daily" for d in days} <= set(mine)
    assert sum(1 for sk in mine if sk.startswith("ANS#")) == 20
    assert items_of(B) == {}
