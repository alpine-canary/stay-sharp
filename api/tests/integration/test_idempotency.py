"""The same answer sent twice counts once (T051, FR-006, SC-003, V3)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from staysharp.domain import grading
from staysharp.domain.cancellation import Outcome
from staysharp.store import answers, plays, table
from staysharp.store.plays import PlayRef
from tests.events import body
from tests.integration.game import Game, game  # noqa: F401 - fixture

pytestmark = pytest.mark.integration


def _stored_score(g: Game) -> tuple[float, float, list[float | None]]:
    state = body(g.get())
    return state["score"], state["bonus"], state["grades"]


@pytest.mark.parametrize("times", [2, 10, 50])
def test_sequential_repeats_count_once(game: Game, times: int) -> None:  # noqa: F811
    game.start()
    game.open(0)
    game.later(10)
    first = game.answer(0, game.right(0))
    assert first["statusCode"] == 200
    assert body(first)["duplicate"] is False
    before = _stored_score(game)

    for _ in range(times - 1):
        again = game.answer(0, game.right(0))
        assert again["statusCode"] == 200
        repeat = body(again)
        assert repeat["duplicate"] is True
        assert repeat["grade"] == body(first)["grade"]
        assert repeat["elapsedMs"] == body(first)["elapsedMs"]

    assert _stored_score(game) == before
    assert before[0] == 1.0


@pytest.mark.parametrize("times", [2, 10, 50])
def test_concurrent_repeats_count_once(game: Game, times: int) -> None:  # noqa: F811
    """Concurrent requests run in separate Lambda containers, so they meet only in the store.

    The resolver is one request at a time per container (it holds the current event), so the
    race is driven at the store layer with one shared boto3 client, which is thread-safe.
    """
    game.start()
    game.open(0)
    game.later(10)
    ref = PlayRef.parse(game.play_id)
    play = plays.get(game.player, ref, game.now)
    served = answers.read(game.player, play, 0) if play else None
    assert play is not None and served is not None
    q = game.question(0)
    key = grading.AnswerKey(q.answer_choice_id, frozenset(q.answer_lines))
    right = game.right(0)
    submission = grading.Submission(right["choiceId"], right.get("line"))

    def submit(_: int) -> answers.Graded:
        return answers.answer(game.player, play, served, submission, key, game.now)

    with ThreadPoolExecutor(max_workers=min(times, 16)) as pool:
        results = list(pool.map(submit, range(times)))

    outcomes = [r.outcome for r in results]
    assert outcomes.count(None) == 1
    assert outcomes.count(Outcome.DUPLICATE) == times - 1
    score, _bonus, grades = _stored_score(game)
    assert score == 1.0
    assert grades[0] == 1.0


def test_a_different_answer_gets_409_with_the_stored_result(game: Game) -> None:  # noqa: F811
    game.start()
    game.open(0)
    game.later(10)
    first = body(game.answer(0, game.right(0)))
    before = _stored_score(game)

    other = game.answer(0, game.wrong(0))
    assert other["statusCode"] == 409
    payload = body(other)
    assert payload["code"] == "conflict"
    assert payload["recorded"]["grade"] == first["grade"]
    assert payload["recorded"]["correctChoiceId"] == first["correctChoiceId"]
    assert _stored_score(game) == before


def test_a_full_play_sums_once(game: Game) -> None:  # noqa: F811
    results = game.play_all(right=True, think_s=10)
    for index in range(5):
        assert body(game.answer(index, game.right(index)))["duplicate"] is True
    state = body(game.get())
    assert state["finished"] is True
    assert state["score"] == 5.0
    assert state["score"] == sum(r["grade"] for r in results)
    assert state["bonus"] == pytest.approx(sum(r["bonus"] for r in results))


def test_answer_item_keeps_one_grade(game: Game) -> None:  # noqa: F811
    game.start()
    game.open(0)
    game.answer(0, game.right(0))
    game.answer(0, game.right(0))
    item = table.get(table.answer_key(game.player, game.play_id, 0), consistent=True)
    assert item is not None
    assert item["grade"] == 1
