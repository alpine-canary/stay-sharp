"""Publish command for the private content repository (Story 7, research R4).

    python -m staysharp.tools.publish validate CONTENT [--stage local|dev|prod]
    python -m staysharp.tools.publish apply CONTENT --stage local|dev|prod [--dry-run]

``validate`` works offline; with ``--stage`` it also reads the stored versions, so an edit
without a new ``change_reason`` is caught before the merge. ``apply`` validates, plans and
writes, all or nothing. Output is counts and ``id: reason`` lines only, never question text.

Stages: ``local`` is DynamoDB Local. ``dev`` only accepts a fixtures folder (a ``.fixtures`` file
at its root): real questions never reach dev (C7). ``prod`` refuses a fixtures folder. Outside
``local`` the launch day comes from ``--launch`` or ``LAUNCH_DATE``.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from staysharp import aws, clock, config
from staysharp.domain import calendar
from staysharp.publish import apply, validate

FIXTURES_MARKER = ".fixtures"
STAGES = ("local", "dev", "prod")


class Refusal(Exception):  # noqa: N818
    pass


def check_target(stage: str, content: Path) -> None:
    fixtures = (content / FIXTURES_MARKER).is_file()
    if stage == "dev" and not fixtures:
        raise Refusal(f"dev only takes fixture content (a {FIXTURES_MARKER} file at the root)")
    if stage == "prod" and fixtures:
        raise Refusal("prod never takes fixture content")
    if stage != "local" and os.environ.get("DYNAMODB_ENDPOINT"):
        raise Refusal(f"{stage} must not use DYNAMODB_ENDPOINT")


def use_stage(stage: str) -> None:
    if stage == "local":
        os.environ.setdefault("DYNAMODB_ENDPOINT", "http://localhost:8000")
        os.environ.setdefault("AWS_ACCESS_KEY_ID", "local")
        os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "local")
    os.environ["TABLE_NAME"] = f"staysharp-{stage}"
    os.environ["STAGE"] = stage
    aws.reset()


def _print_problems(problems: Sequence[validate.Problem]) -> None:
    print(f"refused: {len(problems)} problem(s), nothing written", file=sys.stderr)
    for problem in problems:
        print(f"  {problem.id}: {problem.reason}", file=sys.stderr)


def run_validate(content: Path, stage: str | None) -> int:
    batch = validate.load(content)
    existing = {}
    if stage is not None:
        check_target(stage, content)
        use_stage(stage)
        existing = apply.latest_versions(
            q.data["id"] for q in batch.questions if isinstance(q.data.get("id"), str)
        )
    problems = validate.validate(batch, existing=existing)
    if problems:
        _print_problems(problems)
        return 1
    days = sum(len(s.data["days"]) for s in batch.schedules)
    print(f"ok: {len(batch.questions)} questions, {days} scheduled days")
    return 0


def run_apply(content: Path, stage: str, *, launch: dt.date | None, dry_run: bool) -> int:
    check_target(stage, content)
    use_stage(stage)
    first = launch or config.launch_date()
    now = clock.now()
    today = calendar.zurich_today(now)
    batch = validate.load(content)
    try:
        result = apply.plan(batch, today=today, launch=first, now=now)
    except apply.Refused as refused:
        _print_problems(refused.problems)
        return 1
    if not dry_run:
        apply.write(result)
    verb = "would write" if dry_run else "written"
    print(f"{verb} to staysharp-{stage} (today {today.isoformat()}): {result.counts()}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="publish", description="Publish questions (R4).")
    sub = parser.add_subparsers(dest="command", required=True)
    v = sub.add_parser("validate", help="check a content folder, write nothing")
    v.add_argument("content", type=Path)
    v.add_argument("--stage", choices=STAGES)
    a = sub.add_parser("apply", help="validate and write, all or nothing")
    a.add_argument("content", type=Path)
    a.add_argument("--stage", choices=STAGES, required=True)
    a.add_argument("--launch", type=dt.date.fromisoformat, default=None)
    a.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            return run_validate(args.content, args.stage)
        return run_apply(args.content, args.stage, launch=args.launch, dry_run=args.dry_run)
    except Refusal as refusal:
        print(f"refused: {refusal}", file=sys.stderr)
        return 2
    except apply.WriteFailed as failed:
        print(f"failed: {failed}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
