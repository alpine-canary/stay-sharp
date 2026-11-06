"""The API Lambda: one HTTP resolver under ``/api/v1`` (research R8, R10).

Every response carries ``Cache-Control: no-store``. Requests other than ``/health``, ``/today`` and
the account routes need a UUIDv4 ``X-Player-Id``. Bodies over 2 KB are refused, except the
progress copy (``/me/progress``, 64 KB plus its envelope). Account routes (``/me`` and below, M2)
read the caller from the JWT authorizer's claims; of them only ``/me/adopt`` takes a player id.
Validation errors are logged as field names and error types only, never input values. Errors
are JSON ``{code, message}``.

A synthetic ``{"selfcheck": true}`` event (sent by the pre-traffic hook to the new version)
runs the data-free self-check instead of the resolver.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from http import HTTPStatus
from typing import Any

from aws_lambda_powertools.event_handler import APIGatewayHttpResolver, Response
from aws_lambda_powertools.event_handler.middlewares import NextMiddleware
from aws_lambda_powertools.utilities.typing import LambdaContext
from pydantic import ValidationError

from staysharp import config
from staysharp.domain.models import ErrorCode, parse_player_id
from staysharp.handlers import (
    routes_challenges,
    routes_me,
    routes_plays,
    routes_practice,
    routes_today,
)
from staysharp.handlers.http import ApiError, caller_sub, error_response
from staysharp.obs import bind_account, bind_player, bind_request, logger, metrics

PREFIX = "/api/v1"
MAX_BODY_BYTES = 2_048
PUBLIC_PATHS = frozenset({"/health", "/today"})
ACCOUNT_PREFIX = "/me"
PROGRESS_PATH = "/me/progress"
MAX_PROGRESS_BYTES = 72 * 1024
NO_STORE = "no-store"

app = APIGatewayHttpResolver(strip_prefixes=[PREFIX])
app.include_router(routes_today.router)
app.include_router(routes_plays.router)
app.include_router(routes_challenges.router)
app.include_router(routes_practice.router)
app.include_router(routes_me.router)


def _route_path() -> str:
    path = app.current_event.path
    return path[len(PREFIX) :] if path.startswith(PREFIX) else path


def edge_checks(resolver: APIGatewayHttpResolver, next_middleware: NextMiddleware) -> Response[Any]:
    event = resolver.current_event
    bind_request(event.request_context.request_id)
    body = event.decoded_body or ""
    path = _route_path()
    limit = MAX_PROGRESS_BYTES if path == PROGRESS_PATH else MAX_BODY_BYTES
    if len(body.encode()) > limit:
        code: ErrorCode = "too_large" if path == PROGRESS_PATH else "invalid_request"
        raise ApiError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, code, "Request too large.")
    if path == ACCOUNT_PREFIX or path.startswith(ACCOUNT_PREFIX + "/"):
        sub = caller_sub(event.raw_event)
        resolver.append_context(account_sub=sub)
        bind_account(sub)
        return next_middleware(resolver)
    if path not in PUBLIC_PATHS:
        try:
            player_id = parse_player_id(event.headers.get("x-player-id"))
        except ValueError as error:
            raise ApiError(
                HTTPStatus.BAD_REQUEST, "invalid_request", "Missing or invalid player id."
            ) from error
        resolver.append_context(player_id=str(player_id))
        bind_player(str(player_id))
    return next_middleware(resolver)


app.use(middlewares=[edge_checks])


def _request_id() -> str | None:
    try:
        return app.current_event.request_context.request_id
    except (AttributeError, KeyError, TypeError):
        return None


@app.exception_handler(ApiError)
def on_api_error(error: ApiError) -> Response[str]:
    logger.info("request refused", extra={"code": error.code, "status": int(error.status)})
    return error_response(error.status, error.code, error.message, _request_id())


@app.exception_handler(ValidationError)
def on_validation_error(error: ValidationError) -> Response[str]:
    # Field names and error types only: never the submitted values (S3).
    problems = [
        {"field": ".".join(str(p) for p in e["loc"]), "type": e["type"]} for e in error.errors()
    ]
    logger.info("validation failed", extra={"problems": problems})
    fields = ", ".join(sorted({p["field"] for p in problems})) or "body"
    return error_response(
        HTTPStatus.BAD_REQUEST, "invalid_request", f"Invalid fields: {fields}.", _request_id()
    )


@app.not_found
def on_not_found(_: Exception) -> Response[str]:
    return error_response(HTTPStatus.NOT_FOUND, "not_found", "Not found.", _request_id())


@app.exception_handler(Exception)
def on_unexpected(error: Exception) -> Response[str]:
    logger.exception("unexpected error", extra={"error_type": type(error).__name__})
    return error_response(
        HTTPStatus.INTERNAL_SERVER_ERROR,
        "unavailable",
        "Something went wrong on our side. Please try again.",
        _request_id(),
    )


def run_selfcheck() -> dict[str, Any]:
    """Run the bundled self-check (task T075). Until it exists, report failure, never success."""
    try:
        module = importlib.import_module("staysharp.selfcheck")
    except ModuleNotFoundError:
        return {"ok": False, "reason": "self-check not built yet"}
    run: Callable[[], dict[str, Any]] = module.run
    return run()


def _no_store(result: dict[str, Any]) -> dict[str, Any]:
    headers = result.setdefault("headers", {})
    headers["Cache-Control"] = NO_STORE
    return result


@metrics.log_metrics
@logger.inject_lambda_context(log_event=False, clear_state=True)
def handler(event: dict[str, Any], context: LambdaContext) -> dict[str, Any]:
    # The function ARN carries the account id: never in logs (AGENTS.md hard limits).
    logger.remove_keys(["function_arn"])
    if metrics.default_dimensions.get("Stage") != config.stage():
        metrics.set_default_dimensions(Stage=config.stage())
    if event.get("selfcheck") is True:
        return run_selfcheck()
    return _no_store(app.resolve(event, context))
