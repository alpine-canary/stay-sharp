"""The pre-traffic self-check (T072, research R10, C5)."""

from __future__ import annotations

import json
from typing import Any

import pytest

from staysharp import aws, selfcheck
from staysharp.domain import cancellation, grading, views
from staysharp.handlers import api
from staysharp.obs import metrics
from tests.events import FakeContext


@pytest.fixture(autouse=True)
def no_table(monkeypatch: pytest.MonkeyPatch) -> None:
    """Any real DynamoDB or table access fails the test."""

    def refuse() -> Any:
        raise AssertionError("the self-check must not touch DynamoDB")

    monkeypatch.setattr(aws, "dynamodb", refuse)
    monkeypatch.delenv("TABLE_NAME", raising=False)
    monkeypatch.setenv("STAGE", "local")
    metrics.clear_default_dimensions()
    metrics.clear_metrics()


def test_passes_on_this_build() -> None:
    result = selfcheck.run()
    assert result == {
        "ok": True,
        "checks": {
            "grading": True,
            "view_allowlist": True,
            "classification": True,
            "answer_path": True,
        },
        "failed": [],
    }


def test_the_lambda_routes_the_synthetic_event() -> None:
    result = api.handler({"selfcheck": True}, FakeContext())
    assert result["ok"] is True


def test_fixtures_are_never_eligible_for_a_daily() -> None:
    assert all(not q.daily_eligible for q in selfcheck.fixtures().values())


@pytest.mark.parametrize("check", list(selfcheck.CHECKS))
def test_any_failing_check_fails_the_whole(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], check: str
) -> None:
    def broken() -> bool:
        raise AssertionError("broken on purpose")

    monkeypatch.setitem(selfcheck.CHECKS, check, broken)
    result = selfcheck.run()
    assert result["ok"] is False
    assert result["failed"] == [check]
    metrics.flush_metrics()
    out = capsys.readouterr().out
    blobs = [json.loads(line) for line in out.splitlines() if line.startswith("{")]
    assert any("SelfCheckFailures" in b for b in blobs)


def test_a_check_returning_false_also_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(selfcheck.CHECKS, "grading", lambda: False)
    assert selfcheck.run()["ok"] is False


def test_a_leaking_view_is_caught(monkeypatch: pytest.MonkeyPatch) -> None:
    real = views.question_view

    def leaky(question: Any, **kwargs: Any) -> dict[str, Any]:
        view = real(question, **kwargs)
        view["explanation"] = question["explanation"]
        return view

    monkeypatch.setattr(selfcheck, "question_view", leaky)
    assert selfcheck.run()["failed"] == ["view_allowlist"]


def test_a_grading_regression_is_caught(monkeypatch: pytest.MonkeyPatch) -> None:
    from decimal import Decimal

    monkeypatch.setattr(
        grading,
        "speed_bonus",
        lambda grade_, **_: Decimal("0.3") if grade_ == 1 else Decimal(0),
    )
    assert "grading" in selfcheck.run()["failed"]


def test_a_classification_regression_is_caught(monkeypatch: pytest.MonkeyPatch) -> None:
    from staysharp.domain.cancellation import Outcome

    monkeypatch.setattr(cancellation, "classify", lambda *_: Outcome.DUPLICATE)
    failed = selfcheck.run()["failed"]
    assert "classification" in failed
