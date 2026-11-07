"""At most 5 code e-mails an hour and 10 a day to one address, 300 an hour in all (FR-117).

Sign-up calls reach Cognito directly, outside the web ACL: these limits keep someone from
sending codes in a loop to an address that never asked, which would also get SES to pause
sending for everyone. Counters are kept under a keyed hash of the address, never the address.
"""

from __future__ import annotations

import datetime as dt

import pytest

from staysharp import aws
from staysharp.store import mail_limits, table
from tests.integration.accounts_world import NOW

pytestmark = pytest.mark.integration

ADDRESS = "Someone@Example.test"


@pytest.fixture(autouse=True)
def local(monkeypatch: pytest.MonkeyPatch, table: str) -> None:  # noqa: F811
    monkeypatch.setenv("STAGE", "local")


def test_five_an_hour_to_one_address() -> None:
    assert [mail_limits.allow(ADDRESS, NOW) for _ in range(6)] == [True] * 5 + [False]
    # The same address in other letters is the same address.
    assert mail_limits.allow("someone@example.test", NOW) is False
    assert mail_limits.allow(ADDRESS, NOW + dt.timedelta(hours=1)) is True


def test_ten_a_day_to_one_address() -> None:
    sent = [mail_limits.allow(ADDRESS, NOW + dt.timedelta(hours=h)) for h in range(12)]
    assert sent == [True] * 10 + [False] * 2
    assert mail_limits.allow(ADDRESS, NOW + dt.timedelta(days=1)) is True


def test_three_hundred_an_hour_in_all(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mail_limits, "ALL_PER_HOUR", 3)
    assert [mail_limits.allow(f"p{i}@example.test", NOW) for i in range(4)] == [True] * 3 + [False]


def test_counters_hold_no_address_and_expire() -> None:
    mail_limits.allow(ADDRESS, NOW)
    items = aws.dynamodb().scan(TableName=table.table_name())["Items"]
    mine = [i for i in items if i["PK"]["S"].startswith("MAIL#")]
    assert mine
    text = str(mine).lower()
    assert "someone" not in text and "example" not in text
    assert all("expiresAt" in i for i in mine)
