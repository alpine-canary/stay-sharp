"""Contract harness: every response is validated against its contract.

M1 routes use ``specs/001-m1-web-app/contracts/openapi.yaml``; the account routes (``/api/v1/me``
and below) use ``specs/002-accounts/contracts/accounts.openapi.yaml``.

Schemas use ``additionalProperties: false``, so a response with an unknown field (for example an
answer field leaking into a question view) fails here.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from openapi_core import OpenAPI
from openapi_core.testing import MockRequest, MockResponse

from tests.events import call

SPECS = Path(__file__).resolve().parents[3] / "specs"
CONTRACT = SPECS / "001-m1-web-app" / "contracts" / "openapi.yaml"
ACCOUNTS_CONTRACT = SPECS / "002-accounts" / "contracts" / "accounts.openapi.yaml"
HOST = "https://stay-sharp.example"


@pytest.fixture(scope="session")
def openapi() -> OpenAPI:
    return OpenAPI.from_file_path(str(CONTRACT))


@pytest.fixture(scope="session")
def accounts_openapi() -> OpenAPI:
    return OpenAPI.from_file_path(str(ACCOUNTS_CONTRACT))


Checked = Callable[..., dict[str, Any]]


@pytest.fixture
def checked(openapi: OpenAPI, accounts_openapi: OpenAPI) -> Checked:
    """Call the API in-process and validate the request and response against the contract."""

    def run(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        result = call(method, path, **kwargs)
        contract = accounts_openapi if path.startswith("/api/v1/me") else openapi
        headers = {"X-Player-Id": kwargs["player"]} if kwargs.get("player") else {}
        if kwargs.get("token"):
            headers["Authorization"] = f"Bearer {kwargs['token']}"
        raw_body = kwargs.get("body")
        request = MockRequest(
            HOST,
            method.lower(),
            path,
            headers=headers,
            data=json.dumps(raw_body).encode() if raw_body is not None else None,
        )
        response = MockResponse(
            result["body"].encode(),
            status_code=result["statusCode"],
            headers=result.get("headers", {}),
            content_type=result.get("headers", {}).get("Content-Type", "application/json"),
        )
        contract.validate_response(request, response)
        assert result["headers"]["Cache-Control"] == "no-store"
        return result

    return run
