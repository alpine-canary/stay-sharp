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
