"""Leak guard layer 1: the view builder over today + 7 days (R4, SC-002)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import pytest

from staysharp.publish import leak_check, validate
from staysharp.tools import publish

VALID = Path(__file__).resolve().parents[1] / "fixtures" / "publish" / "valid"


def test_the_real_view_builder_leaks_nothing() -> None:
    checked, problems = leak_check.check(validate.load(VALID), today=dt.date(2026, 11, 30))
    assert checked == 20
    assert problems == []


def test_only_today_to_seven_days_ahead_is_checked() -> None:
    content = validate.load(VALID)
    assert leak_check.check(content, today=dt.date(2026, 12, 2))[0] == 10
    assert leak_check.check(content, today=dt.date(2026, 11, 23))[0] == 0
    assert leak_check.check(content, today=dt.date(2026, 11, 24))[0] == 10


def test_a_view_that_carries_the_explanation_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    real = leak_check.question_view

    def leaky(question: Any, **kwargs: Any) -> dict[str, Any]:
        view = real(question, **kwargs)
        view["prompt"] = f"{view['prompt']} {question['explanation']}"
        return view

    monkeypatch.setattr(leak_check, "question_view", leaky)
    _, problems = leak_check.check(validate.load(VALID), today=dt.date(2026, 11, 30))
    assert len(problems) == 20
    assert {p.reason for p in problems} == {"the explanation reaches the view"}


def test_a_view_with_an_answer_field_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    real = leak_check.question_view

    def leaky(question: Any, **kwargs: Any) -> dict[str, Any]:
        return {**real(question, **kwargs), "answerChoiceId": question["answerChoiceId"]}

    monkeypatch.setattr(leak_check, "question_view", leaky)
    _, problems = leak_check.check(validate.load(VALID), today=dt.date(2026, 11, 30))
    reasons = {p.reason for p in problems}
    assert "an answer field reaches the view" in reasons
    assert any("outside the allowlist" in r for r in reasons)


def test_fingerprints_need_the_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("LEAK_GUARD_KEY", raising=False)
    assert publish.main(["fingerprints", str(VALID), "--out", str(tmp_path / "f.json")]) == 2
    assert "LEAK_GUARD_KEY" in capsys.readouterr().err
