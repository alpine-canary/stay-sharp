"""Temporary storage failures on the answer path (T054, R2, V15).

The transaction is retried up to 3 times with backoff and jitter, then the player gets 503,
``ScoringFailures`` goes up by one, nothing partial is written, and the failure is never read as
a duplicate.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest
from botocore.exceptions import ClientError, ReadTimeoutError

from staysharp import aws
from staysharp.store import answers, table
from tests.events import body
from tests.integration.game import Game, game  # noqa: F401 - fixture

pytestmark = pytest.mark.integration


class Flaky:
    """Wraps the real client; the first ``failures`` transactions raise ``error``."""

    def __init__(self, real: Any, failures: int, error: Exception) -> None:
        self.real = real
        self.failures = failures
        self.error = error
        self.attempts = 0

    def transact_write_items(self, **kwargs: Any) -> Any:
        self.attempts += 1
        if self.attempts <= self.failures:
            raise self.error
        return self.real.transact_write_items(**kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.real, name)


def _cancelled(code: str) -> ClientError:
    return ClientError(
        {
            "Error": {"Code": "TransactionCanceledException", "Message": "cancelled"},
            "CancellationReasons": [{"Code": code}, {"Code": "None"}],
        },
        "TransactWriteItems",
    )


THROTTLED = ClientError(
    {"Error": {"Code": "ThrottlingException", "Message": "slow down"}}, "TransactWriteItems"
)
TIMEOUT = ReadTimeoutError(endpoint_url="http://localhost:8000")


def _install(monkeypatch: pytest.MonkeyPatch, failures: int, error: Exception) -> Flaky:
    flaky = Flaky(aws.dynamodb(), failures, error)
    # Only the answer path sees the flaky client; reads and the fixtures keep the real one.
    monkeypatch.setattr(answers, "aws", SimpleNamespace(dynamodb=lambda: flaky))
    return flaky


def _scoring_failures(out: str) -> list[dict[str, Any]]:
    blobs = [json.loads(line) for line in out.splitlines() if line.startswith("{")]
    return [b for b in blobs if "ScoringFailures" in b]


@pytest.mark.parametrize(
    "error",
    [THROTTLED, TIMEOUT, _cancelled("TransactionConflict"), _cancelled("ThrottlingError")],
    ids=["throttled", "timeout", "conflict", "throttled-in-transaction"],
)
def test_recovers_within_three_attempts(
    game: Game,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
) -> None:
    game.start()
    game.open(0)
    flaky = _install(monkeypatch, 2, error)
    result = game.answer(0, game.right(0))
    assert result["statusCode"] == 200
    assert body(result)["duplicate"] is False
    assert flaky.attempts == 3
    assert body(game.get())["score"] == 1.0


@pytest.mark.parametrize("error", [THROTTLED, TIMEOUT, _cancelled("TransactionConflict")])
def test_gives_up_with_503_and_writes_nothing(
    game: Game,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    error: Exception,
) -> None:
    game.start()
    game.open(0)
    capsys.readouterr()
    flaky = _install(monkeypatch, 99, error)

    result = game.answer(0, game.right(0))
    assert result["statusCode"] == 503
    assert body(result)["code"] == "unavailable"
    assert flaky.attempts == answers.ATTEMPTS

    failures = _scoring_failures(capsys.readouterr().out)
    assert len(failures) == 1
    assert failures[0]["FunctionVersion"] == "7"

    item = table.get(table.answer_key(game.player, game.play_id, 0), consistent=True)
    assert item is not None and "grade" not in item
    state = body(game.get())
    assert state["score"] == 0 and state["grades"][0] is None

    flaky.failures = 0
    retried = game.answer(0, game.right(0))
    assert retried["statusCode"] == 200
    assert body(retried)["duplicate"] is False


def test_backoff_has_jitter_and_a_cap() -> None:
    delays = {answers._backoff(2) for _ in range(50)}  # noqa: SLF001
    assert len(delays) > 1
    assert all(0 <= d <= answers.MAX_DELAY_S for d in delays)
