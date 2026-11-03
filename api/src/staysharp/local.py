"""Run the API on a laptop for front-end work: ``python -m staysharp.local``.

Serves the same resolver as Lambda on http://127.0.0.1:3001 against DynamoDB Local (table
``staysharp-local``; seed it first with ``python -m staysharp.tools.seed --fixtures
--create-table``). The Vite dev server proxies ``/api`` here. Local only: it binds to 127.0.0.1
and refuses any stage but ``local``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlsplit

HOST = "127.0.0.1"


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


class Handler(BaseHTTPRequestHandler):
    server_version = "staysharp-local"

    def _serve(self) -> None:
        from staysharp.handlers import api

        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        event = to_event(self.command, self.path, dict(self.headers.items()), body)
        result = api.handler(event, LocalContext())
        payload = (result.get("body") or "").encode()
        self.send_response(int(result.get("statusCode", 500)))
        for name, value in (result.get("headers") or {}).items():
            self.send_header(name, str(value))
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    do_GET = _serve  # noqa: N815 - http.server naming
    do_POST = _serve  # noqa: N815

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
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
