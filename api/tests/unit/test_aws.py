"""Client factory settings (research R8)."""

from typing import Any

import pytest

from staysharp import aws


def test_config_has_short_timeouts_and_limited_retries() -> None:
    config: Any = aws.CONFIG  # botocore stubs do not declare these attributes
    assert config.connect_timeout == 2
    assert config.read_timeout == 3
    assert config.retries == {"mode": "standard", "total_max_attempts": 3}


def test_dynamodb_endpoint_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DYNAMODB_ENDPOINT", "http://localhost:8000")
    monkeypatch.setenv("AWS_REGION", "eu-central-2")
    aws.reset()
    try:
        client = aws.dynamodb()
        assert client.meta.endpoint_url == "http://localhost:8000"
        client_config: Any = client.meta.config
        assert client_config.read_timeout == 3
        assert aws.dynamodb() is client
    finally:
        aws.reset()


def test_default_region_is_zurich(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
    monkeypatch.delenv("DYNAMODB_ENDPOINT", raising=False)
    aws.reset()
    try:
        assert aws.dynamodb().meta.region_name == "eu-central-2"
    finally:
        aws.reset()
