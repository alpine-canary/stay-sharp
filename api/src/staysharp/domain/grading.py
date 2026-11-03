"""Server-side grading (FR-004 to FR-005d). Deterministic and pure.

Numbers are ``Decimal`` so that sums stay exact (0.2 has no exact binary float) and map directly
to DynamoDB numbers.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from staysharp.domain.models import LINE_DECKS, Deck

__all__ = [
    "BONUS",
    "MAX_DAY_TOTAL",
    "AnswerKey",
    "Deck",
    "Scored",
    "Submission",
    "day_total",
    "grade",
    "score",
    "speed_bonus",
    "suspiciously_fast",
]

FULL = Decimal(1)
HALF = Decimal("0.5")
ZERO = Decimal(0)
BONUS = Decimal("0.2")
MAX_DAY_TOTAL = Decimal("6.0")

# FR-005d: right answers faster than this are counted, never penalised.
FAST_MS_DEFAULT = 3_000
FAST_MS_SLOW_DECKS = 5_000
SLOW_DECKS: frozenset[Deck] = frozenset({"spot", "logic"})


@dataclass(frozen=True)
class AnswerKey:
    choice_id: str
    lines: frozenset[int]


@dataclass(frozen=True)
class Submission:
    choice_id: str
    line: int | None


@dataclass(frozen=True)
class Scored:
    grade: Decimal
    bonus: Decimal
    suspiciously_fast: bool


def grade(deck: Deck, key: AnswerKey, submission: Submission) -> Decimal:
    choice_right = submission.choice_id == key.choice_id
    if deck not in LINE_DECKS:
        return FULL if choice_right else ZERO
    line_right = submission.line is not None and submission.line in key.lines
    if choice_right and line_right:
        return FULL
    if choice_right or line_right:
        return HALF
    return ZERO


def speed_bonus(grade_: Decimal, *, relaxed: bool, elapsed_ms: int, target_seconds: int) -> Decimal:
    if grade_ == FULL and not relaxed and elapsed_ms <= target_seconds * 1_000:
        return BONUS
    return ZERO


def suspiciously_fast(deck: Deck, grade_: Decimal, elapsed_ms: int) -> bool:
    if grade_ != FULL:
        return False
    limit = FAST_MS_SLOW_DECKS if deck in SLOW_DECKS else FAST_MS_DEFAULT
    return elapsed_ms < limit


def score(
    deck: Deck,
    key: AnswerKey,
    submission: Submission,
    *,
    relaxed: bool,
    elapsed_ms: int,
    target_seconds: int,
) -> Scored:
    if elapsed_ms < 0:
        raise ValueError("elapsed time cannot be negative")
    g = grade(deck, key, submission)
    return Scored(
        grade=g,
        bonus=speed_bonus(g, relaxed=relaxed, elapsed_ms=elapsed_ms, target_seconds=target_seconds),
        suspiciously_fast=suspiciously_fast(deck, g, elapsed_ms),
    )


def day_total(results: Sequence[Scored]) -> Decimal:
    if len(results) > 5:
        raise ValueError("a day has at most 5 answers")
    return sum((r.grade + r.bonus for r in results), ZERO)
