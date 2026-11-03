"""Contract harness: every response is validated against contracts/openapi.yaml.

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

CONTRACT = (
    Path(__file__).resolve().parents[3] / "specs" / "001-m1-web-app" / "contracts" / "openapi.yaml"
)
HOST = "https://stay-sharp.example"


@pytest.fixture(scope="session")
def openapi() -> OpenAPI:
    return OpenAPI.from_file_path(str(CONTRACT))


Checked = Callable[..., dict[str, Any]]


@pytest.fixture
def checked(openapi: OpenAPI) -> Checked:
    """Call the API in-process and validate the request and response against the contract."""

    def run(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        result = call(method, path, **kwargs)
        headers = {"X-Player-Id": kwargs["player"]} if kwargs.get("player") else {}
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
        openapi.validate_response(request, response)
        assert result["headers"]["Cache-Control"] == "no-store"
        return result

    return run
