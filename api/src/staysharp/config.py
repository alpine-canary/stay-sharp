"""Settings read from the environment. Set by CDK in AWS, by ``staysharp.local`` on a laptop."""

from __future__ import annotations

import datetime as dt
import os

STAGES = ("local", "dev", "prod")


def stage() -> str:
    value = os.environ.get("STAGE", "local")
    if value not in STAGES:
        raise RuntimeError(f"unknown STAGE {value!r}")
    return value


def launch_date() -> dt.date:
    """Day of game #1 (spec Assumptions). Required outside ``local``."""
    value = os.environ.get("LAUNCH_DATE")
    if value:
        return dt.date.fromisoformat(value)
    if stage() == "local":
        return LOCAL_LAUNCH_DATE
    raise RuntimeError("LAUNCH_DATE is not set")


# A fixed day for laptops and tests; the real launch day is set per stage in CDK.
LOCAL_LAUNCH_DATE = dt.date(2026, 11, 1)
