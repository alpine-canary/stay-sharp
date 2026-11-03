"""Calendar rules: Zurich day, game number, ISO week, allowed dates (research R6, W2)."""

from datetime import UTC, date, datetime, timedelta

import pytest

from staysharp.domain import calendar

LAUNCH = date(2026, 11, 16)


def utc(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        # Winter time, UTC+1.
        (utc(2026, 1, 10, 22, 59), date(2026, 1, 10)),
        (utc(2026, 1, 10, 23, 0), date(2026, 1, 11)),
        # Spring change on 2026-03-29: 02:00 CET becomes 03:00 CEST.
        (utc(2026, 3, 28, 22, 59), date(2026, 3, 28)),
        (utc(2026, 3, 28, 23, 0), date(2026, 3, 29)),
        (utc(2026, 3, 29, 21, 59), date(2026, 3, 29)),
        (utc(2026, 3, 29, 22, 0), date(2026, 3, 30)),
        # Summer time, UTC+2.
        (utc(2026, 7, 1, 21, 59), date(2026, 7, 1)),
        (utc(2026, 7, 1, 22, 0), date(2026, 7, 2)),
        # Autumn change on 2026-10-25: 03:00 CEST becomes 02:00 CET (a 25-hour day).
        (utc(2026, 10, 24, 22, 0), date(2026, 10, 25)),
        (utc(2026, 10, 25, 22, 59), date(2026, 10, 25)),
        (utc(2026, 10, 25, 23, 0), date(2026, 10, 26)),
    ],
)
def test_zurich_today(now: datetime, expected: date) -> None:
    assert calendar.zurich_today(now) == expected


def test_zurich_today_refuses_a_naive_datetime() -> None:
    with pytest.raises(ValueError, match="time zone"):
        calendar.zurich_today(datetime(2026, 1, 1, 12, 0))  # noqa: DTZ001


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (LAUNCH, 1),
        (LAUNCH + timedelta(days=1), 2),
        (LAUNCH + timedelta(days=364), 365),
        # Across the spring change: counted in days, not hours.
        (date(2027, 3, 28), 133),
        (date(2027, 3, 29), 134),
    ],
)
def test_game_number_counts_days_from_launch(day: date, expected: int) -> None:
    assert calendar.game_number(day, LAUNCH) == expected


def test_game_number_refuses_a_day_before_launch() -> None:
    with pytest.raises(ValueError, match="before launch"):
        calendar.game_number(LAUNCH - timedelta(days=1), LAUNCH)


@pytest.mark.parametrize(
    ("day", "monday"),
    [
        (date(2026, 11, 2), date(2026, 11, 2)),  # Monday
        (date(2026, 11, 8), date(2026, 11, 2)),  # Sunday
        (date(2026, 11, 9), date(2026, 11, 9)),  # next Monday
        (date(2027, 1, 1), date(2026, 12, 28)),  # week across the new year
        (date(2026, 3, 29), date(2026, 3, 23)),  # DST Sunday belongs to its week
    ],
)
def test_week_start_is_iso_monday(day: date, monday: date) -> None:
    assert calendar.week_start(day) == monday


TODAY = date(2026, 11, 20)
YESTERDAY = TODAY - timedelta(days=1)
TOMORROW = TODAY + timedelta(days=1)
LAST_WEEK = TODAY - timedelta(days=7)


@pytest.mark.parametrize(
    ("mode", "play_date", "challenge", "allowed"),
    [
        ("daily", TODAY, False, True),
        ("daily", YESTERDAY, False, False),
        ("daily", TOMORROW, False, False),
        ("daily", LAST_WEEK, True, True),  # a colleague plays a past challenge
        ("daily", TOMORROW, True, False),
        ("replay", TODAY, False, True),  # allowed by date; the store checks the daily is done
        ("replay", LAST_WEEK, False, True),
        ("replay", TOMORROW, False, False),
    ],
)
def test_start_date_allowed(
    mode: calendar.Mode, play_date: date, challenge: bool, allowed: bool
) -> None:
    assert calendar.start_date_allowed(mode, play_date, TODAY, challenge=challenge) is allowed


@pytest.mark.parametrize(
    ("mode", "play_date", "challenge", "allowed"),
    [
        # A daily play can be finished until the end of the next day (play started 23:58).
        ("daily", TODAY, False, True),
        ("daily", YESTERDAY, False, True),
        ("daily", TODAY - timedelta(days=2), False, False),
        ("daily", TOMORROW, False, False),
        ("daily", LAST_WEEK, True, True),
        ("replay", LAST_WEEK, False, True),
        ("replay", TOMORROW, False, False),
    ],
)
def test_play_date_allowed_for_open_and_answer(
    mode: calendar.Mode, play_date: date, challenge: bool, allowed: bool
) -> None:
    assert calendar.play_date_allowed(mode, play_date, TODAY, challenge=challenge) is allowed
