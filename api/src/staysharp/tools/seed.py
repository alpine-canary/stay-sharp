"""Load fixture content into DynamoDB Local or the dev table. Never prod (research R4, C7).

    python -m staysharp.tools.seed --fixtures [--stage local|dev] [--days 3] [--create-table]

Writes every sample question (``content/samples/``), the practice pool for the prototype days,
and fixture daily sets for each level from yesterday to ``--days`` days ahead, with their stock
markers. Only sample content ever reaches dev: real questions live in the private content
repository and are published to prod only.

``local`` targets DynamoDB Local (``DYNAMODB_ENDPOINT``, default ``http://localhost:8000``) and
table ``staysharp-local``; ``dev`` targets ``staysharp-dev`` with the caller's AWS credentials.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from staysharp import aws
from staysharp.domain import calendar
from staysharp.domain.models import DECKS, DailyItem, DailySet, Deck, Level, Question
from staysharp.store import table
from staysharp.store.questions import daily_set_item, question_item
from staysharp.tools.content import question_files, schedule_files, to_question

ROOT = Path(__file__).resolve().parents[4]
SAMPLES = ROOT / "content" / "samples"
ALLOWED_STAGES = ("local", "dev")
TARGETS: dict[Level, dict[Deck, int]] = {
    "senior": {"spot": 60, "better": 45, "fail": 45, "acronym": 20, "news": 30},
    "starter": {"logic": 60, "readcode": 45, "whatif": 30, "words": 20, "aisense": 30},
}


def load_samples(root: Path) -> list[Question]:
    import yaml  # tool-only dependency, not in the Lambda package

    return [
        to_question(yaml.safe_load(p.read_text(encoding="utf-8"))) for p in question_files(root)
    ]


def load_pool(root: Path, questions: dict[str, Question]) -> list[dict[str, Any]]:
    import yaml

    items: list[dict[str, Any]] = []
    for path in schedule_files(root):
        schedule = yaml.safe_load(path.read_text(encoding="utf-8"))
        for day, qids in schedule["days"].items():
            for qid in qids:
                q = questions[qid]
                k = table.pool_key(q.level, q.deck, dt.date.fromisoformat(day), qid)
                items.append({"PK": k["PK"]["S"], "SK": k["SK"]["S"], "version": q.version})
    return items


def fixture_sets(
    questions: Sequence[Question], first: dt.date, days: int, launch: dt.date
) -> list[DailySet]:
    """One set per level and day, rotating through the samples of each deck."""
    by_deck: dict[Deck, list[Question]] = {}
    for q in sorted(questions, key=lambda q: q.qid):
        by_deck.setdefault(q.deck, []).append(q)
    sets: list[DailySet] = []
    for level, decks in DECKS.items():
        if not all(by_deck.get(deck) for deck in decks):
            continue
        for offset in range(days):
            day = first + dt.timedelta(days=offset)
            items = [
                DailyItem(
                    index=i,
                    deck=deck,
                    qid=by_deck[deck][offset % len(by_deck[deck])].qid,
                    version=1,
                    target_seconds=TARGETS[level][deck],
                )
                for i, deck in enumerate(decks)
            ]
            sets.append(
                DailySet(
                    date=day,
                    level=level,
                    game_number=calendar.game_number(day, launch),
                    items=items,
                )
            )
    return sets


def create_table(name: str) -> None:
    client = aws.dynamodb()
    if name in client.list_tables().get("TableNames", []):
        return
    client.create_table(
        TableName=name,
        BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
        ],
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
    )


def write(items: Sequence[dict[str, Any]]) -> None:
    client = aws.dynamodb()
    name = table.table_name()
    for start in range(0, len(items), 25):
        batch = [{"PutRequest": {"Item": table.serialize(i)}} for i in items[start : start + 25]]
        pending: Any = {name: batch}
        for _ in range(5):
            response = client.batch_write_item(RequestItems=pending)
            pending = response.get("UnprocessedItems") or {}
            if not pending:
                break
        else:
            raise table.StoreError("batch write left unprocessed items after 5 attempts")


def seed(root: Path, *, today: dt.date, days: int, launch: dt.date) -> dict[str, int]:
    questions = {q.qid: q for q in load_samples(root)}
    pool = load_pool(root, questions)
    sets = fixture_sets(list(questions.values()), today - dt.timedelta(days=1), days + 2, launch)
    items: list[dict[str, Any]] = [question_item(q) for q in questions.values()]
    items += pool
    items += [daily_set_item(s) for s in sets]
    for s in sets:
        k = table.stock_key(s.level, s.date)
        items.append({"PK": k["PK"]["S"], "SK": k["SK"]["S"]})
    write(items)
    return {"questions": len(questions), "pool": len(pool), "sets": len(sets)}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--fixtures", action="store_true", required=True)
    parser.add_argument("--stage", default=os.environ.get("STAGE", "local"))
    parser.add_argument("--days", type=int, default=3)
    parser.add_argument("--create-table", action="store_true")
    parser.add_argument("--launch", type=dt.date.fromisoformat, default=None)
    args = parser.parse_args(argv)

    if args.stage not in ALLOWED_STAGES or os.environ.get("STAGE") == "prod":
        print(f"refused: seed only runs against {', '.join(ALLOWED_STAGES)}", file=sys.stderr)
        return 2
    if args.stage == "local":
        os.environ.setdefault("DYNAMODB_ENDPOINT", "http://localhost:8000")
        os.environ.setdefault("AWS_ACCESS_KEY_ID", "local")
        os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "local")
    os.environ.setdefault("TABLE_NAME", f"staysharp-{args.stage}")
    if args.stage == "dev" and os.environ.get("DYNAMODB_ENDPOINT"):
        print("refused: dev must not use DYNAMODB_ENDPOINT", file=sys.stderr)
        return 2
    aws.reset()

    today = calendar.zurich_today(dt.datetime.now(dt.UTC))
    launch = args.launch or today - dt.timedelta(days=1)
    if args.create_table:
        if args.stage != "local":
            print("refused: --create-table is for DynamoDB Local only", file=sys.stderr)
            return 2
        create_table(table.table_name())
    counts = seed(SAMPLES, today=today, days=args.days, launch=launch)
    print(f"seeded {table.table_name()}: {counts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
