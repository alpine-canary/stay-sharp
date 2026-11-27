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


def test_scoring_failures_also_per_stage_for_paging(capsys: pytest.CaptureFixture[str]) -> None:
    metrics.emit("ScoringFailures", dimension=("FunctionVersion", "7"))
    powertools_metrics.flush_metrics()
    blobs = [
        json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith("{")
    ]
    dimension_sets = [
        sorted(d)
        for b in blobs
        if "ScoringFailures" in b
        for d in b["_aws"]["CloudWatchMetrics"][0]["Dimensions"]
    ]
    assert ["FunctionVersion", "Stage"] in dimension_sets
    assert ["Stage"] in dimension_sets


def test_no_service_dimension_even_with_the_lambda_variable(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Alarms match exact dimension sets: Powertools must not add "service" (fault drill V8)."""
    monkeypatch.setenv("POWERTOOLS_SERVICE_NAME", "staysharp")
    metrics.emit("AnswersGraded")
    metrics.emit("ScoringFailures", dimension=("FunctionVersion", "7"))
    powertools_metrics.flush_metrics()
    blobs = [
        json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith("{")
    ]
    dimension_sets = [
        d for b in blobs for m in b["_aws"]["CloudWatchMetrics"] for d in m["Dimensions"]
    ]
    assert dimension_sets
    assert all("service" not in d for d in dimension_sets), dimension_sets


# --- Campaign source (2026-11): aggregate counts per network, never per player -----------------


@pytest.mark.parametrize("source", sorted(metrics.SOURCES))
def test_by_source_metrics_take_an_allowed_source(source: str) -> None:
    for name in metrics.BY_SOURCE:
        metrics.emit(f"{name}BySource", dimension=("Source", source))


@pytest.mark.parametrize("source", ["facebook", "LinkedIn", "", "x; drop", "a" * 200])
def test_an_unknown_source_is_refused(source: str) -> None:
    with pytest.raises(ValueError):
        metrics.emit("PlaysStartedBySource", dimension=("Source", source))


def test_counted_emits_the_total_and_the_source(capsys: pytest.CaptureFixture[str]) -> None:
    metrics.counted("PlaysStarted", "linkedin")
    powertools_metrics.flush_metrics()
    blobs = [json.loads(line) for line in capsys.readouterr().out.strip().splitlines()]
    by_source = [b for b in blobs if "PlaysStartedBySource" in b]
    assert [b["Source"] for b in by_source] == ["linkedin"]
    assert any("PlaysStarted" in b and "Source" not in b for b in blobs)


def test_counted_without_a_source_emits_the_total_only(capsys: pytest.CaptureFixture[str]) -> None:
    metrics.counted("PlaysStarted", None)
    powertools_metrics.flush_metrics()
    out = capsys.readouterr().out
    assert "PlaysStarted" in out
    assert "BySource" not in out
