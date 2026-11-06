"""Player hash and pepper handling (research R3, R16; T039)."""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Iterator
from typing import Any

import pytest

from staysharp import aws, obs

PLAYER = "9f1c2b3a-4d5e-4f60-8a7b-1c2d3e4f5a6b"


@pytest.fixture(autouse=True)
def fresh_pepper() -> Iterator[None]:
    obs.pepper.cache_clear()
    yield
    obs.pepper.cache_clear()


def test_local_stage_uses_the_local_pepper(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STAGE", "local")
    monkeypatch.delenv("PEPPER_SECRET_ARN", raising=False)
    expected = hmac.new(obs.LOCAL_PEPPER, PLAYER.encode(), hashlib.sha256).hexdigest()
    assert obs.player_hash(PLAYER) == expected
    assert PLAYER not in obs.player_hash(PLAYER)


@pytest.mark.parametrize("stage", ["dev", "prod"])
def test_other_stages_refuse_to_run_without_the_secret(
    monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    monkeypatch.setenv("STAGE", stage)
    monkeypatch.delenv("PEPPER_SECRET_ARN", raising=False)
    with pytest.raises(RuntimeError, match="PEPPER_SECRET_ARN"):
        obs.player_hash(PLAYER)


class FakeSecrets:
    def __init__(self, value: Any) -> None:
        self.value = value
        self.calls = 0

    def get_secret_value(self, SecretId: str) -> dict[str, Any]:  # noqa: N803 - boto3 name
        self.calls += 1
        return {"SecretString": self.value}


def test_pepper_is_read_once_per_cold_start(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeSecrets("p" * 48)
    monkeypatch.setenv("STAGE", "prod")
    monkeypatch.setenv("PEPPER_SECRET_ARN", "arn:secret")
    monkeypatch.setattr(aws, "secretsmanager", lambda: fake)
    first = obs.player_hash(PLAYER)
    assert obs.player_hash(PLAYER) == first
    assert obs.player_hash("another") != first
    assert fake.calls == 1


@pytest.mark.parametrize("value", [None, "", "short"])
def test_a_missing_or_short_secret_is_refused(monkeypatch: pytest.MonkeyPatch, value: Any) -> None:
    monkeypatch.setenv("STAGE", "prod")
    monkeypatch.setenv("PEPPER_SECRET_ARN", "arn:secret")
    monkeypatch.setattr(aws, "secretsmanager", lambda: FakeSecrets(value))
    with pytest.raises(RuntimeError, match="pepper"):
        obs.pepper()


def test_account_hash_differs_from_the_player_hash_of_the_same_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STAGE", "local")
    monkeypatch.delenv("PEPPER_SECRET_ARN", raising=False)
    sub = PLAYER
    assert obs.account_hash(sub) != obs.player_hash(sub)
    assert sub not in obs.account_hash(sub)
    assert len(obs.account_hash(sub)) == 64


def test_bound_account_logs_the_hash_only(monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.events import captured_logs
    from tests.pii import pii_found

    monkeypatch.setenv("STAGE", "local")
    monkeypatch.delenv("PEPPER_SECRET_ARN", raising=False)
    with captured_logs() as logs:
        obs.bind_request("req-1")
        obs.bind_account(PLAYER)
        obs.logger.info("account read")
        obs.bind_request("req-2")
        obs.logger.info("next request")
    first, second = logs.lines
    assert obs.account_hash(PLAYER) in first
    assert "account_hash" not in second
    assert pii_found(logs.text) == []


@pytest.mark.parametrize(
    ("text", "found"),
    [
        ("player@example.test signed in", ["e-mail"]),
        ("token eyJhbGciOi.eyJzdWIiOi.c2lnbmF0dXJl", ["jwt"]),
        ("Authorization: Bearer abc", ["bearer"]),
        ("code 123456", ["code"]),
        ("from 192.0.2.1", ["ipv4"]),
        ('{"request_id": "req-1", "account_hash": "ab12"}', []),
    ],
)
def test_the_pii_check_itself(text: str, found: list[str]) -> None:
    from tests.pii import pii_found

    assert pii_found(text) == found
