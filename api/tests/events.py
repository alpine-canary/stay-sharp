"""Build API Gateway HTTP API (payload 2.0) events and call the API handler in-process."""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

PLAYER = "9f1c2b3a-4d5e-4f60-8a7b-1c2d3e4f5a6b"


@dataclass
class FakeContext:
    function_name: str = "staysharp-test-api"
    memory_limit_in_mb: int = 512
    invoked_function_arn: str = (
        "arn:aws:lambda:eu-central-2:000000000000:function:staysharp-test-api:live"
    )
    aws_request_id: str = "req-test"
    function_version: str = "7"


def http_event(
    method: str,
    path: str,
    *,
    body: Any = None,
    player: str | None = PLAYER,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    all_headers = {"content-type": "application/json"}
    if player is not None:
        all_headers["x-player-id"] = player
    all_headers.update(headers or {})
    raw = body if isinstance(body, str) or body is None else json.dumps(body)
    return {
        "version": "2.0",
        "routeKey": "$default",
        "rawPath": path,
        "rawQueryString": "",
        "headers": all_headers,
        "requestContext": {
            "accountId": "000000000000",
            "apiId": "api",
            "domainName": "example.test",
            "domainPrefix": "example",
            "http": {
                "method": method,
                "path": path,
                "protocol": "HTTP/1.1",
                "sourceIp": "192.0.2.1",
                "userAgent": "pytest",
            },
            "requestId": f"req-{uuid.uuid4().hex[:8]}",
            "routeKey": "$default",
            "stage": "$default",
            "time": "20/Nov/2026:08:00:00 +0000",
            "timeEpoch": 1_795_000_000_000,
        },
        "body": raw,
        "isBase64Encoded": False,
    }


def call(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
    from staysharp.handlers import api

    result: dict[str, Any] = api.handler(http_event(method, path, **kwargs), FakeContext())
    return result


def body(result: dict[str, Any]) -> Any:
    return json.loads(result["body"])


class LogCapture(logging.Handler):
    """Collect the API's JSON log lines, formatted exactly as in Lambda."""

    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(self.format(record))

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


@contextmanager
def captured_logs() -> Iterator[LogCapture]:
    from staysharp.obs import logger

    inner: logging.Logger = logger._logger  # noqa: SLF001 - the Powertools logger's own logger
    capture = LogCapture()
    capture.setFormatter(logger.registered_formatter)
    inner.addHandler(capture)
    try:
        yield capture
    finally:
        inner.removeHandler(capture)
