"""Run the API on a laptop for front-end work: ``python -m staysharp.local``.

Serves the same resolver as Lambda on http://127.0.0.1:3001 against DynamoDB Local (table
``staysharp-local``; seed it first with ``python -m staysharp.tools.seed --fixtures
--create-table``). The Vite dev server proxies ``/api`` here. Local only: it binds to 127.0.0.1
and refuses any stage but ``local``.

With ``FAKE_COGNITO=1`` it also stands in for the sign-in service (``testing.fake_cognito``):
``GET /auth.json`` points the website at it, ``POST /cognito`` answers the user pool API calls
the website makes, and requests to
``/api/v1/me`` and below need a valid fake access token, whose claims are passed on as the API
Gateway JWT authorizer does (401 without one, before the function runs).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlsplit

HOST = "127.0.0.1"
# One request at a time, like one Lambda container: the resolver holds the current request.
_ONE_AT_A_TIME = threading.Lock()


@dataclass
class LocalContext:
    function_name: str = "staysharp-local-api"
    memory_limit_in_mb: int = 512
    invoked_function_arn: str = "arn:aws:lambda:local:000000000000:function:staysharp-local-api"
    aws_request_id: str = "local"
    function_version: str = "$LATEST"


def to_event(method: str, target: str, headers: dict[str, str], body: bytes) -> dict[str, Any]:
    url = urlsplit(target)
    return {
        "version": "2.0",
        "routeKey": "$default",
        "rawPath": url.path,
        "rawQueryString": url.query,
        "headers": {name.lower(): value for name, value in headers.items()},
        "requestContext": {
            "accountId": "000000000000",
            "apiId": "local",
            "domainName": "localhost",
            "domainPrefix": "localhost",
            "http": {
                "method": method,
                "path": url.path,
                "protocol": "HTTP/1.1",
                "sourceIp": "127.0.0.1",
                "userAgent": headers.get("User-Agent", ""),
            },
            "requestId": uuid.uuid4().hex,
            "routeKey": "$default",
            "stage": "$default",
            "time": "",
            "timeEpoch": 0,
        },
        "body": body.decode() if body else None,
        "isBase64Encoded": False,
    }


ACCOUNT_PREFIX = "/api/v1/me"
COGNITO_PATH = "/cognito"
AUTH_CONFIG_PATH = "/auth.json"


def fake_cognito_on() -> bool:
    return os.environ.get("FAKE_COGNITO") == "1"


def authorize(event: dict[str, Any]) -> bool:
    """What the API Gateway JWT authorizer does for the account routes, with the fake tokens.

    ``True`` when the request may go on (not an account route, or a valid token, whose claims
    are now in the event); ``False`` for a 401.
    """
    if not event["rawPath"].startswith(ACCOUNT_PREFIX):
        return True
    from testing import fake_cognito

    scheme, _, token = event["headers"].get("authorization", "").partition(" ")
    claims = fake_cognito.verify(token) if scheme.lower() == "bearer" else None
    if claims is None:
        return False
    event["requestContext"]["authorizer"] = {
        "jwt": {"claims": {name: str(value) for name, value in claims.items()}, "scopes": None}
    }
    return True


def route(method: str, target: str, headers: dict[str, str], body: bytes) -> dict[str, Any]:
    """One local request to a Lambda-style result (status, headers, body)."""
    if fake_cognito_on() and urlsplit(target).path == AUTH_CONFIG_PATH and method == "GET":
        from testing import fake_cognito

        # What the web stack writes to auth.json in a stage, pointing at the fake.
        config = {"endpoint": COGNITO_PATH, "clientId": fake_cognito.CLIENT_ID}
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json", "Cache-Control": "no-store"},
            "body": json.dumps(config),
        }
    if fake_cognito_on() and urlsplit(target).path == COGNITO_PATH and method == "POST":
        from testing import fake_cognito

        lower = {name.lower(): value for name, value in headers.items()}
        status, answer = fake_cognito.handle(lower.get("x-amz-target", ""), body)
        return {
            "statusCode": status,
            "headers": {"Content-Type": "application/x-amz-json-1.1", "Cache-Control": "no-store"},
            "body": json.dumps(answer),
        }
    event = to_event(method, target, headers, body)
    if fake_cognito_on() and not authorize(event):
        return {
            "statusCode": 401,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"message": "Unauthorized"}),
        }
    from staysharp.handlers import api

    with _ONE_AT_A_TIME:
        result: dict[str, Any] = api.handler(event, LocalContext())
    return result


class Handler(BaseHTTPRequestHandler):
    server_version = "staysharp-local"

    def _serve(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        result = route(self.command, self.path, dict(self.headers.items()), body)
        payload = (result.get("body") or "").encode()
        self.send_response(int(result.get("statusCode", 500)))
        for name, value in (result.get("headers") or {}).items():
            self.send_header(name, str(value))
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    do_GET = _serve  # noqa: N815 - http.server naming
    do_POST = _serve  # noqa: N815
    do_PUT = _serve  # noqa: N815
    do_DELETE = _serve  # noqa: N815

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - base class name
        # Method and path only: no headers, no body.
        sys.stderr.write(json.dumps({"local": f"{self.command} {urlsplit(self.path).path}"}) + "\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local API for front-end work")
    parser.add_argument("--port", type=int, default=3001)
    args = parser.parse_args(argv)

    if os.environ.get("STAGE", "local") != "local":
        print("refused: staysharp.local runs with STAGE=local only", file=sys.stderr)
        return 2
    os.environ["STAGE"] = "local"
    os.environ.setdefault("TABLE_NAME", "staysharp-local")
    os.environ.setdefault("DYNAMODB_ENDPOINT", "http://localhost:8000")
    os.environ.setdefault("AWS_ACCESS_KEY_ID", "local")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "local")
    os.environ.setdefault("AWS_REGION", "eu-central-2")
    os.environ.setdefault("POWERTOOLS_METRICS_DISABLED", "true")

    server = ThreadingHTTPServer((HOST, args.port), Handler)
    print(f"Stay Sharp API on http://{HOST}:{args.port}/api/v1 (table {os.environ['TABLE_NAME']})")
    if fake_cognito_on():
        print(f"Fake sign-in on http://{HOST}:{args.port}{COGNITO_PATH} (every code: 123456)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
