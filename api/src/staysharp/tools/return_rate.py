"""Monthly return rate (task T117, SC-010). Read-only; prints aggregate numbers only.

    AWS_PROFILE=... python -m staysharp.tools.return_rate --month 2026-12 [--stage prod]

- players: players with at least one finished daily dated in that month;
- returning: of those, players with finished dailies on two or more dates in that month;
- challenges: challenge links created in that month;
- challengesFinished: of those, links that led to at least one colleague's finished game.

Plays expire after about 90 days and challenges after about 30, so run it in the first days of
the next month. It scans the table with a projection of keys, dates and counters: no player id
or hash is ever printed or kept.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections import defaultdict
from collections.abc import Iterator, Mapping, Sequence
from typing import Any

from staysharp import aws
from staysharp.store import table

MONTH = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
FINISHED = 5


def _items() -> Iterator[dict[str, Any]]:
    """Plays and challenge headers only, a page at a time."""
    start: Mapping[str, Any] | None = None
    while True:
        kwargs: dict[str, Any] = {
            "TableName": table.table_name(),
            "ProjectionExpression": "PK, SK, #d, #m, answered, results, createdAt",
            "FilterExpression": "begins_with(SK, :play) OR (begins_with(PK, :ch) AND SK = :meta)",
            "ExpressionAttributeNames": {"#d": "date", "#m": "mode"},
            "ExpressionAttributeValues": {
                ":play": {"S": "PLAY#"},
                ":ch": {"S": "CH#"},
                ":meta": {"S": "META"},
            },
        }
        if start:
            kwargs["ExclusiveStartKey"] = start
        page = aws.dynamodb().scan(**kwargs)
        for raw in page.get("Items", []):
            yield table.deserialize(raw)
        start = page.get("LastEvaluatedKey")
        if not start:
            return


def count(month: str) -> dict[str, Any]:
    days_by_player: dict[str, set[str]] = defaultdict(set)
    challenges = finished_challenges = 0
    for item in _items():
        pk = str(item["PK"])
        if pk.startswith("CH#"):
            if str(item.get("createdAt", "")).startswith(month):
                challenges += 1
                if int(item.get("results", 0)) > 0:
                    finished_challenges += 1
            continue
        day = str(item.get("date", ""))
        answered = item.get("answered") or set()
        if item.get("mode") == "daily" and day.startswith(month) and len(answered) == FINISHED:
            days_by_player[pk].add(day)
    return {
        "month": month,
        "players": len(days_by_player),
        "returning": sum(1 for days in days_by_player.values() if len(days) >= 2),
        "challenges": challenges,
        "challengesFinished": finished_challenges,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--month", required=True, help="YYYY-MM")
    parser.add_argument("--stage", default=os.environ.get("STAGE", "prod"))
    args = parser.parse_args(argv)
    if not MONTH.fullmatch(args.month):
        print("refused: --month must be YYYY-MM", file=sys.stderr)
        return 2
    os.environ.setdefault("TABLE_NAME", f"staysharp-{args.stage}")
    result = count(args.month)
    print(
        f"{result['month']}: returning {result['returning']} of {result['players']} players; "
        f"{result['challengesFinished']} of {result['challenges']} challenge links led to a "
        "finished game"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
