"""The local stand-in for Cognito behaves like the real flow the website uses (T203)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import pytest

from testing import fake_cognito as fc

EMAIL = "Player@Example.test"


@pytest.fixture(autouse=True)
def fresh() -> Iterator[None]:
    fc.reset()
    yield
    fc.reset()


def call(action: str, **params: Any) -> tuple[int, dict[str, Any]]:
    params.setdefault("ClientId", fc.CLIENT_ID)
    return fc.handle(fc.TARGET_PREFIX + action, json.dumps(params).encode())


def sign_up_and_sign_in() -> dict[str, Any]:
    status, up = call("SignUp", Username=EMAIL, UserAttributes=[{"Name": "email", "Value": EMAIL}])
    assert status == 200
    status, confirmed = call(
        "ConfirmSignUp", Username=EMAIL, ConfirmationCode="123456", Session=up["Session"]
    )
    assert status == 200
    status, signed = call(
        "InitiateAuth",
        AuthFlow="USER_AUTH",
        AuthParameters={"USERNAME": EMAIL},
        Session=confirmed["Session"],
    )
    assert status == 200
    result: dict[str, Any] = signed["AuthenticationResult"]
    return result


def test_issued_tokens_verify_and_carry_the_claims() -> None:
    token = fc.issue("sub-1")
    claims = fc.verify(token)
    assert claims is not None
    assert claims["sub"] == "sub-1"
    assert claims["token_use"] == "access"


@pytest.mark.parametrize(
    "token",
    [
        "not-a-token",
        fc.issue("sub-1", token_use="id"),
        fc.issue("sub-1", client_id="other"),
        fc.issue("sub-1", now=0),
    ],
    ids=["garbage", "id-token", "other-client", "expired"],
)
def test_bad_tokens_are_refused(token: str) -> None:
    assert fc.verify(token) is None


def test_a_changed_token_is_refused() -> None:
    head, body, sig = fc.issue("sub-1").split(".")
    assert fc.verify(f"{head}.{body}x.{sig}") is None


def test_sign_up_without_password_then_sign_in() -> None:
    result = sign_up_and_sign_in()
    claims = fc.verify(result["AccessToken"])
    assert claims is not None
    assert claims["sub"] == fc.sub_for(EMAIL)
    assert result["RefreshToken"]


def test_sign_up_with_a_password_is_refused() -> None:
    status, body = call("SignUp", Username=EMAIL, Password="hunter2")
    assert status == 400
    assert body["__type"] == "InvalidParameterException"


def test_returning_player_signs_in_with_an_email_code() -> None:
    sign_up_and_sign_in()
    status, challenge = call(
        "InitiateAuth",
        AuthFlow="USER_AUTH",
        AuthParameters={"USERNAME": EMAIL.upper(), "PREFERRED_CHALLENGE": "EMAIL_OTP"},
    )
    assert status == 200
    assert challenge["ChallengeName"] == "EMAIL_OTP"
    status, signed = call(
        "RespondToAuthChallenge",
        ChallengeName="EMAIL_OTP",
        Session=challenge["Session"],
        ChallengeResponses={"USERNAME": EMAIL, "EMAIL_OTP_CODE": "123456"},
    )
    assert status == 200
    assert fc.verify(signed["AuthenticationResult"]["AccessToken"]) is not None


def test_unknown_email_gets_a_challenge_but_no_code_matches() -> None:
    status, challenge = call(
        "InitiateAuth", AuthFlow="USER_AUTH", AuthParameters={"USERNAME": "nobody@example.test"}
    )
    assert status == 200
    status, body = call(
        "RespondToAuthChallenge",
        ChallengeName="EMAIL_OTP",
        Session=challenge["Session"],
        ChallengeResponses={"USERNAME": "nobody@example.test", "EMAIL_OTP_CODE": "123456"},
    )
    assert (status, body["__type"]) == (400, "CodeMismatchException")


def test_wrong_code_is_refused() -> None:
    sign_up_and_sign_in()
    _, challenge = call("InitiateAuth", AuthFlow="USER_AUTH", AuthParameters={"USERNAME": EMAIL})
    status, body = call(
        "RespondToAuthChallenge",
        ChallengeName="EMAIL_OTP",
        Session=challenge["Session"],
        ChallengeResponses={"USERNAME": EMAIL, "EMAIL_OTP_CODE": "000000"},
    )
    assert (status, body["__type"]) == (400, "CodeMismatchException")


def test_refresh_then_global_sign_out_revokes_everything() -> None:
    result = sign_up_and_sign_in()
    status, refreshed = call(
        "InitiateAuth",
        AuthFlow="REFRESH_TOKEN_AUTH",
        AuthParameters={"REFRESH_TOKEN": result["RefreshToken"]},
    )
    assert status == 200
    assert "RefreshToken" not in refreshed["AuthenticationResult"]
    status, _ = call("GlobalSignOut", AccessToken=result["AccessToken"])
    assert status == 200
    assert fc.verify(result["AccessToken"]) is None
    status, body = call(
        "InitiateAuth",
        AuthFlow="REFRESH_TOKEN_AUTH",
        AuthParameters={"REFRESH_TOKEN": result["RefreshToken"]},
    )
    assert (status, body["__type"]) == (400, "NotAuthorizedException")


def test_deleted_user_tokens_stop_working() -> None:
    result = sign_up_and_sign_in()
    fc.admin_delete_user(fc.sub_for(EMAIL))
    assert fc.verify(result["AccessToken"]) is None
    fc.admin_delete_user(fc.sub_for(EMAIL))  # idempotent


def test_down_answers_503(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_COGNITO_DOWN", "1")
    status, _ = call("SignUp", Username=EMAIL)
    assert status == 503


def test_unknown_action() -> None:
    assert fc.handle("AWSCognitoIdentityProviderService.AdminGetUser", b"{}")[0] == 400
