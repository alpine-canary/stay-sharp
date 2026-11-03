"""Grading rules (FR-004, FR-005, FR-005b, FR-005d, scenario V4)."""

from decimal import Decimal

import pytest

from staysharp.domain import grading
from staysharp.domain.grading import AnswerKey, Submission

RIGHT = "AAAAAAAA"
WRONG = "BBBBBBBB"
SPOT_KEY = AnswerKey(choice_id=RIGHT, lines=frozenset({4, 5}))
PLAIN_KEY = AnswerKey(choice_id=RIGHT, lines=frozenset())


@pytest.mark.parametrize(
    ("submission", "expected"),
    [
        (Submission(RIGHT, 4), Decimal(1)),
        (Submission(RIGHT, 5), Decimal(1)),
        (Submission(RIGHT, 9), Decimal("0.5")),  # right problem, wrong line
        (Submission(RIGHT, None), Decimal("0.5")),
        (Submission(WRONG, 4), Decimal("0.5")),  # right line, wrong problem
        (Submission(WRONG, 9), Decimal(0)),
        (Submission(WRONG, None), Decimal(0)),
    ],
)
def test_spot_the_bug_grades(submission: Submission, expected: Decimal) -> None:
    assert grading.grade("spot", SPOT_KEY, submission) == expected


@pytest.mark.parametrize(
    "deck", ["better", "fail", "acronym", "news", "logic", "readcode", "whatif", "words", "aisense"]
)
def test_other_decks_are_right_or_wrong_only(deck: grading.Deck) -> None:
    assert grading.grade(deck, PLAIN_KEY, Submission(RIGHT, None)) == Decimal(1)
    assert grading.grade(deck, PLAIN_KEY, Submission(WRONG, None)) == Decimal(0)
    # A line sent for a deck without lines changes nothing.
    assert grading.grade(deck, PLAIN_KEY, Submission(WRONG, 3)) == Decimal(0)


@pytest.mark.parametrize(
    ("grade", "relaxed", "elapsed_ms", "target", "bonus"),
    [
        (Decimal(1), False, 1_000, 45, Decimal("0.2")),
        (Decimal(1), False, 45_000, 45, Decimal("0.2")),  # exactly on target
        (Decimal(1), False, 45_001, 45, Decimal(0)),
        (Decimal(1), True, 1_000, 45, Decimal(0)),  # relaxed: never a bonus
        (Decimal("0.5"), False, 1_000, 60, Decimal(0)),  # only a full grade earns it
        (Decimal(0), False, 1_000, 45, Decimal(0)),
    ],
)
def test_speed_bonus(
    grade: Decimal, relaxed: bool, elapsed_ms: int, target: int, bonus: Decimal
) -> None:
    assert (
        grading.speed_bonus(grade, relaxed=relaxed, elapsed_ms=elapsed_ms, target_seconds=target)
        == bonus
    )


@pytest.mark.parametrize(
    ("deck", "grade", "elapsed_ms", "flag"),
    [
        ("better", Decimal(1), 2_999, True),
        ("better", Decimal(1), 3_000, False),
        ("spot", Decimal(1), 4_999, True),
        ("spot", Decimal(1), 5_000, False),
        ("logic", Decimal(1), 4_000, True),
        ("words", Decimal(1), 4_000, False),
        ("better", Decimal(0), 500, False),  # only right answers are counted
        ("spot", Decimal("0.5"), 500, False),
    ],
)
def test_suspiciously_fast_is_a_flag(
    deck: grading.Deck, grade: Decimal, elapsed_ms: int, flag: bool
) -> None:
    assert grading.suspiciously_fast(deck, grade, elapsed_ms) is flag


def test_suspiciously_fast_never_changes_the_grade() -> None:
    result = grading.score(
        "better",
        PLAIN_KEY,
        Submission(RIGHT, None),
        relaxed=False,
        elapsed_ms=100,
        target_seconds=45,
    )
    assert result.grade == Decimal(1)
    assert result.bonus == Decimal("0.2")
    assert result.suspiciously_fast is True


def test_best_day_totals_exactly_six() -> None:
    results = [
        grading.score(
            deck, key, Submission(RIGHT, 4), relaxed=False, elapsed_ms=10_000, target_seconds=20
        )
        for deck, key in [
            ("spot", SPOT_KEY),
            ("better", PLAIN_KEY),
            ("fail", PLAIN_KEY),
            ("acronym", PLAIN_KEY),
            ("news", PLAIN_KEY),
        ]
    ]
    total = grading.day_total(results)
    assert total == Decimal("6.0")
    assert total <= grading.MAX_DAY_TOTAL


def test_day_total_refuses_more_than_five_answers() -> None:
    one = grading.score(
        "better",
        PLAIN_KEY,
        Submission(RIGHT, None),
        relaxed=False,
        elapsed_ms=10_000,
        target_seconds=45,
    )
    with pytest.raises(ValueError, match="at most 5"):
        grading.day_total([one] * 6)


def test_same_input_same_output() -> None:
    first = [
        grading.score(
            "spot", SPOT_KEY, Submission(c, line), relaxed=r, elapsed_ms=e, target_seconds=60
        )
        for c in (RIGHT, WRONG)
        for line in (None, 4, 9)
        for r in (False, True)
        for e in (0, 59_999, 60_000, 60_001)
    ]
    second = [
        grading.score(
            "spot", SPOT_KEY, Submission(c, line), relaxed=r, elapsed_ms=e, target_seconds=60
        )
        for c in (RIGHT, WRONG)
        for line in (None, 4, 9)
        for r in (False, True)
        for e in (0, 59_999, 60_000, 60_001)
    ]
    assert first == second


def test_negative_elapsed_time_is_refused() -> None:
    with pytest.raises(ValueError, match="elapsed"):
        grading.score(
            "better",
            PLAIN_KEY,
            Submission(RIGHT, None),
            relaxed=False,
            elapsed_ms=-1,
            target_seconds=45,
        )
