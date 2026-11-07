"""The hourly job finishes stuck deletions and counts the ones still stuck (T233)."""

from __future__ import annotations

import datetime as dt

import pytest

from staysharp.handlers import account_jobs
from staysharp.store import accounts, deletion
from tests.integration.accounts_world import NOW, SUB, A

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def local(monkeypatch: pytest.MonkeyPatch, table: str) -> None:  # noqa: F811
    monkeypatch.setenv("STAGE", "local")


def broken(_: str) -> None:
    raise RuntimeError("cognito down")


def half_deleted() -> None:
    accounts.adopt(SUB, A, NOW)
    with pytest.raises(RuntimeError):
        deletion.delete_account(SUB, NOW, broken)


def test_a_deletion_stuck_for_10_minutes_is_finished(monkeypatch: pytest.MonkeyPatch) -> None:
    half_deleted()
    emitted: list[tuple[str, float]] = []
    monkeypatch.setattr(account_jobs, "emit", lambda name, value: emitted.append((name, value)))
    early = account_jobs.finish_deletions(NOW + dt.timedelta(minutes=5), lambda _s: None)
    assert early == {"finished": 0, "failed": 0, "stuck": 0}
    later = account_jobs.finish_deletions(NOW + dt.timedelta(minutes=11), lambda _s: None)
    assert later["finished"] == 1
    assert accounts.get(SUB) is None
    assert emitted[-1] == ("StuckAccountDeletions", 0)


def test_still_failing_after_an_hour_is_counted(monkeypatch: pytest.MonkeyPatch) -> None:
    half_deleted()
    emitted: list[tuple[str, float]] = []
    monkeypatch.setattr(account_jobs, "emit", lambda name, value: emitted.append((name, value)))
    result = account_jobs.finish_deletions(NOW + dt.timedelta(hours=2), broken)
    assert result == {"finished": 0, "failed": 1, "stuck": 1}
    assert emitted == [("StuckAccountDeletions", 1)]


def test_the_whole_job_runs_locally_and_reports_counts_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every step together, with the real metric names (a name outside R11 fails here)."""
    monkeypatch.setenv("FAKE_COGNITO", "1")
    monkeypatch.setattr(account_jobs.clock, "now", lambda: NOW)
    accounts.adopt(SUB, A, NOW)
    result = account_jobs.run()
    assert result == {
        "finished": 0,
        "failed": 0,
        "stuck": 0,
        "inactive_warned": 0,
        "inactive_deleted": 0,
        "inactive_failed": 0,
        "unconfirmed_removed": 0,
    }

