"""The only way code emits a metric (research R11, W9).

Each metric has exactly one allowed extra dimension (or none). Anything else raises, so a new
dimension cannot slip in and multiply the metric series (and the bill) by accident. ``Stage`` is
added to everything by the handler.
"""

from __future__ import annotations

from aws_lambda_powertools.metrics import MetricUnit, single_metric

from staysharp.domain.models import DECKS
from staysharp.obs import metrics

COUNT = MetricUnit.Count
MILLISECONDS = MetricUnit.Milliseconds

# metric name -> (unit, allowed extra dimension or None)
ALLOWED: dict[str, tuple[MetricUnit, str | None]] = {
    "ScoringFailures": (COUNT, "FunctionVersion"),
    "AnswersGraded": (COUNT, None),
    "DuplicateAnswers": (COUNT, None),
    "SuspiciouslyFast": (COUNT, "Deck"),
    "PlaysStarted": (COUNT, None),
    "PlaysFinished": (COUNT, None),
    "PlayDurationMs": (MILLISECONDS, None),
    "ChallengesCreated": (COUNT, None),
    "ChallengesOpened": (COUNT, None),
    "ChallengesFinished": (COUNT, None),
    "StockDaysAhead": (COUNT, "Level"),
    # Accounts (M2): deletions still not finished an hour after they were asked (FR-114).
    "StuckAccountDeletions": (COUNT, None),
    "SelfCheckFailures": (COUNT, None),
    # Dev only: emitted by api/testing/fault_injection.py while injection is on (W11).
    "FaultInjectionActive": (COUNT, None),
}

# Also emitted with ``Stage`` alone, so the paging alarm sums over versions (R10, FR-028).
ALSO_PER_STAGE = frozenset({"ScoringFailures"})

_DECKS = frozenset(deck for decks in DECKS.values() for deck in decks)
_LEVELS = frozenset(DECKS)


def _check_value(dimension: str, value: str) -> None:
    if dimension == "Deck" and value not in _DECKS:
        raise ValueError(f"unknown deck {value!r}")
    if dimension == "Level" and value not in _LEVELS:
        raise ValueError(f"unknown level {value!r}")
    if dimension == "FunctionVersion" and not (value == "$LATEST" or value.isdigit()):
        raise ValueError(f"unexpected function version {value!r}")


def emit(name: str, value: float = 1, *, dimension: tuple[str, str] | None = None) -> None:
    """Record ``value`` for ``name``; ``dimension`` must be the one R11 allows for it."""
    if name not in ALLOWED:
        raise ValueError(f"metric {name!r} is not in R11")
    unit, allowed = ALLOWED[name]
    given = dimension[0] if dimension else None
    if given != allowed:
        raise ValueError(f"metric {name!r} takes dimension {allowed!r}, not {given!r}")
    if dimension is None:
        metrics.add_metric(name=name, unit=unit, value=value)
        return
    _check_value(*dimension)
    if name in ALSO_PER_STAGE:
        metrics.add_metric(name=name, unit=unit, value=value)
    with single_metric(
        name=name,
        unit=unit,
        value=value,
        namespace=metrics.namespace,
        default_dimensions=metrics.default_dimensions,
    ) as metric:
        metric.service = ""  # single_metric reads POWERTOOLS_SERVICE_NAME on its own
        metric.add_dimension(name=dimension[0], value=dimension[1])
