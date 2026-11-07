"""The sign-in e-mail sender (handlers/mail_sender.py): what it sends, and what it never logs."""

from __future__ import annotations

import logging
from typing import Any

import pytest

from staysharp.handlers import mail_sender


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


def test_a_send_failure_reaches_cognito() -> None:
    def broken(to: str, subject: str, text: str) -> None:
        raise RuntimeError("SES is down")

    with pytest.raises(RuntimeError):
        mail_sender.send_code(event(), fake_decrypt, broken)
