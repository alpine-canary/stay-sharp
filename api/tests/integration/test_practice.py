"""Practice (task T108, Story 5, FR-021, FR-006, research C4, V14).

Practice reads only the past pool ``POOL#<level>#<deck>`` with ``SK < today``. A ``prefer`` id is
honoured only when it is in that result, so a future, unknown or other-level id gives a normal
past question and never the one asked for. Runs on DynamoDB Local through the real handler.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

from staysharp import aws
from staysharp.domain.models import DECKS
from staysharp.store import questions
from staysharp.store import table as store
from tests.events import PLAYER, body, call
from tests.integration.conftest import ddb, table  # noqa: F401 - fixtures
from tests.integration.game import TODAY, Game, game  # noqa: F401 - fixture

pytestmark = pytest.mark.integration

FUTURE_ONLY = "future_only_question"


def next_question(**payload: Any) -> dict[str, Any]:
    return call("POST", "/api/v1/practice/next", body={"level": "senior", **payload}, player=PLAYER)


def answer(attempt_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return call("POST", f"/api/v1/practice/{attempt_id}/answer", body=payload, player=PLAYER)


def past_pool(level: str, deck: str) -> set[str]:
    items = store.query_all(store.pool_query(level, deck, TODAY))  # type: ignore[arg-type]
    return {str(item["SK"]).split("#", 1)[1] for item in items}


def right(qid: str, version: int) -> dict[str, Any]:
    q = questions.question(qid, version)
    payload: dict[str, Any] = {"choiceId": q.answer_choice_id}
    if q.answer_lines:
        payload["line"] = q.answer_lines[0]
    return payload


def add_pool(level: str, deck: str, day: dt.date, qid: str) -> None:
    aws.dynamodb().put_item(
        TableName=store.table_name(),
        Item={**store.pool_key(level, deck, day, qid), "version": {"N": "1"}},  # type: ignore[arg-type]
    )


def test_questions_come_only_from_the_past_pool(game: Game) -> None:  # noqa: F811
    allowed = set().union(*(past_pool("senior", deck) for deck in DECKS["senior"]))
    assert allowed
    for deck in (None, "spot", "news"):
        for _ in range(6):
            result = next_question(**({"deck": deck} if deck else {}))
            assert result["statusCode"] == 200, result
            got = body(result)
            assert got["qid"] in allowed
            if deck:
                assert got["question"]["deck"] == deck
            for leaked in ("explanation", "answerChoiceId", "correctChoiceId", "sourceUrl"):
                assert leaked not in result["body"]


def test_prefer_is_honoured_for_a_past_pool_question(game: Game) -> None:  # noqa: F811
    wanted = sorted(past_pool("senior", "fail"))[0]
    got = body(next_question(deck="fail", prefer=[wanted]))
    assert got["qid"] == wanted
    # With all decks too, the first preferred id in the pool wins.
    got = body(next_question(prefer=["not_a_real_question", wanted]))
    assert got["qid"] == wanted


@pytest.mark.parametrize("when", [0, 1, 30])
def test_prefer_never_reaches_today_or_the_future(game: Game, when: int) -> None:  # noqa: F811
    add_pool("senior", "spot", TODAY + dt.timedelta(days=when), FUTURE_ONLY)
    for deck in ("spot", None):
        for _ in range(5):
            result = next_question(prefer=[FUTURE_ONLY], **({"deck": deck} if deck else {}))
            assert result["statusCode"] == 200
            assert body(result)["qid"] != FUTURE_ONLY


def test_prefer_never_reaches_an_unknown_or_other_level_question(game: Game) -> None:  # noqa: F811
    daily = questions.daily_set(TODAY, "starter")
    assert not isinstance(daily, questions.NotReady)
    starter = daily.items[0].qid
    add_pool("starter", "logic", TODAY - dt.timedelta(days=3), starter)
    assert starter in past_pool("starter", "logic")
    for prefer in (["no_such_question"], [starter]):
        got = body(next_question(prefer=prefer))
        assert got["qid"] not in prefer
        assert got["question"]["deck"] in DECKS["senior"]


def test_a_deck_of_another_level_is_refused(game: Game) -> None:  # noqa: F811
    assert next_question(deck="logic")["statusCode"] == 400


def test_answer_is_graded_once_and_the_same_answer_counts_once(game: Game) -> None:  # noqa: F811
    got = body(next_question(deck="better"))
    stored = store.get(store.practice_key(PLAYER, got["attemptId"]), consistent=True)
    assert stored is not None
    payload = right(got["qid"], int(stored["version"]))

    first = answer(got["attemptId"], payload)
    assert first["statusCode"] == 200
    graded = body(first)
    assert graded["grade"] == 1
    assert graded["bonus"] == 0
    assert graded["duplicate"] is False
    assert graded["explanation"]

    again = body(answer(got["attemptId"], payload))
    assert again["duplicate"] is True
    assert again["grade"] == 1

    q = questions.question(got["qid"], int(stored["version"]))
    other = next(c.id for c in q.choices if c.id != q.answer_choice_id)
    conflict = answer(got["attemptId"], {"choiceId": other})
    assert conflict["statusCode"] == 409
    assert body(conflict)["recorded"]["grade"] == 1


def test_attempts_are_per_player_and_expire_after_14_days(game: Game) -> None:  # noqa: F811
    got = body(next_question(deck="acronym"))
    stored = store.get(store.practice_key(PLAYER, got["attemptId"]), consistent=True)
    assert stored is not None
    assert stored["expiresAt"] == store.epoch_seconds(game.now + dt.timedelta(days=14))
    payload = right(got["qid"], int(stored["version"]))

    stranger = call(
        "POST",
        f"/api/v1/practice/{got['attemptId']}/answer",
        body=payload,
        player="2b7e1516-28ae-4d2a-a6d2-abf7158809cf",
    )
    assert stranger["statusCode"] == 400

    game.later(14 * 24 * 3600 + 1)
    assert answer(got["attemptId"], payload)["statusCode"] == 400
    assert answer("NOTANATTEMPTID22", payload)["statusCode"] == 400
    assert answer("bad id", payload)["statusCode"] == 400


def test_at_most_200_attempts_a_day(game: Game) -> None:  # noqa: F811
    aws.dynamodb().put_item(
        TableName=store.table_name(),
        Item={
            **store.practice_count_key(PLAYER, TODAY),
            "n": {"N": "199"},
            "expiresAt": {"N": "1"},
        },
    )
    assert next_question()["statusCode"] == 200
    refused = next_question()
    assert refused["statusCode"] == 429
    assert body(refused)["code"] == "rate_limited"
    # The next day starts again.
    game.later(24 * 3600)
    assert next_question()["statusCode"] == 200


def test_practice_never_touches_the_daily(game: Game) -> None:  # noqa: F811
    game.start()
    before = body(game.get())
    got = body(next_question(deck="spot"))
    stored = store.get(store.practice_key(PLAYER, got["attemptId"]), consistent=True)
    assert stored is not None
    answer(got["attemptId"], right(got["qid"], int(stored["version"])))
    assert body(game.get()) == before
