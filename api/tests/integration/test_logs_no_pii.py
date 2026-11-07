"""No personal data in any log (T247, FR-117).

The whole account life runs through the real handlers, with the logs captured exactly as Lambda
writes them (JSON lines), plus anything printed to stdout or stderr: sign-up code e-mail,
account creation, display name, progress, the inactivity warning, the hourly job and the
deletion. None of the e-mail address, the display name, the code, the token or the caller's IP
address may appear anywhere.
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any

import pytest

from staysharp import clock
from staysharp.handlers import account_delete, account_jobs, mail_sender
from staysharp.store import accounts, inactive
from tests.events import FakeContext, call, captured_logs, http_event
from tests.integration.accounts_world import NOW
from tests.integration.conftest import ddb, table  # noqa: F401 - fixtures

pytestmark = pytest.mark.integration

SUB = "3b9f0c1e-0000-4000-8000-00000000beef"
A = "11111111-1111-4111-8111-111111111111"
EMAIL = "ada.private@example.test"
NAME = "Ada Quietname"
CODE = "834271"
TOKEN = "eyJraWQiOiJzZWNyZXQtdG9rZW4tdmFsdWUifQ.payload.signature"
IP = "192.0.2.1"  # the sourceIp of every test event (tests/events.py)

SECRETS = (EMAIL, NAME, CODE, TOKEN, IP, "ada.private")


@pytest.fixture(autouse=True)
def world(monkeypatch: pytest.MonkeyPatch, table: str) -> None:  # noqa: F811
    monkeypatch.setenv("STAGE", "local")
    monkeypatch.setenv("FAKE_COGNITO", "1")
    monkeypatch.setattr(clock, "now", lambda: NOW)


def me(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
    headers = {"authorization": f"Bearer {TOKEN}"}
    return call(method, path, sub=SUB, headers=headers, **kwargs)


def test_an_account_life_leaves_no_personal_data_in_logs(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    sent: list[tuple[str, str, str]] = []
    with captured_logs() as logs:
        # The sign-up code e-mail (Cognito's custom sender).
        event = {
            "triggerSource": "CustomEmailSender_SignUp",
            "request": {"code": "encrypted", "userAttributes": {"email": EMAIL}},
        }
        monkeypatch.setattr(mail_sender, "kms_decrypt", lambda: lambda _c: CODE)
        monkeypatch.setattr(mail_sender, "ses_send", lambda *a: sent.append(a))
        mail_sender.handler(event, FakeContext())

        # Account, name, progress.
        assert me("POST", "/api/v1/me/adopt", player=A, body={"adult": True})["statusCode"] in (
            200,
            201,
        )
        assert me("PUT", "/api/v1/me", player=None, body={"displayName": NAME})["statusCode"] == 200
        assert me("GET", "/api/v1/me/progress", player=None)["statusCode"] == 200
        # A refused request logs too: make sure it does not echo the input.
        me("PUT", "/api/v1/me", player=None, body={"displayName": f"www.{EMAIL}"})

        # Two years later: the warning, then the hourly job, then the deletion.
        later = NOW + dt.timedelta(days=760)
        inactive.run(
            later,
            send=lambda *a: sent.append(a),
            email_of=lambda _s: EMAIL,
            delete_user=lambda _s: None,
        )
        monkeypatch.setattr(clock, "now", lambda: later)
        monkeypatch.setattr(account_jobs, "email_of", lambda: lambda _s: EMAIL)
        monkeypatch.setattr(account_jobs, "ses_send", lambda *a: sent.append(a))
        account_jobs.run()
        monkeypatch.setattr(account_delete, "delete_user", lambda: lambda _s: None)
        headers = {"authorization": f"Bearer {TOKEN}"}
        result = account_delete.handler(
            http_event("DELETE", "/api/v1/me", player=None, sub=SUB, headers=headers),
            FakeContext(),
        )
        assert result["statusCode"] == 204
        assert accounts.get(SUB) is None

    printed = capsys.readouterr()
    everything = "\n".join([logs.text, printed.out, printed.err, caplog.text])
    assert logs.lines, "the handlers logged nothing: the capture is not working"
    assert sent, "no e-mail went out: the flow did not run"
    leaked = [secret for secret in SECRETS if secret in everything]
    assert leaked == []
