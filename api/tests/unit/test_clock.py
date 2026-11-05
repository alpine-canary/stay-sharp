"""The fake clock works on a laptop only (T059 support)."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from pathlib import Path

import pytest

from staysharp import clock


@pytest.fixture(autouse=True)
def fresh() -> Iterator[None]:
    clock.reset()
    yield
    clock.reset()


def test_real_time_without_a_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STAYSHARP_CLOCK_FILE", raising=False)
    assert abs(clock.now() - dt.datetime.now(dt.UTC)) < dt.timedelta(seconds=2)


def test_follows_the_file_on_local(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    file = tmp_path / "clock"
    file.write_text("2026-11-20T23:58:00+01:00")
    monkeypatch.setenv("STAGE", "local")
    monkeypatch.setenv("STAYSHARP_CLOCK_FILE", str(file))
    first = clock.now()
    assert (
        dt.timedelta(0)
        <= first - dt.datetime(2026, 11, 20, 22, 58, tzinfo=dt.UTC)
        < dt.timedelta(seconds=2)
    )
    file.write_text("2026-11-21T00:03:00+01:00")
    assert clock.now().astimezone(dt.UTC).hour == 23
    file.write_text("")
    assert abs(clock.now() - dt.datetime.now(dt.UTC)) < dt.timedelta(seconds=2)


@pytest.mark.parametrize("stage", ["dev", "prod"])
def test_ignored_outside_local(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, stage: str) -> None:
    file = tmp_path / "clock"
    file.write_text("2030-01-01T00:00:00+00:00")
    monkeypatch.setenv("STAGE", stage)
    monkeypatch.setenv("STAYSHARP_CLOCK_FILE", str(file))
    assert clock.now().year == dt.datetime.now(dt.UTC).year
