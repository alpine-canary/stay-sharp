"""Reading the caller from the claims the JWT authorizer passes on (T209)."""

from __future__ import annotations

from typing import Any

import pytest

from staysharp.handlers.http import ApiError, caller_sub


def event(claims: dict[str, Any] | None) -> dict[str, Any]:
    context: dict[str, Any] = {"http": {"method": "GET"}}
    if claims is not None:
        context["authorizer"] = {"jwt": {"claims": claims, "scopes": None}}
    return {"requestContext": context}


def test_access_token_gives_the_sub() -> None:
    assert caller_sub(event({"sub": "abc", "token_use": "access"})) == "abc"


@pytest.mark.parametrize(
    "claims",
    [
        None,
        {},
        {"sub": "abc", "token_use": "id"},
        {"token_use": "access"},
        {"sub": "", "token_use": "access"},
    ],
    ids=["no-authorizer", "no-claims", "id-token", "no-sub", "empty-sub"],
)
def test_anything_else_is_401(claims: dict[str, Any] | None) -> None:
    with pytest.raises(ApiError) as caught:
        caller_sub(event(claims))
    assert caught.value.status == 401
    assert caught.value.code == "unauthorized"
