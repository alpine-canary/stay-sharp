"""``/me``, ``/me/adopt``, ``/me/progress`` against the accounts contract (T222).

Runs on DynamoDB Local. Every response is checked against the contract (additionalProperties
false), and no response may contain an e-mail address.
"""

from __future__ import annotations

import json
import re

import pytest

from staysharp import clock
from staysharp.store import accounts
from tests.contract.conftest import Checked
from tests.integration.accounts_world import NOW, put_play
from tests.integration.conftest import ddb, table  # noqa: F401 - fixtures

pytestmark = pytest.mark.integration

SUB = "3b9f0c1e-0000-4000-8000-00000000c0de"
A = "11111111-1111-4111-8111-111111111111"
B = "22222222-2222-4222-8222-222222222222"
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


@pytest.fixture(autouse=True)
def world(monkeypatch: pytest.MonkeyPatch, table: str) -> None:  # noqa: F811
    monkeypatch.setenv("STAGE", "local")
    monkeypatch.setattr(clock, "now", lambda: NOW)


def run(checked: Checked, method: str, path: str, **kwargs: object) -> dict[str, object]:
    result = checked(method, path, sub=SUB, **kwargs)
    assert not EMAIL.search(str(result["body"]))
    return result


def test_no_account_yet_then_create_by_adopting(checked: Checked) -> None:
    assert run(checked, "GET", "/api/v1/me", player=None)["statusCode"] == 404
    created = run(checked, "POST", "/api/v1/me/adopt", player=A, body={"adult": True})
    assert created["statusCode"] == 200
    assert json.loads(str(created["body"])) == {
        "primaryPlayerId": A,
        "created": True,
        "merged": {"plays": 0, "replays": 0},
    }
    me = run(checked, "GET", "/api/v1/me", player=None)
    assert json.loads(str(me["body"]))["primaryPlayerId"] == A


def test_adopt_needs_the_adult_answer_and_a_player_id(checked: Checked) -> None:
    assert (
        run(checked, "POST", "/api/v1/me/adopt", player=A, body={"adult": False})["statusCode"]
        == 400
    )
    assert (
        run(checked, "POST", "/api/v1/me/adopt", player=None, body={"adult": True})["statusCode"]
        == 400
    )


def test_second_browser_merge(checked: Checked) -> None:
    run(checked, "POST", "/api/v1/me/adopt", player=A, body={"adult": True})
    put_play(B, "2026-11-19.senior.daily")
    merged = run(checked, "POST", "/api/v1/me/adopt", player=B, body={"adult": True})
    assert json.loads(str(merged["body"]))["merged"] == {"plays": 1, "replays": 0}


def test_progress_round_trip_and_conflict(checked: Checked) -> None:
    run(checked, "POST", "/api/v1/me/adopt", player=A, body={"adult": True})
    fresh = run(checked, "GET", "/api/v1/me/progress", player=None)
    assert json.loads(str(fresh["body"]))["version"] == 0
    copy = {**accounts.fresh_body(), "level": "senior"}
    stored = run(
        checked, "PUT", "/api/v1/me/progress", player=None, body={"version": 0, "body": copy}
    )
    assert json.loads(str(stored["body"]))["version"] == 1
    stale = run(
        checked, "PUT", "/api/v1/me/progress", player=None, body={"version": 0, "body": copy}
    )
    assert stale["statusCode"] == 409
    assert json.loads(str(stale["body"])) == {"version": 1, "body": copy}


def test_progress_over_64_kb(checked: Checked) -> None:
    run(checked, "POST", "/api/v1/me/adopt", player=A, body={"adult": True})
    copy = accounts.fresh_body()
    copy["days"] = {"senior": {f"d{i}": "x" * 100 for i in range(700)}, "junior": {}, "starter": {}}
    result = run(
        checked, "PUT", "/api/v1/me/progress", player=None, body={"version": 0, "body": copy}
    )
    assert result["statusCode"] == 413


def test_display_name(checked: Checked) -> None:
    run(checked, "POST", "/api/v1/me/adopt", player=A, body={"adult": True})
    named = run(checked, "PUT", "/api/v1/me", player=None, body={"displayName": " Ann  K "})
    assert json.loads(str(named["body"]))["displayName"] == "Ann K"
    refused = run(checked, "PUT", "/api/v1/me", player=None, body={"displayName": "www.x"})
    assert refused["statusCode"] == 400


def test_without_claims_every_route_is_401(checked: Checked) -> None:
    result = checked("GET", "/api/v1/me", player=None)
    assert result["statusCode"] == 401
