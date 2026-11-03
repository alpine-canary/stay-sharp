"""Day boundary and date rules (research R6, W2). Pure functions, no clock of their own.

"Today" is the calendar day in Europe/Zurich. A play's own date decides streak, freeze week and
share card. A daily play for day D can be answered until the end of D+1; a replay or a challenge
play can be for any past day. A future date is always refused.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from staysharp.domain.models import Mode

ZURICH = ZoneInfo("Europe/Zurich")

__all__ = [
    "ZURICH",
    "Mode",
    "game_number",
    "play_date_allowed",
    "start_date_allowed",
    "week_start",
    "zurich_today",
]


def zurich_today(now: datetime) -> date:
    if now.tzinfo is None:
        raise ValueError("now must carry a time zone")
    return now.astimezone(ZURICH).date()


def game_number(day: date, launch: date) -> int:
    """#1 is the launch day, the same number at every level."""
    if day < launch:
        raise ValueError(f"{day} is before launch ({launch})")
    return (day - launch).days + 1


def week_start(day: date) -> date:
    """Monday of the ISO week (Monday to Sunday) that contains ``day``."""
    return day - timedelta(days=day.weekday())


def start_date_allowed(mode: Mode, play_date: date, today: date, *, challenge: bool) -> bool:
    """May a play for ``play_date`` start today?

    A replay of today is allowed here by date only; the store also checks that the daily play
    of that date and level is finished (C3).
    """
    if play_date > today:
        return False
    if mode == "replay" or challenge:
        return True
    return play_date == today


def play_date_allowed(mode: Mode, play_date: date, today: date, *, challenge: bool) -> bool:
    """May a question of a ``play_date`` play be opened or answered today?"""
    if play_date > today:
        return False
    if mode == "replay" or challenge:
        return True
    return today - play_date <= timedelta(days=1)
