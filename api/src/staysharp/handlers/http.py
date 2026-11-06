"""Response helpers shared by every route: JSON from the models, typed errors."""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

from aws_lambda_powertools.event_handler import Response
from pydantic import BaseModel

from staysharp.domain.models import Error, ErrorCode

JSON = "application/json"


def json_response(model: BaseModel, status: int = HTTPStatus.OK) -> Response[str]:
    """Serialize through the model, so numbers stay numbers and empty fields are left out."""
    return Response(
        status_code=status,
        content_type=JSON,
        body=model.model_dump_json(by_alias=True, exclude_none=True),
    )


def error_response(
    status: int, code: ErrorCode, message: str, request_id: str | None = None
) -> Response[str]:
    return json_response(Error(code=code, message=message, request_id=request_id), status)


class ApiError(Exception):
    """A refusal with a status and a contract error code. The message is shown to players."""

    def __init__(self, status: int, code: ErrorCode, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def caller_sub(raw_event: dict[str, Any]) -> str:
    """The Cognito user id of a request that passed the JWT authorizer (T209).

    API Gateway checks the token (signature, issuer, expiry, client) before the function runs
    and passes its claims in ``requestContext.authorizer.jwt.claims``. Only access tokens are
    accepted: an id token carries the same ``sub`` but is not meant for APIs.
    """
    context = raw_event.get("requestContext") or {}
    claims = ((context.get("authorizer") or {}).get("jwt") or {}).get("claims") or {}
    sub = claims.get("sub")
    if claims.get("token_use") != "access" or not isinstance(sub, str) or not sub:
        raise ApiError(HTTPStatus.UNAUTHORIZED, "unauthorized", "Please sign in again.")
    return sub
