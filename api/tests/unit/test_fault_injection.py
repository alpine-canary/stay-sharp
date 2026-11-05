"""The dev-only fault-injection wrapper (T077, research R10, W11)."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from typing import Any

import boto3
import pytest

from staysharp import obs
from staysharp.handlers import api
from staysharp.store import answers
from testing import fault_injection as fi
from tests.events import FakeContext, http_event

NOW = dt.datetime.now(dt.UTC)


@pytest.fixture(autouse=True)
def dev(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("STAGE", "dev")
    monkeypatch.delenv("STAYSHARP_DRILL", raising=False)
    fi._cache.clear()  # noqa: SLF001
    obs.metrics.clear_default_dimensions()
    obs.metrics.clear_metrics()
    yield
    fi._cache.clear()  # noqa: SLF001


def until(value: dt.datetime | None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fi, "_read_until", lambda: value)


def passthrough(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    seen: list[Any] = []

    def fake(event: Any, _context: Any) -> dict[str, Any]:
        seen.append((event, answers.answer))
        return {"statusCode": 200}

    monkeypatch.setattr(api, "handler", fake)
    return seen


def test_refused_in_prod(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STAGE", "prod")
    with pytest.raises(fi.Refused):
        fi.handler(http_event("GET", "/api/v1/health"), FakeContext())


def test_off_passes_through_untouched(monkeypatch: pytest.MonkeyPatch) -> None:
    until(None, monkeypatch)
    seen = passthrough(monkeypatch)
    fi.handler(http_event("GET", "/api/v1/health"), FakeContext())
    assert seen[0][1] is answers.answer


def test_on_makes_answers_fail_then_restores(monkeypatch: pytest.MonkeyPatch) -> None:
    until(NOW + dt.timedelta(minutes=5), monkeypatch)
    seen = passthrough(monkeypatch)
    real = answers.answer
    fi.handler(http_event("POST", "/api/v1/plays"), FakeContext())
    injected = seen[0][1]
    assert injected is not real
    with pytest.raises(answers.ScoringFailure):
        injected()
    assert answers.answer is real


def test_expired_injection_is_off(monkeypatch: pytest.MonkeyPatch) -> None:
    until(NOW - dt.timedelta(seconds=1), monkeypatch)
    seen = passthrough(monkeypatch)
    fi.handler(http_event("POST", "/api/v1/plays"), FakeContext())
    assert seen[0][1] is answers.answer


def test_end_time_is_capped_at_30_minutes(monkeypatch: pytest.MonkeyPatch) -> None:
    changed = NOW - dt.timedelta(minutes=31)

    class Ssm:
        class exceptions:  # noqa: N801 - boto3 shape
            ParameterNotFound = KeyError

        def get_parameter(self, Name: str) -> dict[str, Any]:  # noqa: N803 - boto3 shape
            assert Name == "/staysharp/dev/fault-injection"
            later = (NOW + dt.timedelta(days=1)).isoformat()
            return {"Parameter": {"Value": later, "LastModifiedDate": changed}}

    monkeypatch.setattr(boto3, "client", lambda *_a, **_k: Ssm())
    assert fi.injection_until() == changed + fi.MAX_ON
    assert not fi.injecting(NOW)


def test_selfcheck_drill_fails_the_selfcheck(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STAYSHARP_DRILL", "selfcheck-fail")
    result = fi.handler({"selfcheck": True}, FakeContext())
    assert result["ok"] is False


def test_traffic_drill_fails_requests_but_not_the_selfcheck(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STAYSHARP_DRILL", "fail-traffic")
    assert fi.handler({"selfcheck": True}, FakeContext())["ok"] is True
    with pytest.raises(RuntimeError, match="canary drill"):
        fi.handler(http_event("GET", "/api/v1/health"), FakeContext())


def test_unknown_drill_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STAYSHARP_DRILL", "everything")
    with pytest.raises(fi.Refused):
        fi.handler({"selfcheck": True}, FakeContext())
