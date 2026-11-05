"""The Lambda clock in one place, so tests and the local server can set the time.

Only when ``STAGE=local``, ``STAYSHARP_CLOCK_FILE`` may name a file holding an ISO 8601 time with
offset. From the moment the file's content changes, the clock runs from that time at the real
pace. An empty or missing file means the real time. The end-to-end midnight test (T059) uses it;
anywhere else the variable is ignored.
"""

from __future__ import annotations

import datetime as dt
import os
from pathlib import Path

from staysharp import config

_state: dict[str, str] = {}
_offset: list[dt.timedelta] = []


def _fake_offset(path: Path, real: dt.datetime) -> dt.timedelta | None:
    try:
        text = path.read_text().strip()
    except OSError:
        return None
    if not text:
        return None
    if _state.get("text") != text:
        start = dt.datetime.fromisoformat(text)
        if start.tzinfo is None:
            raise ValueError("the clock file must hold a time with an offset")
        _state["text"] = text
        _offset[:] = [start - real]
    return _offset[0]


def now() -> dt.datetime:
    real = dt.datetime.now(dt.UTC)
    name = os.environ.get("STAYSHARP_CLOCK_FILE")
    if not name or config.stage() != "local":
        return real
    offset = _fake_offset(Path(name), real)
    return real if offset is None else real + offset


def reset() -> None:
    _state.clear()
    _offset.clear()
