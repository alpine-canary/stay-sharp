"""``DELETE /me`` through its handler: 204, 503 then retry, 401 (T232, A10)."""

from __future__ import annotations

import json

import pytest

from staysharp.handlers import account_delete
from staysharp.store import accounts, deletion
from tests.events import FakeContext, http_event
from tests.integration.accounts_world import NOW, SUB, A

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def local(monkeypatch: pytest.MonkeyPatch, table: str) -> None:  # noqa: F811
    monkeypatch.setenv("STAGE", "local")


def delete(sub: str | None = SUB) -> dict[str, object]:
    return account_delete.handler(
        http_event("DELETE", "/api/v1/me", player=None, sub=sub), FakeContext()
    )


def test_204_only_when_done(monkeypatch: pytest.MonkeyPatch) -> None:
    accounts.adopt(SUB, A, NOW)
    gone: list[str] = []
    monkeypatch.setattr(account_delete, "delete_user", lambda: gone.append)
    result = delete()
    assert result["statusCode"] == 204
    assert result["headers"]["Cache-Control"] == "no-store"  # type: ignore[index]
    assert gone == [SUB]
    assert accounts.get(SUB) is None
    assert delete()["statusCode"] == 204


def test_503_with_retry_after_then_a_retry_finishes(monkeypatch: pytest.MonkeyPatch) -> None:
    accounts.adopt(SUB, A, NOW)

    def down(_: str) -> None:
        raise RuntimeError("cognito down")

    monkeypatch.setattr(account_delete, "delete_user", lambda: down)
    failed = delete()
    assert failed["statusCode"] == 503
    assert failed["headers"]["Retry-After"] == "5"  # type: ignore[index]
    assert json.loads(str(failed["body"]))["code"] == "unavailable"
    monkeypatch.setattr(account_delete, "delete_user", lambda: lambda _sub: None)
    assert delete()["statusCode"] == 204
    assert deletion.stuck(NOW) == []


def test_no_token_401() -> None:
    assert delete(sub=None)["statusCode"] == 401
