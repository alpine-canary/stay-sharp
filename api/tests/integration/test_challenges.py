"""Challenge a colleague (task T101, Story 4, FR-018 to FR-020, research R2, W4, V6).

Runs on DynamoDB Local through the real handler with a fixed clock. The owner and the colleague
are two players; the colleague's result item must be written in the same transaction as their
fifth answer, so the tests read it straight from the table before any GET.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

from staysharp import aws
from staysharp.obs import player_hash
from staysharp.store import table as store
from tests.events import body, call
from tests.integration.conftest import ddb, table  # noqa: F401 - fixtures
from tests.integration.game import NOON, TODAY, Game, game  # noqa: F401 - fixture

pytestmark = pytest.mark.integration

COLLEAGUE = "2b7e1516-28ae-4d2a-a6d2-abf7158809cf"
THIRD = "6bc1bee2-2e40-4f96-a93d-7e117393172a"


def create(player: str, play_id: str) -> dict[str, Any]:
    return call("POST", "/api/v1/challenges", body={"playId": play_id}, player=player)


def view(player: str, challenge_id: str) -> dict[str, Any]:
    return call("GET", f"/api/v1/challenges/{challenge_id}", player=player)


def owner_challenge(owner: Game, *, right: bool = True) -> str:
    owner.play_all(right=right)
    created = create(owner.player, owner.play_id)
    assert created["statusCode"] == 200, created
    challenge_id: str = body(created)["challengeId"]
    return challenge_id


def colleague(owner: Game, challenge_id: str, *, player: str = COLLEAGUE) -> Game:
    """A colleague's play started from the link, on the challenge's date and level."""
    mode = "daily" if owner.day == TODAY else "replay"
    g = Game(now=owner.now, player=player, day=owner.day, mode=mode)
    started = g.start(challengeId=challenge_id, date=owner.day.isoformat())
    assert started["statusCode"] in (200, 201), started
    return g


def finish(g: Game, *, right: bool = False) -> list[dict[str, Any]]:
    results = []
    for index in range(5):
        g.open(index)
        g.later(3)
        result = g.answer(index, g.right(index) if right else g.wrong(index))
        assert result["statusCode"] == 200, result
        results.append(body(result))
    return results


def meta(challenge_id: str) -> dict[str, Any]:
    item = store.get(store.challenge_meta_key(challenge_id), consistent=True)
    assert item is not None
    return item


def result_item(challenge_id: str, player: str) -> dict[str, Any] | None:
    return store.get(store.challenge_result_key(challenge_id, player_hash(player)), consistent=True)


# --- Create ----------------------------------------------------------------------------------


def test_creating_twice_returns_the_same_id(game: Game) -> None:  # noqa: F811
    challenge_id = owner_challenge(game)
    again = create(game.player, game.play_id)
    assert again["statusCode"] == 200
    assert body(again) == {"challengeId": challenge_id, "path": f"/c/{challenge_id}"}

    item = meta(challenge_id)
    assert item["ownerHash"] == player_hash(game.player)
    assert game.player not in str(item)
    assert item["owner"]["score"] == 5
    assert item["results"] == 0
    assert item["expiresAt"] == store.epoch_seconds(NOON + dt.timedelta(days=30))


def test_create_refuses_an_unfinished_play_and_a_missing_one(game: Game) -> None:  # noqa: F811
    assert create(game.player, game.play_id)["statusCode"] == 404
    game.start()
    game.open(0)
    game.answer(0, game.right(0))
    refused = create(game.player, game.play_id)
    assert refused["statusCode"] == 409
    assert body(refused)["code"] == "conflict"


def test_create_refuses_a_replay(game: Game) -> None:  # noqa: F811
    game.play_all()
    replay = Game(now=game.now, mode="replay")
    replay.start()
    finish(replay)
    refused = create(game.player, replay.play_id)
    assert refused["statusCode"] == 400


# --- Colleague -------------------------------------------------------------------------------


def test_colleague_sees_only_the_owner_score_before_finishing(game: Game) -> None:  # noqa: F811
    challenge_id = owner_challenge(game)
    before = view(COLLEAGUE, challenge_id)
    assert before["statusCode"] == 200
    seen = body(before)
    assert seen["viewer"] == "colleague_before"
    assert seen["ownerScore"] == 5
    assert "owner" not in seen
    assert "you" not in seen
    assert (seen["date"], seen["level"]) == (TODAY.isoformat(), "senior")


def test_fifth_answer_writes_the_result_in_the_same_transaction(game: Game) -> None:  # noqa: F811
    challenge_id = owner_challenge(game)
    g = colleague(game, challenge_id)
    assert body(g.get())["challengeId"] == challenge_id
    finish(g)

    # No GET yet: the answer transaction wrote it.
    written = result_item(challenge_id, COLLEAGUE)
    assert written is not None
    assert written["score"] == 0
    assert meta(challenge_id)["results"] == 1

    after = body(view(COLLEAGUE, challenge_id))
    assert after["viewer"] == "colleague_after"
    assert after["owner"]["grades"] == [1, 1, 1, 1, 1]
    assert after["you"]["grades"] == [0, 0, 0, 0, 0]
    assert after["others"] == 1

    owner_view = body(view(game.player, challenge_id))
    assert owner_view["viewer"] == "owner"
    assert owner_view["owner"]["score"] == 5
    assert [c["score"] for c in owner_view["colleagues"]] == [0]
    assert "you" not in owner_view


def test_the_cap_of_50_keeps_grading(game: Game) -> None:  # noqa: F811
    challenge_id = owner_challenge(game)
    aws.dynamodb().update_item(
        TableName=store.table_name(),
        Key=store.challenge_meta_key(challenge_id),
        UpdateExpression="SET results = :n",
        ExpressionAttributeValues={":n": {"N": "50"}},
    )
    g = colleague(game, challenge_id)
    results = finish(g, right=True)
    assert [r["grade"] for r in results] == [1] * 5
    assert body(g.get())["score"] == 5
    assert result_item(challenge_id, COLLEAGUE) is None
    assert meta(challenge_id)["results"] == 50

    # Still shown side by side, from the colleague's own play.
    after = body(view(COLLEAGUE, challenge_id))
    assert after["viewer"] == "colleague_after"
    assert after["you"]["score"] == 5
    assert meta(challenge_id)["results"] == 50


def test_a_colleague_who_already_finished_sees_both_at_once(game: Game) -> None:  # noqa: F811
    challenge_id = owner_challenge(game)
    already = Game(now=game.now, player=COLLEAGUE)
    already.play_all(right=False)

    first = body(view(COLLEAGUE, challenge_id))
    assert first["viewer"] == "colleague_after"
    assert first["you"]["score"] == 0
    assert result_item(challenge_id, COLLEAGUE) is not None
    assert meta(challenge_id)["results"] == 1

    # Opening again writes nothing more, and starting from the link plays nothing new.
    assert body(view(COLLEAGUE, challenge_id))["others"] == 1
    assert meta(challenge_id)["results"] == 1
    again = already.start(challengeId=challenge_id)
    assert again["statusCode"] == 200
    assert body(again)["finished"] is True


def test_a_past_date_link_plays_as_a_past_set(game: Game) -> None:  # noqa: F811
    yesterday = TODAY - dt.timedelta(days=1)
    owner = Game(now=NOON - dt.timedelta(days=1), day=yesterday)
    challenge_id = owner_challenge(owner)

    g = Game(now=NOON, player=COLLEAGUE, day=yesterday, mode="replay")
    started = g.start(challengeId=challenge_id, date=yesterday.isoformat())
    assert started["statusCode"] == 201
    state = body(started)
    assert (state["mode"], state["date"]) == ("replay", yesterday.isoformat())
    assert state["question"]["index"] == 0
    finish(g, right=True)
    after = body(view(COLLEAGUE, challenge_id))
    assert after["viewer"] == "colleague_after"
    assert after["you"]["score"] == 5


def test_a_past_link_waits_for_an_unfinished_daily_of_that_day(game: Game) -> None:  # noqa: F811
    """C3 still holds: a replay must not show answers of a daily that can still be answered."""
    yesterday = TODAY - dt.timedelta(days=1)
    owner = Game(now=NOON - dt.timedelta(days=1), day=yesterday)
    challenge_id = owner_challenge(owner)
    late = Game(now=NOON - dt.timedelta(days=1), player=COLLEAGUE, day=yesterday)
    late.start()
    late.open(0)

    g = Game(now=NOON, player=COLLEAGUE, day=yesterday, mode="replay")
    refused = g.start(challengeId=challenge_id, date=yesterday.isoformat())
    assert refused["statusCode"] == 409


def test_a_play_must_match_the_challenge_date_level_and_mode(game: Game) -> None:  # noqa: F811
    challenge_id = owner_challenge(game)
    starter = Game(now=game.now, player=COLLEAGUE, level="starter")
    assert starter.start(challengeId=challenge_id)["statusCode"] == 400
    replay = Game(now=game.now, player=COLLEAGUE, mode="replay")
    assert replay.start(challengeId=challenge_id)["statusCode"] == 400
    unknown = Game(now=game.now, player=COLLEAGUE)
    assert unknown.start(challengeId="AAAAAAAAAAAA")["statusCode"] == 404


# --- Bad links and the owner -----------------------------------------------------------------


def test_expired_unknown_and_malformed_links(game: Game) -> None:  # noqa: F811
    challenge_id = owner_challenge(game)
    game.later(30 * 24 * 3600 + 1)
    expired = view(COLLEAGUE, challenge_id)
    assert expired["statusCode"] == 404
    assert body(expired)["code"] == "expired"
    late = Game(now=game.now, player=COLLEAGUE, day=TODAY, mode="replay")
    assert late.start(challengeId=challenge_id, date=TODAY.isoformat())["statusCode"] == 404

    unknown = view(COLLEAGUE, "ABCDEFGHJKMN")
    assert unknown["statusCode"] == 404
    assert body(unknown)["code"] == "not_found"
    for bad in ("short", "abcdefghijkl", "ABCDEFGHIJK1", "ABCDEFGHIJKLM"):
        malformed = view(COLLEAGUE, bad)
        assert malformed["statusCode"] == 404, bad
        assert body(malformed)["code"] == "not_found"


def test_the_owner_opening_their_own_link_sees_their_result(game: Game) -> None:  # noqa: F811
    challenge_id = owner_challenge(game)
    own = body(view(game.player, challenge_id))
    assert own["viewer"] == "owner"
    assert own["owner"]["score"] == 5
    assert own["colleagues"] == []
    assert own["others"] == 0

    # Starting from their own link gives back their finished daily, never a second play.
    again = game.start(challengeId=challenge_id)
    assert again["statusCode"] == 200
    assert body(again)["finished"] is True
    assert meta(challenge_id)["results"] == 0


def test_two_colleagues_are_counted_apart(game: Game) -> None:  # noqa: F811
    challenge_id = owner_challenge(game)
    finish(colleague(game, challenge_id))
    finish(colleague(game, challenge_id, player=THIRD), right=True)
    owner_view = body(view(game.player, challenge_id))
    assert sorted(c["score"] for c in owner_view["colleagues"]) == [0, 5]
    assert owner_view["others"] == 2
    assert body(view(THIRD, challenge_id))["you"]["score"] == 5
