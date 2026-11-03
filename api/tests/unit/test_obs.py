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
