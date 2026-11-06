"""Display name rules (T244)."""

import pytest

from staysharp.domain import names


@pytest.mark.parametrize(
    ("raw", "kept"),
    [("Ann", "Ann"), ("  Zoë   K ", "Zoë K"), ("dev_42-x", "dev_42-x"), (None, None)],
)
def test_good_names(raw: str | None, kept: str | None) -> None:
    assert names.check(raw) == kept


@pytest.mark.parametrize(
    "raw", ["A", "x" * 25, "a<b>", "-dash", "www.example", "httpfoo", "AdMiN", "Lumi-neth team"]
)
def test_refused_names(raw: str) -> None:
    with pytest.raises(names.BadName):
        names.check(raw)
