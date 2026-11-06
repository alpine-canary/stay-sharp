"""The local server builds HTTP API events like API Gateway does (T042)."""

import pytest

from staysharp import local


def test_event_from_a_local_request() -> None:
    event = local.to_event(
        "POST",
        "/api/v1/plays?x=1",
        {"X-Player-Id": "abc", "Content-Type": "application/json"},
        b"{}",
    )
    assert event["rawPath"] == "/api/v1/plays"
    assert event["rawQueryString"] == "x=1"
    assert event["headers"]["x-player-id"] == "abc"
    assert event["requestContext"]["http"]["method"] == "POST"
    assert event["body"] == "{}"


def test_refuses_any_stage_but_local(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STAGE", "dev")
    assert local.main([]) == 2


def _local_fake(monkeypatch: pytest.MonkeyPatch) -> None:
    from testing import fake_cognito

    fake_cognito.reset()
    monkeypatch.setenv("FAKE_COGNITO", "1")


def test_account_routes_need_a_token(monkeypatch: pytest.MonkeyPatch) -> None:
    _local_fake(monkeypatch)
    assert local.route("GET", "/api/v1/me", {}, b"")["statusCode"] == 401
    assert (
        local.route("GET", "/api/v1/me", {"Authorization": "Bearer nope"}, b"")["statusCode"] == 401
    )


def test_a_valid_token_passes_its_claims_like_the_authorizer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from testing import fake_cognito

    _local_fake(monkeypatch)
    event = local.to_event(
        "GET", "/api/v1/me", {"Authorization": f"Bearer {fake_cognito.issue('sub-9')}"}, b""
    )
    assert local.authorize(event)
    claims = event["requestContext"]["authorizer"]["jwt"]["claims"]
    assert claims["sub"] == "sub-9"
    assert claims["token_use"] == "access"


def test_m1_routes_stay_open(monkeypatch: pytest.MonkeyPatch) -> None:
    _local_fake(monkeypatch)
    assert local.authorize(local.to_event("GET", "/api/v1/today", {}, b""))


def test_the_fake_sign_in_answers_on_cognito(monkeypatch: pytest.MonkeyPatch) -> None:
    _local_fake(monkeypatch)
    result = local.route(
        "POST",
        "/cognito",
        {"X-Amz-Target": "AWSCognitoIdentityProviderService.SignUp"},
        b'{"ClientId": "fake-client", "Username": "a@example.test"}',
    )
    assert result["statusCode"] == 200
    assert "UserSub" in result["body"]


def test_without_the_flag_there_is_no_fake(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FAKE_COGNITO", raising=False)
    monkeypatch.setenv("STAGE", "local")
    result = local.route("POST", "/cognito", {}, b"{}")
    assert result["statusCode"] >= 400
    assert "UserSub" not in result["body"]


def test_auth_json_points_at_the_fake(monkeypatch: pytest.MonkeyPatch) -> None:
    import json

    _local_fake(monkeypatch)
    result = local.route("GET", "/auth.json", {}, b"")
    assert json.loads(result["body"]) == {"endpoint": "/cognito", "clientId": "fake-client"}
