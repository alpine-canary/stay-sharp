"""Practice routes against contracts/openapi.yaml (T110): the view has no answer field, and the
200, 409 and 429 bodies match the contract."""

from __future__ import annotations

import pytest

from staysharp import aws
from staysharp.store import questions
from staysharp.store import table as store
from tests.contract.conftest import Checked
from tests.events import PLAYER, body
from tests.integration.conftest import ddb, table  # noqa: F401 - fixtures
from tests.integration.game import TODAY, Game, game  # noqa: F401 - fixture

pytestmark = pytest.mark.integration


def test_next_answer_conflict_and_limit(game: Game, checked: Checked) -> None:  # noqa: F811
    got = body(checked("POST", "/api/v1/practice/next", body={"level": "senior"}, player=PLAYER))
    item = store.get(store.practice_key(PLAYER, got["attemptId"]), consistent=True)
    assert item is not None
    q = questions.question(got["qid"], int(item["version"]))
    path = f"/api/v1/practice/{got['attemptId']}/answer"
    first = {
        "choiceId": q.answer_choice_id,
        **({"line": q.answer_lines[0]} if q.answer_lines else {}),
    }
    assert checked("POST", path, body=first, player=PLAYER)["statusCode"] == 200
    other = next(c.id for c in q.choices if c.id != q.answer_choice_id)
    second = {"choiceId": other, **({"line": q.answer_lines[0]} if q.answer_lines else {})}
    assert checked("POST", path, body=second, player=PLAYER)["statusCode"] == 409

    aws.dynamodb().put_item(
        TableName=store.table_name(),
        Item={**store.practice_count_key(PLAYER, TODAY), "n": {"N": "200"}},
    )
    limited = checked("POST", "/api/v1/practice/next", body={"level": "senior"}, player=PLAYER)
    assert limited["statusCode"] == 429
