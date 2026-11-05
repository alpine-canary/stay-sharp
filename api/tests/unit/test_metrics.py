"""Only the metric and dimension pairs of R11 can be emitted (T063)."""

from __future__ import annotations

import json

import pytest

from staysharp import metrics
from staysharp.obs import metrics as powertools_metrics


@pytest.fixture(autouse=True)
def clean() -> None:
    powertools_metrics.clear_default_dimensions()
    powertools_metrics.clear_metrics()
    powertools_metrics.set_default_dimensions(Stage="test")


@pytest.mark.parametrize(
    ("name", "dimension"),
    [
        ("AnswersGraded", None),
        ("DuplicateAnswers", None),
        ("PlaysStarted", None),
        ("PlayDurationMs", None),
        ("ScoringFailures", ("FunctionVersion", "7")),
        ("ScoringFailures", ("FunctionVersion", "$LATEST")),
        ("SuspiciouslyFast", ("Deck", "spot")),
        ("SuspiciouslyFast", ("Deck", "aisense")),
        ("StockDaysAhead", ("Level", "starter")),
    ],
)
def test_allowed_pairs(name: str, dimension: tuple[str, str] | None) -> None:
    metrics.emit(name, dimension=dimension)


@pytest.mark.parametrize(
    ("name", "dimension"),
    [
        ("Unknown", None),
        ("AnswersGraded", ("Deck", "spot")),
        ("ScoringFailures", None),
        ("ScoringFailures", ("Deck", "spot")),
        ("SuspiciouslyFast", ("Deck", "cooking")),
        ("SuspiciouslyFast", ("PlayerHash", "abc")),
        ("StockDaysAhead", ("Level", "expert")),
        ("ScoringFailures", ("FunctionVersion", "v7; drop")),
    ],
)
def test_any_other_pair_fails(name: str, dimension: tuple[str, str] | None) -> None:
    with pytest.raises(ValueError):
        metrics.emit(name, dimension=dimension)


def test_a_dimensioned_metric_keeps_the_stage(capsys: pytest.CaptureFixture[str]) -> None:
    metrics.emit("SuspiciouslyFast", dimension=("Deck", "spot"))
    blob = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert blob["Stage"] == "test"
    assert blob["Deck"] == "spot"
    assert blob["SuspiciouslyFast"] == [1.0] or blob["SuspiciouslyFast"] == 1.0
