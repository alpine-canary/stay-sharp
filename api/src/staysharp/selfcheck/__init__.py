"""Data-free self-check run on a new version before it gets traffic (task T075, research R10, C5).

It grades the bundled fixtures, checks the question view against the allowlist, and runs the
answer path's duplicate handling (R2) against a stubbed DynamoDB client. It reads no table and
writes nothing; its only side effect is the ``SelfCheckFailures`` metric when a check fails.

``run()`` returns ``{"ok": bool, "checks": {name: bool}, "failed": [names]}``. A check that
raises counts as failed and is logged with its error type; nothing is swallowed silently.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Any

from staysharp.domain import cancellation, grading
from staysharp.domain.cancellation import Outcome, Reason
from staysharp.domain.grading import AnswerKey, Submission
from staysharp.domain.models import Question
from staysharp.domain.views import VIEW_FIELDS, question_view

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "questions.json"
NOW = dt.datetime(2026, 1, 1, 12, 0, tzinfo=dt.UTC)


def fixtures() -> dict[str, Question]:
    raw = json.loads(FIXTURES.read_text())
    return {q["qid"]: Question.model_validate(q) for q in raw["questions"]}


def _key(q: Question) -> AnswerKey:
    return AnswerKey(q.answer_choice_id, frozenset(q.answer_lines))


# --- Checks: each returns True or raises -----------------------------------------------------


def check_grading() -> bool:
    qs = fixtures()
    spot, news = qs["selfcheck_spot"], qs["selfcheck_news"]
    wrong = next(c.id for c in spot.choices if c.id != spot.answer_choice_id)
    cases: list[tuple[Question, Submission, bool, int, Decimal, Decimal]] = [
        # question, submission, relaxed, elapsed ms, expected grade, expected bonus
        (spot, Submission(spot.answer_choice_id, 3), False, 10_000, Decimal(1), Decimal("0.2")),
        (spot, Submission(spot.answer_choice_id, 1), False, 10_000, Decimal("0.5"), Decimal(0)),
        (spot, Submission(wrong, 3), False, 10_000, Decimal("0.5"), Decimal(0)),
        (spot, Submission(wrong, 1), False, 10_000, Decimal(0), Decimal(0)),
        (spot, Submission(spot.answer_choice_id, 3), True, 10_000, Decimal(1), Decimal(0)),
        (spot, Submission(spot.answer_choice_id, 3), False, 61_000, Decimal(1), Decimal(0)),
        (news, Submission(news.answer_choice_id, None), False, 30_000, Decimal(1), Decimal("0.2")),
        (news, Submission("FFFFFFFF", None), False, 5_000, Decimal(0), Decimal(0)),
    ]
    for q, submission, relaxed, elapsed, grade, bonus in cases:
        scored = grading.score(
            q.deck,
            _key(q),
            submission,
            relaxed=relaxed,
            elapsed_ms=elapsed,
            target_seconds=60 if q.deck == "spot" else 30,
        )
        if (scored.grade, scored.bonus) != (grade, bonus):
            raise AssertionError(f"{q.qid}: got {scored.grade}/{scored.bonus}")
    return True


def check_view_allowlist() -> bool:
    for q in fixtures().values():
        full = q.model_dump(mode="json", by_alias=True)
        view = question_view(full, index=0, served_at="2026-01-01T12:00:00.000Z", target_seconds=30)
        if not set(view) <= set(VIEW_FIELDS):
            raise AssertionError(
                f"view has fields outside the allowlist: {set(view) - set(VIEW_FIELDS)}"
            )
        text = json.dumps(view)
        for secret in (q.explanation, "answerChoiceId", "answerLines", "explanation", "source"):
            if secret in text:
                raise AssertionError(f"view of {q.qid} reveals {secret[:20]!r}")
    return True


def check_classification() -> bool:
    sub = Submission("AAAAAAAA", 3)
    graded = {"servedAt": "x", "grade": Decimal(1), "choiceId": "AAAAAAAA", "line": Decimal(3)}
    table = [
        ([Reason("ConditionalCheckFailed", graded), Reason("None")], Outcome.DUPLICATE),
        (
            [Reason("ConditionalCheckFailed", {**graded, "choiceId": "BBBBBBBB"}), Reason("None")],
            Outcome.CONFLICT,
        ),
        ([Reason("ConditionalCheckFailed", None), Reason("None")], Outcome.NOT_OPENED),
        ([Reason("ConditionalCheckFailed", {"servedAt": "x"}), Reason("None")], Outcome.RETRY),
        ([Reason("TransactionConflict"), Reason("None")], Outcome.RETRY),
        ([Reason("ConditionalCheckFailed", graded), Reason("ThrottlingError")], Outcome.RETRY),
        (
            [Reason("None"), Reason("None"), Reason("ConditionalCheckFailed")],
            Outcome.CHALLENGE_FULL,
        ),
    ]
    for reasons, expected in table:
        got = cancellation.classify(reasons, sub)
        if got is not expected:
            raise AssertionError(f"expected {expected}, got {got}")
    return True


class _StubDynamoDB:
    """Answers every transaction with a cancellation carrying the stored answer (ALL_OLD)."""

    def __init__(self, stored: dict[str, Any]) -> None:
        self.stored = stored
        self.calls = 0

    def transact_write_items(self, **_: Any) -> Any:
        from botocore.exceptions import ClientError

        self.calls += 1
        response: Any = {
            "Error": {"Code": "TransactionCanceledException", "Message": "stub"},
            "CancellationReasons": [
                {"Code": "ConditionalCheckFailed", "Item": self.stored},
                {"Code": "None"},
            ],
        }
        raise ClientError(response, "TransactWriteItems")


def check_answer_path() -> bool:
    """The real answer function and a stub: same answer is a duplicate, another a conflict."""
    from staysharp.store import answers
    from staysharp.store.plays import Play, PlayRef

    spot = fixtures()["selfcheck_spot"]
    play = Play(
        ref=PlayRef(NOW.date(), "senior", "daily"),
        game_number=1,
        relaxed=False,
        relaxed_from=None,
        started_at=NOW,
        expires_at=0,
    )
    served = answers.Served(
        index=0,
        qid=spot.qid,
        version=1,
        deck="spot",
        target_seconds=60,
        served_at=NOW,
    )
    stored = {
        "qid": {"S": spot.qid},
        "version": {"N": "1"},
        "deck": {"S": "spot"},
        "targetSeconds": {"N": "60"},
        "servedAt": {"S": "2026-01-01T12:00:00.000Z"},
        "choiceId": {"S": spot.answer_choice_id},
        "line": {"N": "3"},
        "grade": {"N": "1"},
        "bonus": {"N": "0.2"},
        "elapsedMs": {"N": "5000"},
    }
    same = Submission(spot.answer_choice_id, 3)
    other = Submission("BBBBBBBB", 3)
    for submission, expected in ((same, Outcome.DUPLICATE), (other, Outcome.CONFLICT)):
        stub = _StubDynamoDB(stored)
        result = answers.answer(
            "selfcheck",
            play,
            served,
            submission,
            _key(spot),
            NOW,
            client=stub,
            table_name="selfcheck",
        )
        if result.outcome is not expected or stub.calls != 1:
            raise AssertionError(f"expected {expected} after one call, got {result.outcome}")
    return True


CHECKS: dict[str, Callable[[], bool]] = {
    "grading": check_grading,
    "view_allowlist": check_view_allowlist,
    "classification": check_classification,
    "answer_path": check_answer_path,
}


def run() -> dict[str, Any]:
    from staysharp import metrics
    from staysharp.obs import logger

    results: dict[str, bool] = {}
    for name, check in CHECKS.items():
        try:
            results[name] = check() is True
        except Exception as error:  # noqa: BLE001 - every failure is recorded and reported below
            logger.error(
                "self-check failed", extra={"check": name, "error_type": type(error).__name__}
            )
            results[name] = False
    failed = [name for name, ok in results.items() if not ok]
    if failed:
        metrics.emit("SelfCheckFailures")
    return {"ok": not failed, "checks": results, "failed": failed}
