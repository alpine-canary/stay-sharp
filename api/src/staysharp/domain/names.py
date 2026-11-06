"""Display names (task T244, data-model.md): 2 to 24 letters, digits, space, _ or -, no link,
no blocked word. The check is on a folded copy, so "AdMiN" and "a d m i n" are caught too."""

from __future__ import annotations

import re
import unicodedata

PATTERN = re.compile(r"^[^\W_]([^\W_]| |_|-)*$")
# Small on purpose: names are shown only to the player and next to their own challenge result.
BLOCKED = ("admin", "staysharp", "lumineth", "moderator", "support", "official")


class BadName(ValueError):
    """Shown to the player as is."""


def _folded(name: str) -> str:
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", plain)


def check(raw: str | None) -> str | None:
    if raw is None:
        return None
    name = " ".join(raw.split())
    if not 2 <= len(name) <= 24:
        raise BadName("A name has 2 to 24 characters.")
    if not PATTERN.fullmatch(name):
        raise BadName("Use letters, digits, spaces, _ or - only.")
    folded = _folded(name)
    if "http" in folded or "www" in folded:
        raise BadName("A name cannot be a link.")
    if any(word in folded for word in BLOCKED):
        raise BadName("Please choose another name.")
    return name
