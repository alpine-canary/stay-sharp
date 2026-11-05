"""Public leak scan (research R4 layer 2, FR-024b, SC-002a, V18).

    LEAK_GUARD_KEY=... python -m staysharp.tools.leak_scan --fingerprints FILE [--repo DIR]

Looks for the fingerprints of every question scheduled for today or later in every tracked file
and in every blob of the full git history (all refs). Prints file paths and match counts only,
never text. Exit codes: 0 clean, 1 match found, 2 usage error (no key, bad file).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections.abc import Iterator, Sequence
from pathlib import Path

from staysharp.publish.fingerprints import Fingerprints, Scanner

MAX_BLOB = 2_000_000  # bytes; larger blobs are build output, not authored text
_GIT = "git"


def _git(repo: Path, *args: str, stdin: bytes | None = None) -> bytes:
    return subprocess.run(  # noqa: S603
        [_GIT, "-C", str(repo), *args], input=stdin, capture_output=True, check=True
    ).stdout


def tracked_blobs(repo: Path) -> dict[str, str]:
    """blob id -> path for every file in the index."""
    blobs: dict[str, str] = {}
    for entry in _git(repo, "ls-files", "-s", "-z").split(b"\0"):
        if not entry:
            continue
        meta, path = entry.split(b"\t", 1)
        blobs.setdefault(meta.split()[1].decode(), path.decode(errors="replace"))
    return blobs


def history_blobs(repo: Path) -> dict[str, str]:
    """blob id -> one path it had, for every blob reachable from any ref."""
    paths: dict[str, str] = {}
    for line in _git(repo, "rev-list", "--all", "--objects").decode(errors="replace").splitlines():
        sha, _, path = line.partition(" ")
        if path:
            paths.setdefault(sha, path)
    if not paths:
        return {}
    checks = _git(
        repo,
        "cat-file",
        "--batch-check=%(objectname) %(objecttype)",
        stdin="\n".join(paths).encode(),
    )
    blobs = {
        sha: paths[sha]
        for sha, kind in (line.split() for line in checks.decode().splitlines())
        if kind == "blob"
    }
    return blobs


def read_blobs(repo: Path, shas: Sequence[str]) -> Iterator[tuple[str, bytes]]:
    if not shas:
        return
    out = _git(repo, "cat-file", "--batch", stdin="\n".join(shas).encode())
    pos = 0
    while pos < len(out):
        end = out.index(b"\n", pos)
        sha, _kind, size = out[pos:end].decode().split()
        start = end + 1
        stop = start + int(size)
        yield sha, out[start:stop]
        pos = stop + 1


def _text(data: bytes) -> str | None:
    if len(data) > MAX_BLOB or b"\0" in data[:8000]:
        return None
    return data.decode("utf-8", errors="replace")


def scan(repo: Path, key: bytes, prints: Fingerprints) -> int:
    scanner = Scanner(key, prints)
    tracked = tracked_blobs(repo)
    history = history_blobs(repo)
    everything = {**history, **tracked}
    hits: list[tuple[str, int]] = []
    for sha, data in read_blobs(repo, sorted(everything)):
        text = _text(data)
        if text is None:
            continue
        found = scanner.count(text)
        if found:
            label = tracked[sha] if sha in tracked else f"{history[sha]} (history)"
            hits.append((label, found))
    counted = f"{len(tracked)} tracked files and {len(everything)} blobs in history"
    if not hits:
        print(f"leak scan: no match in {counted}")
        return 0
    print(f"leak scan: FUTURE QUESTION TEXT FOUND in {len(hits)} file(s) ({counted})")
    for label, found in sorted(hits):
        print(f"  {label}: {found} matching shingle(s)")
    return 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Public leak scan (R4 layer 2).")
    parser.add_argument("--fingerprints", type=Path, required=True)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    key = os.environ.get("LEAK_GUARD_KEY", "")
    if not key:
        print("refused: LEAK_GUARD_KEY is not set", file=sys.stderr)
        return 2
    try:
        prints = Fingerprints.from_json(args.fingerprints.read_text(encoding="utf-8"))
    except (OSError, ValueError, KeyError) as error:
        print(f"refused: unreadable fingerprint file ({type(error).__name__})", file=sys.stderr)
        return 2
    return scan(args.repo, key.encode(), prints)


if __name__ == "__main__":
    sys.exit(main())
