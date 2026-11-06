"""A stand-in for the Cognito user pool, for local runs and tests only (T203).

Two parts:

- **Tokens**: ``issue`` signs access tokens shaped like Cognito's (``sub``, ``token_use``,
  ``client_id``, ``exp``); ``verify`` checks them. The real API never verifies tokens itself:
  the API Gateway JWT authorizer does, and the function reads the claims it passes on. Locally
  there is no API Gateway, so ``staysharp.local`` calls ``verify`` and passes the same claims.
  The tokens use HMAC-SHA256 with a fixed local key (no crypto dependency); they are worthless
  anywhere else, and ``staysharp.local`` refuses any stage but ``local``.
- **User pool API**: ``handle`` answers the JSON calls the website makes to Cognito
  (``X-Amz-Target: AWSCognitoIdentityProviderService.<Action>``): sign up without a password,
  confirm, choice-based sign-in (``USER_AUTH``) with an e-mail code, refresh, global sign-out.
  Users live in memory. Every code is ``FAKE_COGNITO_CODE`` (default ``123456``). Set
  ``FAKE_COGNITO_DOWN=1`` to answer 503 to every call (quickstart A14).

Nothing here logs an e-mail address, a code or a token.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

KEY = b"fake-cognito-local-key-not-secret"
CLIENT_ID = "fake-client"
ISSUER = "https://fake-cognito.local/pool"
ACCESS_SECONDS = 3600
DEFAULT_CODE = "123456"
# Pinned user ids keep tests and repeated local runs stable.
_SUB_NAMESPACE = uuid.UUID("5b0b7a1e-6a8e-4bde-9d3e-2f1f6c0a7d11")


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(signing_input: bytes) -> str:
    return _b64(hmac.new(KEY, signing_input, hashlib.sha256).digest())


def sub_for(email: str) -> str:
    return str(uuid.uuid5(_SUB_NAMESPACE, email.strip().lower()))


def issue(
    sub: str,
    *,
    token_use: str = "access",
    client_id: str = CLIENT_ID,
    now: float | None = None,
    lifetime: int = ACCESS_SECONDS,
) -> str:
    issued = int(time.time() if now is None else now)
    header = {"alg": "HS256", "typ": "JWT", "kid": "fake"}
    claims = {
        "sub": sub,
        "iss": ISSUER,
        "client_id": client_id,
        "token_use": token_use,
        "scope": "aws.cognito.signin.user.admin",
        "auth_time": issued,
        "iat": issued,
        "exp": issued + lifetime,
        "jti": uuid.uuid4().hex,
        "username": sub,
    }
    if token_use == "id":
        claims["aud"] = client_id
        del claims["client_id"]
    head = _b64(json.dumps(header, separators=(",", ":")).encode())
    body = _b64(json.dumps(claims, separators=(",", ":")).encode())
    signing_input = f"{head}.{body}".encode()
    return f"{head}.{body}.{_sign(signing_input)}"


def verify(token: str, *, now: float | None = None) -> dict[str, Any] | None:
    """The claims of a valid, unexpired access token for this client, else ``None``.

    The same checks as the API Gateway JWT authorizer: signature, issuer, expiry, client.
    """
    parts = token.split(".")
    if len(parts) != 3:
        return None
    head, body, signature = parts
    if not hmac.compare_digest(_sign(f"{head}.{body}".encode()), signature):
        return None
    try:
        claims: dict[str, Any] = json.loads(_unb64(body))
    except ValueError:
        return None
    current = time.time() if now is None else now
    if claims.get("iss") != ISSUER or claims.get("token_use") != "access":
        return None
    if claims.get("client_id") != CLIENT_ID or float(claims.get("exp", 0)) <= current:
        return None
    if _STATE.revoked_before.get(str(claims.get("sub")), 0) > float(claims.get("iat", 0)):
        return None
    return claims


# --- the user pool API --------------------------------------------------------------------


class CognitoError(Exception):
    def __init__(self, kind: str, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.status = status


@dataclass
class _User:
    sub: str
    confirmed: bool = False


@dataclass
class _State:
    users: dict[str, _User] = field(default_factory=dict)  # by lower-case e-mail
    sessions: dict[str, str] = field(default_factory=dict)  # session -> e-mail
    refresh: dict[str, str] = field(default_factory=dict)  # refresh token -> sub
    # Tokens issued before this time (per sub) are refused: global sign-out, deleted user.
    revoked_before: dict[str, float] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)


_STATE = _State()


def reset() -> None:
    global _STATE
    _STATE = _State()


def _code() -> str:
    return os.environ.get("FAKE_COGNITO_CODE", DEFAULT_CODE)


def _email(params: dict[str, Any]) -> str:
    raw = params.get("Username") or params.get("AuthParameters", {}).get("USERNAME") or ""
    email = str(raw).strip().lower()
    if "@" not in email:
        raise CognitoError("InvalidParameterException", "Invalid username")
    return email


def _client(params: dict[str, Any]) -> None:
    if params.get("ClientId") != CLIENT_ID:
        raise CognitoError("ResourceNotFoundException", "Client not found")


def _new_session(email: str) -> str:
    session = secrets.token_urlsafe(24)
    _STATE.sessions[session] = email
    return session


def _tokens(sub: str, *, with_refresh: bool = True) -> dict[str, Any]:
    # Tokens issued in the same second as a sign-out must still be valid afterwards.
    now = max(time.time(), _STATE.revoked_before.get(sub, 0))
    result: dict[str, Any] = {
        "AccessToken": issue(sub, now=now),
        "IdToken": issue(sub, token_use="id", now=now),
        "ExpiresIn": ACCESS_SECONDS,
        "TokenType": "Bearer",
    }
    if with_refresh:
        refresh = secrets.token_urlsafe(32)
        _STATE.refresh[refresh] = sub
        result["RefreshToken"] = refresh
    return {"AuthenticationResult": result, "ChallengeParameters": {}}


def _sign_up(params: dict[str, Any]) -> dict[str, Any]:
    _client(params)
    email = _email(params)
    if "Password" in params:
        raise CognitoError("InvalidParameterException", "Passwords are not used")
    if email in _STATE.users:
        raise CognitoError("UsernameExistsException", "User already exists")
    user = _User(sub=sub_for(email))
    _STATE.users[email] = user
    return {
        "UserConfirmed": False,
        "UserSub": user.sub,
        "Session": _new_session(email),
        "CodeDeliveryDetails": {"DeliveryMedium": "EMAIL", "AttributeName": "email"},
    }


def _confirm_sign_up(params: dict[str, Any]) -> dict[str, Any]:
    _client(params)
    email = _email(params)
    user = _STATE.users.get(email)
    if user is None or params.get("ConfirmationCode") != _code():
        raise CognitoError("CodeMismatchException", "Invalid code")
    user.confirmed = True
    return {"Session": _new_session(email)}


def _initiate_auth(params: dict[str, Any]) -> dict[str, Any]:
    _client(params)
    flow = params.get("AuthFlow")
    auth = params.get("AuthParameters") or {}
    if flow == "REFRESH_TOKEN_AUTH":
        sub = _STATE.refresh.get(str(auth.get("REFRESH_TOKEN")))
        if sub is None:
            raise CognitoError("NotAuthorizedException", "Invalid refresh token")
        return _tokens(sub, with_refresh=False)
    if flow != "USER_AUTH":
        raise CognitoError("InvalidParameterException", "Unsupported flow")
    email = _email(params)
    user = _STATE.users.get(email)
    # Sign-in right after a confirmed sign-up: the confirm session signs the user in.
    session = params.get("Session")
    if session and _STATE.sessions.pop(str(session), None) == email and user and user.confirmed:
        return _tokens(user.sub)
    if auth.get("PREFERRED_CHALLENGE", "EMAIL_OTP") != "EMAIL_OTP":
        raise CognitoError("InvalidParameterException", "Unsupported challenge")
    # Like a pool that prevents user existence errors: an unknown e-mail gets a challenge too,
    # and no code ever matches it.
    return {
        "ChallengeName": "EMAIL_OTP",
        "Session": _new_session(email),
        "ChallengeParameters": {"CODE_DELIVERY_DELIVERY_MEDIUM": "EMAIL"},
    }


def _respond(params: dict[str, Any]) -> dict[str, Any]:
    _client(params)
    if params.get("ChallengeName") != "EMAIL_OTP":
        raise CognitoError("InvalidParameterException", "Unsupported challenge")
    responses = params.get("ChallengeResponses") or {}
    email = _STATE.sessions.get(str(params.get("Session")))
    user = _STATE.users.get(email or "")
    if email is None:
        raise CognitoError("NotAuthorizedException", "Invalid session for the user.")
    if user is None or not user.confirmed or responses.get("EMAIL_OTP_CODE") != _code():
        raise CognitoError("CodeMismatchException", "Invalid code received for user")
    del _STATE.sessions[str(params.get("Session"))]
    return _tokens(user.sub)


def _global_sign_out(params: dict[str, Any]) -> dict[str, Any]:
    claims = verify(str(params.get("AccessToken", "")))
    if claims is None:
        raise CognitoError("NotAuthorizedException", "Access Token has been revoked")
    sub = str(claims["sub"])
    _STATE.revoked_before[sub] = time.time() + 1
    _STATE.refresh = {token: s for token, s in _STATE.refresh.items() if s != sub}
    return {}


def admin_delete_user(sub: str) -> None:
    """What the delete function does with ``AdminDeleteUser`` (idempotent here)."""
    with _STATE.lock:
        _STATE.users = {e: u for e, u in _STATE.users.items() if u.sub != sub}
        _STATE.revoked_before[sub] = time.time() + 1
        _STATE.refresh = {token: s for token, s in _STATE.refresh.items() if s != sub}


ACTIONS = {
    "SignUp": _sign_up,
    "ConfirmSignUp": _confirm_sign_up,
    "InitiateAuth": _initiate_auth,
    "RespondToAuthChallenge": _respond,
    "GlobalSignOut": _global_sign_out,
}
TARGET_PREFIX = "AWSCognitoIdentityProviderService."


def handle(target: str, body: bytes) -> tuple[int, dict[str, Any]]:
    """Answer one user pool API call: ``(status, JSON body)``, errors shaped like Cognito's."""
    if os.environ.get("FAKE_COGNITO_DOWN") == "1":
        return 503, {"__type": "ServiceUnavailable", "message": "Service unavailable"}
    action = ACTIONS.get(target.removeprefix(TARGET_PREFIX))
    if action is None:
        return 400, {"__type": "UnknownOperationException", "message": "Unknown operation"}
    try:
        params = json.loads(body or b"{}")
        with _STATE.lock:
            return 200, action(params)
    except CognitoError as error:
        return error.status, {"__type": error.kind, "message": error.message}
    except ValueError:
        return 400, {"__type": "SerializationException", "message": "Bad request"}
