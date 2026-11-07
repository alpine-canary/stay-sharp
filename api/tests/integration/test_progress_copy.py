"""The account's progress copy with versions (T221, FR-111, A7)."""

from __future__ import annotations

import pytest

from staysharp.store import accounts
from tests.integration.accounts_world import NOW, SUB, A

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def local(monkeypatch: pytest.MonkeyPatch, table: str) -> None:
    monkeypatch.setenv("STAGE", "local")
    accounts.adopt(SUB, A, NOW)  # a copy is only written for an active account


def body(level: str | None = "senior") -> dict[str, object]:
    copy = accounts.fresh_body()
    copy["level"] = level
    return copy


def test_a_new_account_reads_version_0_and_a_fresh_copy() -> None:
    assert accounts.get_progress(SUB) == accounts.ProgressCopy(0, accounts.fresh_body())


def test_versions_go_up_and_a_stale_write_gets_the_stored_copy() -> None:
    first = accounts.put_progress(SUB, 0, body("senior"), NOW)
    assert first.version == 1
    second = accounts.put_progress(SUB, 1, body("junior"), NOW)
    assert second.version == 2
    with pytest.raises(accounts.VersionConflict) as conflict:
        accounts.put_progress(SUB, 1, body("starter"), NOW)
    assert conflict.value.stored == accounts.ProgressCopy(2, body("junior"))
    # The browser merges and retries with the version it was given.
    assert accounts.put_progress(SUB, 2, body("starter"), NOW).version == 3


def test_two_first_writes_one_wins() -> None:
    accounts.put_progress(SUB, 0, body("senior"), NOW)
    with pytest.raises(accounts.VersionConflict):
        accounts.put_progress(SUB, 0, body("junior"), NOW)


def test_over_64_kb_is_refused() -> None:
    big = body()
    big["days"] = {"senior": {f"d{i}": "x" * 100 for i in range(700)}, "junior": {}, "starter": {}}
    with pytest.raises(accounts.TooLarge):
        accounts.put_progress(SUB, 0, big, NOW)


@pytest.mark.parametrize(
    "change",
    [
        {"version": 2},
        {"level": "expert"},
        {"relaxed": "yes"},
        {"days": {"senior": {}}},
        {"longest": {"senior": -1, "junior": 0, "starter": 0}},
        {"playerId": "not part of the copy"},
    ],
)
def test_a_copy_without_the_schema_outline_is_refused(change: dict[str, object]) -> None:
    with pytest.raises(accounts.BadProgress):
        accounts.put_progress(SUB, 0, {**body(), **change}, NOW)
