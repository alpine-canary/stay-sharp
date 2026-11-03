"""The seed tool refuses prod (research R4, C7)."""

import pytest

from staysharp.tools import seed


def test_refuses_stage_prod(capsys: pytest.CaptureFixture[str]) -> None:
    assert seed.main(["--fixtures", "--stage", "prod"]) == 2
    assert "refused" in capsys.readouterr().err


def test_refuses_when_the_environment_says_prod(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STAGE", "prod")
    assert seed.main(["--fixtures", "--stage", "dev"]) == 2


def test_dev_refuses_a_local_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STAGE", raising=False)
    monkeypatch.setenv("DYNAMODB_ENDPOINT", "http://localhost:8000")
    assert seed.main(["--fixtures", "--stage", "dev"]) == 2


def test_fixtures_flag_is_required() -> None:
    with pytest.raises(SystemExit):
        seed.main(["--stage", "local"])
