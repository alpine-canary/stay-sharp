"""Inactive accounts (T242, FR-120, research A8), with a mocked clock.

An account last used in month M counts as inactive from the first day of M + 1. It is warned by
e-mail once 23 months later and deleted 24 months later, never sooner than 30 days after the
warning. Any activity (``touch``) clears the warning. Sign-ups never confirmed are removed from
the sign-in service after 7 days, so an unused address is not kept.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

from staysharp import aws
from staysharp.store import accounts, inactive, table
from tests.integration.accounts_world import NOW, SUB, A

pytestmark = pytest.mark.integration

UTC = dt.UTC
# Last active in November 2026: inactive from 1 December 2026.
WARN_AT = dt.datetime(2028, 11, 1, 3, 0, tzinfo=UTC)
DELETE_AT = dt.datetime(2028, 12, 1, 3, 0, tzinfo=UTC)
ADDRESS = "player@example.test"


@pytest.fixture(autouse=True)
def local(monkeypatch: pytest.MonkeyPatch, table: str) -> None:  # noqa: F811
    monkeypatch.setenv("STAGE", "local")


class Mail:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []

    def __call__(self, to: str, subject: str, text: str) -> None:
        self.sent.append((to, subject, text))


class Users:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    def email(self, sub: str) -> str | None:
        return ADDRESS if sub not in self.deleted else None

    def delete(self, sub: str) -> None:
        self.deleted.append(sub)


def run(now: dt.datetime, mail: Mail, users: Users) -> dict[str, int]:
    return inactive.run(now, send=mail, email_of=users.email, delete_user=users.delete)


def meta() -> dict[str, object] | None:
    return table.get(accounts.account_key(SUB), consistent=True)


def test_months_are_counted_from_the_end_of_the_last_active_month() -> None:
    assert inactive.inactive_since("2026-11") == dt.datetime(2026, 12, 1, tzinfo=UTC)
    assert inactive.add_months(dt.datetime(2027, 1, 31, tzinfo=UTC), 1) == dt.datetime(
        2027, 2, 28, tzinfo=UTC
    )


def test_nothing_happens_before_23_months() -> None:
    accounts.adopt(SUB, A, NOW)
    mail, users = Mail(), Users()
    result = run(dt.datetime(2028, 10, 31, 23, 59, tzinfo=UTC), mail, users)
    assert result["warned"] == 0
    assert result["deleted"] == 0
    assert mail.sent == []


def test_warned_once_at_23_months_in_plain_text_without_links_that_track() -> None:
    accounts.adopt(SUB, A, NOW)
    mail, users = Mail(), Users()
    assert run(WARN_AT, mail, users)["warned"] == 1
    assert run(WARN_AT + dt.timedelta(hours=1), mail, users)["warned"] == 0
    assert len(mail.sent) == 1
    to, subject, text = mail.sent[0]
    assert to == ADDRESS
    assert "deleted" in subject.lower()
    assert "1 December 2028" in text
    assert "sign in" in text.lower()
    assert "?" not in text.split("http", 1)[-1].split()[0]  # a plain address, no tracking query
    item = meta()
    assert item is not None
    assert "warnedAt" in item


def test_deleted_at_24_months_with_the_us3_steps() -> None:
    accounts.adopt(SUB, A, NOW)
    mail, users = Mail(), Users()
    run(WARN_AT, mail, users)
    result = run(DELETE_AT, mail, users)
    assert result["deleted"] == 1
    assert accounts.get(SUB) is None
    assert users.deleted == [SUB]
    assert accounts.linked_sub(A) is None


def test_never_deleted_sooner_than_30_days_after_the_warning() -> None:
    accounts.adopt(SUB, A, NOW)
    mail, users = Mail(), Users()
    late_warning = DELETE_AT - dt.timedelta(days=2)  # the job was down for a month
    run(late_warning, mail, users)
    assert "29 December 2028" in mail.sent[0][2] or "30 December 2028" in mail.sent[0][2]
    assert run(DELETE_AT, mail, users)["deleted"] == 0
    assert accounts.get(SUB) is not None
    assert run(late_warning + dt.timedelta(days=30), mail, users)["deleted"] == 1


def test_activity_after_the_warning_keeps_the_account() -> None:
    accounts.adopt(SUB, A, NOW)
    mail, users = Mail(), Users()
    run(WARN_AT, mail, users)
    accounts.touch(SUB, WARN_AT + dt.timedelta(days=3))
    item = meta()
    assert item is not None
    assert "warnedAt" not in item
    assert item["lastActiveMonth"] == "2028-11"
    assert run(DELETE_AT, mail, users)["deleted"] == 0
    assert accounts.get(SUB) is not None


def test_activity_is_written_at_most_once_a_month() -> None:
    accounts.adopt(SUB, A, NOW)
    client = aws.dynamodb()
    calls: list[str] = []

    class Counting:
        def update_item(self, **kwargs: Any) -> object:
            calls.append("update")
            return client.update_item(**kwargs)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(aws, "dynamodb", lambda: Counting())
        # Same month as the one already stored: no write at all.
        accounts.touch(SUB, NOW + dt.timedelta(days=3), known="2026-11")
        assert calls == []
        # A new month: one write.
        accounts.touch(SUB, dt.datetime(2026, 12, 2, tzinfo=UTC), known="2026-11")
        assert calls == ["update"]
    item = meta()
    assert item is not None
    assert item["lastActiveMonth"] == "2026-12"


def test_an_account_being_deleted_is_left_to_the_deletion_job() -> None:
    accounts.adopt(SUB, A, NOW)
    from staysharp.store import deletion

    with pytest.raises(RuntimeError):
        deletion.delete_account(SUB, NOW, lambda _s: (_ for _ in ()).throw(RuntimeError("x")))
    mail, users = Mail(), Users()
    result = run(DELETE_AT, mail, users)
    assert result == {"warned": 0, "deleted": 0, "failed": 0, "unconfirmed": 0}
    assert mail.sent == []


def test_a_failing_e_mail_is_retried_on_the_next_run() -> None:
    accounts.adopt(SUB, A, NOW)
    users = Users()

    def down(_to: str, _subject: str, _text: str) -> None:
        raise RuntimeError("ses down")

    assert (
        inactive.run(WARN_AT, send=down, email_of=users.email, delete_user=users.delete)["failed"]
        == 1
    )
    item = meta()
    assert item is not None
    assert "warnedAt" not in item
    mail = Mail()
    assert run(WARN_AT + dt.timedelta(hours=1), mail, users)["warned"] == 1


def test_unconfirmed_sign_ups_are_removed_after_7_days() -> None:
    removed: list[str] = []
    pending = [
        ("old", NOW - dt.timedelta(days=8)),
        ("fresh", NOW - dt.timedelta(days=6)),
    ]
    count = inactive.remove_unconfirmed(NOW, lambda: pending, removed.append)
    assert count == 1
    assert removed == ["old"]


def test_a_run_stops_when_its_time_is_up_and_the_next_one_goes_on() -> None:
    accounts.adopt(SUB, A, NOW)
    mail, users = Mail(), Users()
    out_of_time = inactive.run(
        WARN_AT, send=mail, email_of=users.email, delete_user=users.delete, budget=dt.timedelta(0)
    )
    assert out_of_time["warned"] == 0
    assert run(WARN_AT + dt.timedelta(hours=1), mail, users)["warned"] == 1


def test_a_month_that_cannot_be_read_is_counted_and_the_others_go_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    accounts.adopt(SUB, A, NOW)
    real = inactive._subs_of  # noqa: SLF001

    def flaky(month: str) -> list[str]:
        if month == "2026-10":
            raise table.StoreError("boom")
        return real(month)

    monkeypatch.setattr(inactive, "_subs_of", flaky)
    result = run(WARN_AT + dt.timedelta(days=31), Mail(), Users())
    assert result["failed"] == 1
    assert result["warned"] == 1
