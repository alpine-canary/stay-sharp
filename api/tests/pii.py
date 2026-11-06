"""Patterns that must never appear in a log line (FR-117, T208, T247)."""

from __future__ import annotations

import re

PATTERNS = {
    "e-mail": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "jwt": re.compile(r"eyJ[\w-]+\.[\w-]+\.[\w-]+"),
    "bearer": re.compile(r"(?i)bearer\s+\S+"),
    "uuid": re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"),
    "ipv4": re.compile(r"\b\d{1,3}(\.\d{1,3}){3}\b"),
    "code": re.compile(r"\b\d{6}\b"),
}


def pii_found(text: str) -> list[str]:
    """The names of the patterns found in ``text`` (empty when clean)."""
    return sorted(name for name, pattern in PATTERNS.items() if pattern.search(text))
