"""Daily stock check (FR-026, research R11, W8).

Run once a day by a schedule. For each level it counts the days in a row, from tomorrow, that
have a complete published set (``STOCK#<level>`` markers, days strictly after today) and emits
``StockDaysAhead`` with the ``Level`` dimension. A gap ends the count: sets next month do not
help if tomorrow has none. The alarm fires below 7 days, and also when no value arrives
(missing data is breaching). Any error is raised: the invocation fails, the on-failure
destination and the error alarm tell the maintainer.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from typing import Any

from staysharp import clock, config
from staysharp.domain import calendar
from staysharp.domain.models import DECKS
from staysharp.metrics import emit
from staysharp.obs import logger, metrics
from staysharp.store import table

__all__ = ["clock", "days_ahead", "emit", "handler", "run", "table"]


def days_ahead(stock_days: Iterable[str], today: dt.date) -> int:
    present = {dt.date.fromisoformat(day) for day in stock_days}
    count = 0
    while today + dt.timedelta(days=count + 1) in present:
        count += 1
    return count


def run() -> dict[str, int]:
    today = calendar.zurich_today(clock.now())
    result: dict[str, int] = {}
    for level in DECKS:
        items = table.query_all(table.stock_query(level, today), limit=400)
        result[level] = days_ahead((str(item["SK"]) for item in items), today)
        emit("StockDaysAhead", result[level], dimension=("Level", level))
    logger.info("stock checked", extra={"today": today.isoformat(), "days_ahead": result})
    return result


@metrics.log_metrics
def handler(event: dict[str, Any], context: Any) -> dict[str, int]:
    del event, context
    metrics.set_default_dimensions(Stage=config.stage())
    return run()
