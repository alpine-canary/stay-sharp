"""Leak-guard fingerprints (research R4 layer 2, FR-024b, SC-002a).

The private content CI builds a file of ``HMAC-SHA256(K, shingle)`` digests for every question
scheduled for today or a later day: shingles of 12 normalised words from the prompt, the code,
the correct choice and the explanation. A text shorter than 12 words counts as one shingle of its
own length if it has at least 6 words; shorter texts are too common to match safely. The public
CI downloads the file and looks for the same digests in every tracked file and in the full git
history. Without ``K`` (an Actions secret) the file reveals nothing but a count.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import re
import unicodedata
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from staysharp.publish.validate import Content

SHINGLE = 12
MIN_WORDS = 6
DIGEST_CHARS = 32  # 128 bits are plenty to avoid chance matches
_WORD = re.compile(r"[a-z0-9]+")


def normalise(text: str) -> list[str]:
    """Lower case words of letters and digits; everything else separates words."""
    folded = unicodedata.normalize("NFKC", text).casefold()
    return _WORD.findall(folded)


def shingles(words: Sequence[str], size: int) -> Iterator[str]:
    for start in range(len(words) - size + 1):
        yield " ".join(words[start : start + size])


def digest(key: bytes, shingle: str) -> str:
    return hmac.new(key, shingle.encode(), hashlib.sha256).hexdigest()[:DIGEST_CHARS]


@dataclass(frozen=True)
class Fingerprints:
    sizes: frozenset[int]
    hashes: frozenset[str]

    def to_json(self) -> str:
        return json.dumps(
            {"version": 1, "sizes": sorted(self.sizes), "hashes": sorted(self.hashes)},
            separators=(",", ":"),
        )

    @classmethod
    def from_json(cls, text: str) -> Fingerprints:
        data = json.loads(text)
        if data.get("version") != 1:
            raise ValueError("unknown fingerprint file version")
        sizes = frozenset(int(n) for n in data["sizes"])
        if not sizes <= set(range(MIN_WORDS, SHINGLE + 1)):
            raise ValueError("unexpected shingle sizes")
        return cls(sizes, frozenset(str(h) for h in data["hashes"]))


def from_texts(key: bytes, texts: Iterable[str]) -> Fingerprints:
    sizes: set[int] = set()
    hashes: set[str] = set()
    for text in texts:
        words = normalise(text)
        if len(words) >= SHINGLE:
            sizes.add(SHINGLE)
            hashes.update(digest(key, s) for s in shingles(words, SHINGLE))
        elif len(words) >= MIN_WORDS:
            sizes.add(len(words))
            hashes.add(digest(key, " ".join(words)))
    return Fingerprints(frozenset(sizes), frozenset(hashes))


def scheduled_from(content: Content, today: dt.date) -> list[Mapping[str, Any]]:
    """Questions scheduled for ``today`` or a later day."""
    wanted: set[str] = set()
    for schedule in content.schedules:
        for day, qids in schedule.data.get("days", {}).items():
            if dt.date.fromisoformat(day) >= today:
                wanted.update(qids)
    return [q.data for q in content.questions if q.data.get("id") in wanted]


def secret_texts(question: Mapping[str, Any]) -> list[str]:
    texts = [str(question.get("prompt", "")), str(question.get("explanation", ""))]
    if question.get("code"):
        texts.append(str(question["code"]))
    choices = question.get("choices") or []
    answer = question.get("answer") or {}
    correct = answer.get("choice")
    if isinstance(correct, int) and 0 <= correct < len(choices):
        texts.append(str(choices[correct]))
    return texts


def build(key: bytes, content: Content, *, today: dt.date) -> Fingerprints:
    texts = [t for q in scheduled_from(content, today) for t in secret_texts(q)]
    return from_texts(key, texts)


class Scanner:
    """Counts the shingles of a text that are in the fingerprint file."""

    def __init__(self, key: bytes, prints: Fingerprints) -> None:
        self._inner = hmac.new(key, digestmod=hashlib.sha256)
        self.prints = prints

    def _digest(self, shingle: str) -> str:
        h = self._inner.copy()
        h.update(shingle.encode())
        return h.hexdigest()[:DIGEST_CHARS]

    def count(self, text: str) -> int:
        if not self.prints.hashes:
            return 0
        words = normalise(text)
        found = 0
        for size in self.prints.sizes:
            found += sum(1 for s in shingles(words, size) if self._digest(s) in self.prints.hashes)
        return found
