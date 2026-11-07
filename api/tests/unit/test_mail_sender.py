"""The sign-in e-mail sender (handlers/mail_sender.py): what it sends, and what it never logs."""

from __future__ import annotations

import logging
from typing import Any

import pytest

from staysharp.handlers import mail_sender
from staysharp.store import mail_limits
from tests.events import FakeContext


def event(source: str = "CustomEmailSender_Authentication", **request: object) -> dict[str, Any]:
    return {
        "triggerSource": source,
        "request": {
            "type": "customEmailSenderRequestV1",
            "code": "ZW5jcnlwdGVk",
            "userAttributes": {"email": "player@example.com", "sub": "abc"},
            **request,
        },
    }


class Outbox:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []

    def __call__(self, to: str, subject: str, text: str) -> None:
        self.sent.append((to, subject, text))


def fake_decrypt(encrypted: str) -> str:
    assert encrypted == "ZW5jcnlwdGVk"
    return "246810"


@pytest.mark.parametrize(
    "source",
    [
        "CustomEmailSender_SignUp",
        "CustomEmailSender_ResendCode",
        "CustomEmailSender_Authentication",
        "CustomEmailSender_UpdateUserAttribute",
        "CustomEmailSender_VerifyUserAttribute",
    ],
)
def test_sends_the_decrypted_code_to_the_player(source: str) -> None:
    outbox = Outbox()
    assert mail_sender.send_code(event(source), fake_decrypt, outbox) is True
    [(to, subject, text)] = outbox.sent
    assert to == "player@example.com"
    assert subject == "Your Stay Sharp code"
    assert "246810" in text


@pytest.mark.parametrize(
    "source",
    [
        "CustomEmailSender_ForgotPassword",
        "CustomEmailSender_AdminCreateUser",
        "CustomEmailSender_AccountTakeOverNotification",
        "",
    ],
)
def test_sends_nothing_for_events_this_pool_never_uses(source: str) -> None:
    outbox = Outbox()
    assert mail_sender.send_code(event(source), fake_decrypt, outbox) is False
    assert outbox.sent == []


def test_sends_nothing_without_a_code_or_an_address() -> None:
    outbox = Outbox()
    assert mail_sender.send_code(event(code=None), fake_decrypt, outbox) is False
    assert mail_sender.send_code(event(userAttributes={}), fake_decrypt, outbox) is False
    assert outbox.sent == []


def test_logs_never_hold_the_address_or_the_code(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    mail_sender.send_code(event(), fake_decrypt, Outbox())
    logged = caplog.text + " ".join(str(r.__dict__) for r in caplog.records)
    for secret in ("player@example.com", "246810", "ZW5jcnlwdGVk"):
        assert secret not in logged


def test_a_send_failure_reaches_cognito_without_the_address(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def broken(to: str, subject: str, text: str) -> None:
        raise RuntimeError(f"not authorized on identity/{to}")

    caplog.set_level(logging.DEBUG)
    with pytest.raises(mail_sender.SendFailed) as raised:
        mail_sender.send_code(event(), fake_decrypt, broken)
    assert "player@example.com" not in str(raised.value)
    assert raised.value.__cause__ is None
    assert raised.value.__suppress_context__ is True
    logged = caplog.text + " ".join(str(r.__dict__) for r in caplog.records)
    assert "player@example.com" not in logged
    assert "RuntimeError" in logged


def test_nothing_is_sent_over_the_limit_and_the_log_says_so_without_the_address(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    outbox = Outbox()
    asked: list[str] = []

    def over(address: str) -> bool:
        asked.append(address)
        return False

    assert mail_sender.send_code(event(), fake_decrypt, outbox, over) is False
    assert outbox.sent == []
    assert asked == ["player@example.com"]
    assert "sign-in e-mail limited" in caplog.text
    assert "player@example.com" not in caplog.text


def test_the_handler_counts_every_send(monkeypatch: pytest.MonkeyPatch) -> None:
    outbox = Outbox()
    counted: list[str] = []
    monkeypatch.setattr(mail_sender, "kms_decrypt", lambda: fake_decrypt)
    monkeypatch.setattr(mail_sender, "ses_send", outbox)

    def over(address: str, _now: object) -> bool:
        counted.append(address)
        return False

    monkeypatch.setattr(mail_limits, "allow", over)
    mail_sender.handler(event(), FakeContext())
    assert counted == ["player@example.com"]
    assert outbox.sent == []
