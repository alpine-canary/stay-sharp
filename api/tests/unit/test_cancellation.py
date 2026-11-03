"""Classification of a cancelled answer transaction (research R2, W1).

Positions in the transaction: 0 = answer item, 1 = play item, 2 and 3 = challenge items (only on
the fifth answer of a challenge play).
"""

import pytest

from staysharp.domain.cancellation import Outcome, Reason, classify
from staysharp.domain.grading import Submission

SUBMITTED = Submission("AAAAAAAA", 4)
NONE = Reason("None")
CCF = "ConditionalCheckFailed"

GRADED_SAME = {
    "servedAt": "2026-11-20T08:00:00.000Z",
    "grade": 1,
    "choiceId": "AAAAAAAA",
    "line": 4,
}
GRADED_OTHER_CHOICE = {**GRADED_SAME, "choiceId": "BBBBBBBB"}
GRADED_OTHER_LINE = {**GRADED_SAME, "line": 5}
SERVED_ONLY = {"servedAt": "2026-11-20T08:00:00.000Z"}


def test_same_answer_already_graded_is_a_duplicate() -> None:
    assert classify([Reason(CCF, GRADED_SAME), NONE], SUBMITTED) is Outcome.DUPLICATE


def test_same_choice_without_line_matches_a_stored_answer_without_line() -> None:
    stored = {"servedAt": "x", "grade": 1, "choiceId": "AAAAAAAA"}
    assert classify([Reason(CCF, stored), NONE], Submission("AAAAAAAA", None)) is Outcome.DUPLICATE


@pytest.mark.parametrize("stored", [GRADED_OTHER_CHOICE, GRADED_OTHER_LINE])
def test_different_answer_already_graded_is_a_conflict(stored: dict[str, object]) -> None:
    assert classify([Reason(CCF, stored), NONE], SUBMITTED) is Outcome.CONFLICT


@pytest.mark.parametrize("stored", [None, {}, {"grade": 1, "choiceId": "AAAAAAAA"}])
def test_answer_item_missing_or_not_served_means_not_opened(
    stored: dict[str, object] | None,
) -> None:
    assert classify([Reason(CCF, stored), NONE], SUBMITTED) is Outcome.NOT_OPENED


def test_served_and_not_graded_yet_failing_the_condition_is_unknown() -> None:
    # The condition cannot fail on such an item; something else is going on: retry, never guess.
    assert classify([Reason(CCF, SERVED_ONLY), NONE], SUBMITTED) is Outcome.RETRY


@pytest.mark.parametrize(
    "reasons",
    [
        [NONE, NONE, Reason(CCF), NONE],  # result already written for this colleague
        [NONE, NONE, NONE, Reason(CCF)],  # cap of 50 results reached
        [NONE, NONE, Reason(CCF), Reason(CCF)],
    ],
)
def test_only_challenge_items_failing_means_challenge_full(reasons: list[Reason]) -> None:
    assert classify(reasons, SUBMITTED) is Outcome.CHALLENGE_FULL


@pytest.mark.parametrize(
    "code",
    [
        "TransactionConflict",
        "ThrottlingError",
        "ProvisionedThroughputExceeded",
        "ValidationError",
        "Unknown",
    ],
)
def test_temporary_or_unknown_errors_are_retried(code: str) -> None:
    assert classify([Reason(code), NONE], SUBMITTED) is Outcome.RETRY
    assert classify([NONE, Reason(code)], SUBMITTED) is Outcome.RETRY


@pytest.mark.parametrize("code", ["TransactionConflict", "ThrottlingError", "Unknown"])
def test_a_temporary_error_is_never_a_duplicate(code: str) -> None:
    # Even with a matching stored answer, any temporary reason elsewhere wins: retry.
    assert classify([Reason(CCF, GRADED_SAME), Reason(code)], SUBMITTED) is Outcome.RETRY
    assert (
        classify([Reason(CCF, GRADED_SAME), NONE, Reason(code), NONE], SUBMITTED) is Outcome.RETRY
    )


def test_play_item_failing_a_condition_is_unknown() -> None:
    # The play update has no condition (C1); a failure there is unexpected.
    assert classify([NONE, Reason(CCF)], SUBMITTED) is Outcome.RETRY


@pytest.mark.parametrize("reasons", [[], [NONE, NONE]])
def test_no_failing_reason_is_unknown(reasons: list[Reason]) -> None:
    assert classify(reasons, SUBMITTED) is Outcome.RETRY


def test_practice_attempt_has_only_the_answer_item() -> None:
    assert classify([Reason(CCF, GRADED_SAME)], SUBMITTED) is Outcome.DUPLICATE
    assert classify([Reason(CCF, None)], SUBMITTED) is Outcome.NOT_OPENED
