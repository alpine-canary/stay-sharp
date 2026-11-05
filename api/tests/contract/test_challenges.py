"""Challenge routes against contracts/openapi.yaml (task T102).

Every response is validated by the ``checked`` harness: the strict schemas fail if the owner's
squares reach a colleague before they finish, or if any extra field appears.
"""

from __future__ import annotations

import pytest

from tests.contract.conftest import Checked
from tests.events import body
from tests.integration.conftest import ddb, table  # noqa: F401 - fixtures
from tests.integration.game import Game, game  # noqa: F401 - fixture

pytestmark = pytest.mark.integration

COLLEAGUE = "2b7e1516-28ae-4d2a-a6d2-abf7158809cf"


def test_create_view_play_and_compare(game: Game, checked: Checked) -> None:  # noqa: F811
    game.play_all()
    created = checked("POST", "/api/v1/challenges", body={"playId": game.play_id}, player=game.player)
    assert created["statusCode"] == 200
    challenge_id = body(created)["challengeId"]
    path = f"/api/v1/challenges/{challenge_id}"

    before = checked("GET", path, player=COLLEAGUE)
    assert body(before)["viewer"] == "colleague_before"

    other = Game(now=game.now, player=COLLEAGUE)
    start = checked(
        "POST",
        "/api/v1/plays",
        body={"level": "senior", "mode": "daily", "challengeId": challenge_id},
        player=COLLEAGUE,
    )
    assert body(start)["challengeId"] == challenge_id
    for index in range(5):
        other.open(index)
        other.answer(index, other.right(index))

    assert body(checked("GET", path, player=COLLEAGUE))["viewer"] == "colleague_after"
    assert body(checked("GET", path, player=game.player))["viewer"] == "owner"


def test_refusals(game: Game, checked: Checked) -> None:  # noqa: F811
    missing = checked("POST", "/api/v1/challenges", body={"playId": game.play_id}, player=game.player)
    assert missing["statusCode"] == 404
    game.start()
    unfinished = checked(
        "POST", "/api/v1/challenges", body={"playId": game.play_id}, player=game.player
    )
    assert unfinished["statusCode"] == 409
    unknown = checked("GET", "/api/v1/challenges/ABCDEFGHJKMN", player=COLLEAGUE)
    assert unknown["statusCode"] == 404
