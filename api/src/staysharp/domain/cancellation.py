"""Classify a cancelled answer transaction (research R2, W1). Pure: no AWS import.

Transaction positions: 0 = the answer item (the only one whose condition makes an answer
once-only), 1 = the play item (no condition), 2 and later = challenge items, only on the fifth
answer of a challenge play. A practice attempt has position 0 only.

Rule of thumb: any reason that is not ``None`` or ``ConditionalCheckFailed`` means "temporary or
unknown", and that wins over everything else. A temporary error is never read as a duplicate.
"""

from __future__ import annotations

import enum
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from staysharp.domain.grading import Submission

CONDITION_FAILED = "ConditionalCheckFailed"
NO_REASON = "None"
ANSWER_POSITION = 0
CHALLENGE_FROM = 2


class Outcome(enum.Enum):
    DUPLICATE = "duplicate"  # 200 with the stored result, duplicate: true
    CONFLICT = "conflict"  # 409 with the stored result
    NOT_OPENED = "not_opened"  # 400 invalid_request
    CHALLENGE_FULL = "challenge_full"  # retry once without the challenge items
    RETRY = "retry"  # temporary or unknown: retry with backoff, then 503


@dataclass(frozen=True)
class Reason:
    """One entry of ``CancellationReasons``; ``item`` is the deserialized ``ALL_OLD`` item."""

    code: str
    item: Mapping[str, Any] | None = None


def _same_answer(stored: Mapping[str, Any], submitted: Submission) -> bool:
    stored_line = stored.get("line")
    return stored.get("choiceId") == submitted.choice_id and (
        (None if stored_line is None else int(stored_line)) == submitted.line
    )


def classify(reasons: Sequence[Reason], submitted: Submission) -> Outcome:
    codes = [reason.code for reason in reasons]
    if any(code not in (NO_REASON, CONDITION_FAILED) for code in codes):
        return Outcome.RETRY
    failed = {i for i, code in enumerate(codes) if code == CONDITION_FAILED}
    if not failed:
        return Outcome.RETRY

    if ANSWER_POSITION in failed:
        if failed != {ANSWER_POSITION}:
            return Outcome.RETRY
        stored = reasons[ANSWER_POSITION].item
        if not stored or "servedAt" not in stored:
            return Outcome.NOT_OPENED
        if "grade" not in stored:
            return Outcome.RETRY
        return Outcome.DUPLICATE if _same_answer(stored, submitted) else Outcome.CONFLICT

    if all(i >= CHALLENGE_FROM for i in failed):
        return Outcome.CHALLENGE_FULL
    return Outcome.RETRY
