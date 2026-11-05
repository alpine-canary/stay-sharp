"""The Lambda clock in one place, so tests (and the local server) can set the time.

``STAYSHARP_FAKE_NOW`` (an ISO 8601 time with offset) is honoured only when ``STAGE=local``; the
end-to-end midnight test uses it. Anywhere else the variable is ignored.
"""

from __future__ import annotations

import datetime as dt
import os

from staysharp import config

_offset: dt.timedelta | None = None


def now() -> dt.datetime:
    real = dt.datetime.now(dt.UTC)
    fake = os.environ.get("STAYSHARP_FAKE_NOW")
    if not fake or config.stage() != "local":
        return real
    global _offset  # noqa: PLW0603 - set once: fake time then runs at the real pace
    if _offset is None:
        start = dt.datetime.fromisoformat(fake)
        if start.tzinfo is None:
            raise ValueError("STAYSHARP_FAKE_NOW must carry an offset")
        _offset = start - real
    return real + _offset


def reset() -> None:
    global _offset  # noqa: PLW0603
    _offset = None
