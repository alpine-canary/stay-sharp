"""The publish command: stage guards and output with ids and counts only (T089, C7)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from staysharp.tools import publish

VALID = Path(__file__).resolve().parents[1] / "fixtures" / "publish" / "valid"


def test_validate_offline_accepts_the_valid_batch(capsys: pytest.CaptureFixture[str]) -> None:
    assert publish.main(["validate", str(VALID)]) == 0
    assert capsys.readouterr().out == "ok: 22 questions, 4 scheduled days\n"


def test_validate_prints_ids_and_reasons_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    content = tmp_path / "content"
    shutil.copytree(VALID, content)
    path = content / "questions" / "senior" / "sen_spot_amber.yaml"
    path.write_text(path.read_text().replace("  - 4\n", "  - 9\n"))
    assert publish.main(["validate", str(content)]) == 1
    err = capsys.readouterr().err
    assert "sen_spot_amber: answer line outside the code (5 lines)" in err
    assert "Fixture" not in err


def test_dev_takes_fixture_content_only(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    content = tmp_path / "content"
    shutil.copytree(VALID, content)
    assert publish.main(["apply", str(content), "--stage", "dev"]) == 2
    assert "dev only takes fixture content" in capsys.readouterr().err


def test_prod_never_takes_fixture_content(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    content = tmp_path / "content"
    shutil.copytree(VALID, content)
    (content / publish.FIXTURES_MARKER).write_text("")
    assert publish.main(["apply", str(content), "--stage", "prod"]) == 2
    assert "prod never takes fixture content" in capsys.readouterr().err


def test_a_remote_stage_refuses_a_local_endpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DYNAMODB_ENDPOINT", "http://localhost:8000")
    content = tmp_path / "content"
    shutil.copytree(VALID, content)
    (content / publish.FIXTURES_MARKER).write_text("")
    with pytest.raises(publish.Refusal, match="must not use DYNAMODB_ENDPOINT"):
        publish.check_target("dev", content)
