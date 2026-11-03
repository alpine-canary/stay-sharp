"""Shared test set-up.

Integration tests need DynamoDB Local (``docker compose up -d dynamodb``). Locally they are
skipped with a clear reason when it is not running; in CI (``CI=true``) a missing DynamoDB Local
is a failure, never a silent skip.
"""

import os
import socket

import pytest

DYNAMODB_LOCAL = ("localhost", 8000)


def _dynamodb_local_up() -> bool:
    try:
        with socket.create_connection(DYNAMODB_LOCAL, timeout=0.5):
            return True
    except OSError:
        return False


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    needs_db = [item for item in items if "integration" in item.keywords]
    if not needs_db or _dynamodb_local_up():
        return
    if os.environ.get("CI") == "true":
        raise pytest.UsageError("DynamoDB Local is not reachable on localhost:8000 in CI")
    skip = pytest.mark.skip(reason="DynamoDB Local not running: docker compose up -d dynamodb")
    for item in needs_db:
        item.add_marker(skip)
