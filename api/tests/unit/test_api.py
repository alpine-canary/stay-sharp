"""Edge behaviour of the API handler (research R8, R10; T038)."""

from __future__ import annotations

import datetime as dt
import json

import pytest
from aws_lambda_powertools.event_handler import Response

from staysharp.domain.models import AnswerRequest
from staysharp.handlers import api, routes_today
from staysharp.store import questions
from tests.events import PLAYER, FakeContext, body, call, captured_logs, http_event


@pytest.fixture(autouse=True)
def fixed_world(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STAGE", "local")
    monkeypatch.setenv("POWERTOOLS_METRICS_NAMESPACE", "StaySharp")
    monkeypatch.setattr(routes_today, "now", lambda: dt.datetime(2026, 11, 20, 8, tzinfo=dt.UTC))
    monkeypatch.setattr(questions, "daily_set", lambda day, level: questions.NotReady(day, level))


@api.app.post("/echo-test")
def echo() -> Response[str]:
    # Test-only route: validates a body and returns the player id from the context.
    AnswerRequest.model_validate(api.app.current_event.json_body)
    return Response(200, "application/json", json.dumps({"player": api.app.context["player_id"]}))


def test_every_response_is_no_store() -> None:
    for result in (
        call("GET", "/api/v1/health", player=None),
        call("GET", "/api/v1/today", player=None),
        call("GET", "/api/v1/nowhere"),
        call("POST", "/api/v1/echo-test", player="bad"),
    ):
        assert result["headers"]["Cache-Control"] == "no-store"


def test_health_and_today_need_no_player_id() -> None:
    assert call("GET", "/api/v1/health", player=None)["statusCode"] == 200
    assert call("GET", "/api/v1/today", player=None)["statusCode"] == 200


@pytest.mark.parametrize("player", [None, "", "not-a-uuid", "123e4567-e89b-12d3-a456-426614174000"])
def test_other_routes_need_a_uuid4_player_id(player: str | None) -> None:
    result = call("POST", "/api/v1/echo-test", body={"choiceId": "AAAAAAAA"}, player=player)
    assert result["statusCode"] == 400
    assert body(result)["code"] == "invalid_request"


def test_player_id_reaches_the_route() -> None:
    result = call("POST", "/api/v1/echo-test", body={"choiceId": "AAAAAAAA"})
    assert result["statusCode"] == 200
    assert body(result) == {"player": PLAYER}


def test_body_over_2_kb_is_refused() -> None:
    result = call("POST", "/api/v1/echo-test", body="x" * 2_049)
    assert result["statusCode"] == 413
    assert body(result)["code"] == "invalid_request"


def test_unknown_path_is_a_json_404() -> None:
    result = call("GET", "/api/v1/nowhere")
    assert result["statusCode"] == 404
    assert body(result)["code"] == "not_found"


def test_validation_error_logs_field_names_but_never_values() -> None:
    marker = "MARKER-INPUT-VALUE"
    with captured_logs() as logs:
        result = call("POST", "/api/v1/echo-test", body={"choiceId": marker, "extra": marker})
    assert result["statusCode"] == 400
    assert "choiceId" in body(result)["message"]
    assert marker not in result["body"]
    assert "validation failed" in logs.text
    assert "choiceId" in logs.text
    assert marker not in logs.text


def test_logs_carry_the_player_hash_never_the_raw_id_or_ip() -> None:
    with captured_logs() as logs:
        call("POST", "/api/v1/echo-test", body={"choiceId": "bad"})
        call("POST", "/api/v1/echo-test", body={"choiceId": "AAAAAAAA"}, player="bad")
    assert '"player_hash"' in logs.text
    assert '"request_id"' in logs.text
    assert PLAYER not in logs.text
    assert "192.0.2.1" not in logs.text
    assert "pytest" not in logs.text  # user agent


def test_unexpected_error_is_a_json_500(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(day: dt.date, level: str) -> questions.NotReady:
        raise RuntimeError("store down")

    monkeypatch.setattr(questions, "daily_set", boom)
    result = call("GET", "/api/v1/today", player=None)
    assert result["statusCode"] == 500
    assert body(result)["code"] == "unavailable"
    assert "store down" not in result["body"]


def test_selfcheck_event_fails_until_the_self_check_exists() -> None:
    result = api.handler({"selfcheck": True}, FakeContext())
    assert result["ok"] is False


def test_selfcheck_is_only_the_exact_flag() -> None:
    event = http_event("GET", "/api/v1/health", player=None)
    event["selfcheck"] = "yes"
    assert api.handler(event, FakeContext())["statusCode"] == 200
