"""Leak-guard fingerprints and the public scan (T087, research R4 layer 2, V18).

The fingerprint file holds HMAC-SHA256 digests of normalised 12-word shingles of the prompt,
code, correct choice and explanation of every question scheduled for today or later. Without the
key, the file says nothing about the text. The scan prints paths and counts only.
"""

from __future__ import annotations

import datetime as dt
import json
import subprocess
from pathlib import Path

import pytest

from staysharp.publish import fingerprints, validate
from staysharp.tools import leak_scan

VALID = Path(__file__).resolve().parents[1] / "fixtures" / "publish" / "valid"
KEY = b"test key, never a real one"
TODAY = dt.date(2026, 12, 2)


@pytest.fixture(scope="module")
def prints() -> fingerprints.Fingerprints:
    return fingerprints.build(KEY, validate.load(VALID), today=TODAY)


def explanation(qid: str) -> str:
    content = validate.load(VALID)
    return str(next(q.data["explanation"] for q in content.questions if q.data["id"] == qid))


# --- Normalising and shingles -----------------------------------------------------------------


def test_normalise_ignores_case_punctuation_and_layout() -> None:
    assert fingerprints.normalise("Hello,  WORLD!\n\tit's  `x=1`") == [
        "hello",
        "world",
        "it",
        "s",
        "x",
        "1",
    ]


def test_shingles_are_12_words_long() -> None:
    words = [f"w{i}" for i in range(14)]
    got = list(fingerprints.shingles(words, 12))
    assert len(got) == 3
    assert got[0] == " ".join(words[:12])


def test_a_digest_depends_on_the_key() -> None:
    assert fingerprints.digest(KEY, "a b c") != fingerprints.digest(b"another key", "a b c")
    assert fingerprints.digest(KEY, "a b c") == fingerprints.digest(KEY, "a b c")


# --- Which questions are fingerprinted --------------------------------------------------------


def test_only_questions_of_today_and_later_are_fingerprinted() -> None:
    chosen = {q["id"] for q in fingerprints.scheduled_from(validate.load(VALID), TODAY)}
    assert "sen_news_birch" in chosen  # 2026-12-02, today
    assert "sen_news_amber" not in chosen  # 2026-12-01, past
    assert "sen_fail_draft" not in chosen  # never scheduled
    assert len(chosen) == 10


def test_a_future_explanation_is_matched(prints: fingerprints.Fingerprints) -> None:
    assert fingerprints.Scanner(KEY, prints).count(explanation("sen_news_birch")) > 0


def test_the_file_holds_digests_and_sizes_only(prints: fingerprints.Fingerprints) -> None:
    data = json.loads(prints.to_json())
    assert set(data) == {"version", "sizes", "hashes"}
    text = prints.to_json()
    assert "Fixture" not in text and "birch" not in text
    assert all(len(h) == 32 for h in data["hashes"])


def test_short_texts_are_one_shingle_and_very_short_ones_are_skipped() -> None:
    key_words = "deletes items some time after a timestamp attribute has passed"
    built = fingerprints.from_texts(KEY, [key_words, "time to live"])
    scanner = fingerprints.Scanner(KEY, built)
    assert scanner.count(f"In the docs: {key_words.upper()}.") == 1
    assert scanner.count("time to live") == 0


# --- Scanning ---------------------------------------------------------------------------------


def test_a_file_copying_a_future_prompt_is_matched(prints: fingerprints.Fingerprints) -> None:
    content = validate.load(VALID)
    prompt = next(q.data["prompt"] for q in content.questions if q.data["id"] == "sta_logic_birch")
    copied = f"# notes\n\nSomeone pasted this:\n> {prompt.replace(' ', '   ')}\n"
    assert fingerprints.Scanner(KEY, prints).count(copied) > 0


def test_a_harmless_file_is_not_matched(prints: fingerprints.Fingerprints) -> None:
    readme = (Path(__file__).resolve().parents[3] / "README.md").read_text(encoding="utf-8")
    scanner = fingerprints.Scanner(KEY, prints)
    assert scanner.count(readme) == 0
    assert scanner.count(Path(leak_scan.__file__).read_text(encoding="utf-8")) == 0


def _git(repo: Path, *args: str) -> None:
    subprocess.run(  # noqa: S603
        ["git", "-C", str(repo), *args],  # noqa: S607
        check=True,
        capture_output=True,
        env={
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.invalid",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.invalid",
            "HOME": str(repo),
            "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        },
    )


def test_the_scan_finds_a_copy_in_history_and_prints_paths_and_counts_only(
    tmp_path: Path, prints: fingerprints.Fingerprints, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "README.md").write_text("A harmless file.\n")
    secret = explanation("sen_spot_birch")
    (repo / "notes.md").write_text(f"draft: {secret}\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "one")
    (repo / "notes.md").unlink()
    _git(repo, "commit", "-q", "-am", "two")

    fp = tmp_path / "fingerprints.json"
    fp.write_text(prints.to_json())
    code = leak_scan.scan(repo, KEY, fingerprints.Fingerprints.from_json(fp.read_text()))
    out = capsys.readouterr().out
    assert code == 1
    assert "notes.md (history)" in out
    assert "README.md" not in out
    assert "Fixture" not in out and "sen_spot_birch" not in out


def test_the_scan_passes_a_clean_repository(
    tmp_path: Path, prints: fingerprints.Fingerprints, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "README.md").write_text("A harmless file.\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "one")
    assert leak_scan.scan(repo, KEY, prints) == 0
    assert "no match" in capsys.readouterr().out


def test_the_scan_needs_the_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("LEAK_GUARD_KEY", raising=False)
    fp = tmp_path / "f.json"
    fp.write_text(fingerprints.from_texts(KEY, []).to_json())
    assert leak_scan.main(["--fingerprints", str(fp), "--repo", str(tmp_path)]) == 2


def test_a_deck_instruction_shared_by_several_questions_is_not_guarded() -> None:
    instruction = "Pick the worst line and say what is wrong with it."
    questions = [
        {"prompt": instruction, "explanation": f"Explanation number {n} of a spot question here."}
        for n in (1, 2)
    ] + [{"prompt": "A prompt of its own that only this one question uses.", "explanation": ""}]
    texts = fingerprints.guarded_texts(questions)
    assert instruction not in texts
    assert "A prompt of its own that only this one question uses." in texts
    assert "Explanation number 1 of a spot question here." in texts
    prints = fingerprints.from_texts(KEY, texts)
    assert fingerprints.Scanner(KEY, prints).count(instruction) == 0
