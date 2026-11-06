"""``DELETE /api/v1/me`` (task T232, FR-114): its own function, the only one allowed to call
Cognito's ``AdminDeleteUser`` (infra/stacks/api_stack.py).

204 only once everything is gone. If a step fails: 503 with ``Retry-After``; the account stays
``deleting`` and a retry, or the job (account_jobs.py), finishes it. Idempotent.
"""

from __future__ import annotations

import json
import os
from http import HTTPStatus
from typing import Any

from staysharp import clock, config
from staysharp.handlers.http import ApiError, caller_sub
from staysharp.obs import bind_account, bind_request, logger
from staysharp.store import deletion

RETRY_AFTER_SECONDS = 5


def delete_user() -> deletion.DeleteUser:
    if config.stage() == "local" and os.environ.get("FAKE_COGNITO") == "1":
        from testing import fake_cognito

        return fake_cognito.admin_delete_user
    return deletion.cognito_delete_user(os.environ["USER_POOL_ID"])


def _answer(status: int, body: dict[str, Any] | None = None, **headers: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "statusCode": status,
        "headers": {"Cache-Control": "no-store", "Content-Type": "application/json", **headers},
    }
    if body is not None:
        result["body"] = json.dumps(body)
    return result


@logger.inject_lambda_context(log_event=False, clear_state=True)
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:  # noqa: ARG001
    logger.remove_keys(["function_arn"])
    request_id = (event.get("requestContext") or {}).get("requestId")
    bind_request(request_id)
    try:
        sub = caller_sub(event)
    except ApiError as error:
        return _answer(error.status, {"code": error.code, "message": error.message})
    bind_account(sub)
    try:
        deletion.delete_account(sub, clock.now(), delete_user())
    except Exception as error:  # noqa: BLE001 - any failure: 503, the work goes on later
        logger.exception(
            "account deletion not finished", extra={"error_type": type(error).__name__}
        )
        return _answer(
            HTTPStatus.SERVICE_UNAVAILABLE,
            {"code": "unavailable", "message": "Not finished yet. Please try again in a minute."},
            **{"Retry-After": str(RETRY_AFTER_SECONDS)},
        )
    logger.info("account deleted")
    return _answer(HTTPStatus.NO_CONTENT)
