"""SMTP while SMTP_HOST is set, SES otherwise (staysharp.mail)."""

from __future__ import annotations

import json
import smtplib
import ssl
from collections.abc import Iterator
from email.message import EmailMessage
from typing import Any

import pytest

from staysharp import aws, mail


class FakeSmtp:
    opened: list[FakeSmtp] = []

    def __init__(self, host: str, port: int, *, timeout: float, context: ssl.SSLContext) -> None:
        self.host, self.port, self.timeout, self.context = host, port, timeout, context
        self.logins: list[tuple[str, str]] = []
        self.sent: list[EmailMessage] = []
        FakeSmtp.opened.append(self)

    def __enter__(self) -> FakeSmtp:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def login(self, username: str, password: str) -> None:
        self.logins.append((username, password))

    def send_message(self, message: EmailMessage) -> None:
        self.sent.append(message)


class FakeSecrets:
    def __init__(self) -> None:
        self.reads: list[str] = []

    def get_secret_value(self, SecretId: str) -> dict[str, str]:  # noqa: N803 - boto3 name
        self.reads.append(SecretId)
        return {"SecretString": json.dumps({"username": "box@example.org", "password": "pw"})}


class FakeSes:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def send_email(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[FakeSecrets, FakeSes]]:
    secrets, ses = FakeSecrets(), FakeSes()
    FakeSmtp.opened = []
    monkeypatch.setenv("SENDER", "stay-sharp@lumineth.com")
    monkeypatch.setattr(aws, "secretsmanager", lambda: secrets)
    monkeypatch.setattr(aws, "sesv2", lambda: ses)
    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSmtp)
    mail.smtp_login.cache_clear()
    yield secrets, ses
    mail.smtp_login.cache_clear()


def test_ses_when_no_smtp_host(
    env: tuple[FakeSecrets, FakeSes], monkeypatch: pytest.MonkeyPatch
) -> None:
    secrets, ses = env
    monkeypatch.delenv("SMTP_HOST", raising=False)
    mail.send_mail("player@example.com", "Your Stay Sharp code", "Your code is 123456.\n")
    assert len(ses.calls) == 1
    assert ses.calls[0]["FromEmailAddress"] == "Stay Sharp <stay-sharp@lumineth.com>"
    assert not FakeSmtp.opened
    assert not secrets.reads


def test_smtp_over_tls_with_the_mailbox_login(
    env: tuple[FakeSecrets, FakeSes], monkeypatch: pytest.MonkeyPatch
) -> None:
    secrets, ses = env
    monkeypatch.setenv("SMTP_HOST", "smtp.example.net")
    monkeypatch.setenv("SMTP_SECRET_ID", "staysharp/smtp")
    mail.send_mail("player@example.com", "Your Stay Sharp code", "Your code is 123456.\n")
    mail.send_mail("other@example.com", "Your Stay Sharp code", "Your code is 654321.\n")

    assert not ses.calls
    assert secrets.reads == ["staysharp/smtp"]  # read once per instance
    first, second = FakeSmtp.opened
    assert (first.host, first.port) == ("smtp.example.net", 465)
    assert first.timeout == mail.SMTP_TIMEOUT
    assert first.context.verify_mode == ssl.CERT_REQUIRED
    assert first.context.check_hostname
    assert first.logins == [("box@example.org", "pw")]
    (message,) = first.sent
    assert message["From"] == "Stay Sharp <stay-sharp@lumineth.com>"
    assert message["To"] == "player@example.com"
    assert message["Subject"] == "Your Stay Sharp code"
    assert message["Message-ID"].endswith("@lumineth.com>")
    assert message["Date"]
    assert message.get_content_type() == "text/plain"
    assert message.get_content() == "Your code is 123456.\n"
    assert second.sent[0]["To"] == "other@example.com"
