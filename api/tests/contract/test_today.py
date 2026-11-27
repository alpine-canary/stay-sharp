"""``GET /health`` and ``GET /today`` against the contract (T040, T041)."""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

import pytest
from openapi_core import OpenAPI
from openapi_core.testing import MockRequest, MockResponse
from openapi_core.validation.response.exceptions import InvalidData

from staysharp.domain.models import DailySet, Level
from staysharp.handlers import routes_today
from staysharp.store import questions
from tests.contract.conftest import HOST, Checked

NOW = dt.datetime(2026, 11, 20, 23, 30, tzinfo=dt.UTC)  # already Saturday 21 in Zurich


@pytest.fixture(autouse=True)
def world(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STAGE", "local")
    monkeypatch.setenv("LAUNCH_DATE", "2026-11-16")
    monkeypatch.setattr(routes_today, "now", lambda: NOW)

    def daily_set(day: dt.date, level: Level) -> DailySet | questions.NotReady:
        if level == "senior":
            return DailySet.model_validate(
                {
                    "date": day,
                    "level": level,
                    "gameNumber": 6,
                    "items": [
                        {"index": i, "deck": d, "qid": f"q_{i}", "version": 1, "targetSeconds": 30}
                        for i, d in enumerate(["spot", "better", "fail", "acronym", "news"])
                    ],
                }
            )
        return questions.NotReady(day, level)

    monkeypatch.setattr(questions, "daily_set", daily_set)


def test_health(checked: Checked) -> None:
    assert checked("GET", "/api/v1/health", player=None)["statusCode"] == 200


def test_today_uses_the_zurich_day(checked: Checked) -> None:
    result = checked("GET", "/api/v1/today", player=None)
    assert json.loads(result["body"]) == {
        "date": "2026-11-21",
        "gameNumber": 6,
        "weekStart": "2026-11-16",
        "levels": [
            {"level": "senior", "ready": True},
            {"level": "junior", "ready": False},
            {"level": "starter", "ready": False},
        ],
    }


def test_before_launch_game_one_is_coming_and_nothing_is_ready(
    checked: Checked, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LAUNCH_DATE", "2026-11-22")
    result = checked("GET", "/api/v1/today", player=None)
    assert result["statusCode"] == 200
    assert json.loads(result["body"]) == {
        "date": "2026-11-21",
        "gameNumber": 1,
        "weekStart": "2026-11-16",
        "levels": [
            {"level": "senior", "ready": False},
            {"level": "junior", "ready": False},
            {"level": "starter", "ready": False},
        ],
    }


def test_the_harness_rejects_an_unknown_field(openapi: OpenAPI) -> None:
    body: dict[str, Any] = {
        "date": "2026-11-21",
        "gameNumber": 6,
        "weekStart": "2026-11-16",
        "levels": [],
        "answerChoiceId": "AAAAAAAA",
    }
    request = MockRequest(HOST, "get", "/api/v1/today")
    response = MockResponse(json.dumps(body).encode(), status_code=200)
    with pytest.raises(InvalidData):
        openapi.validate_response(request, response)
