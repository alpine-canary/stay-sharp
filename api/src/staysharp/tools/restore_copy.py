"""Copy a restored table back into the live one (task T118, research R17, docs/runbooks/restore.md).

    AWS_PROFILE=... python -m staysharp.tools.restore_copy --source TABLE --target TABLE [--write]

Every item of the source (a point-in-time restore of the live table) is put into the target
(the live table). Items lost or damaged since the restore point come back; items written after it
and absent from the snapshot stay. Without ``--write`` it only counts. Prints counts only, never
keys or values. The live table keeps its CDK settings (TTL, PITR, alarms, permissions).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterator, Mapping, Sequence
from typing import Any

from staysharp import aws

BATCH = 25
ATTEMPTS = 8


def _scan(name: str) -> Iterator[dict[str, Any]]:
    start: Mapping[str, Any] | None = None
    while True:
        kwargs: dict[str, Any] = {"TableName": name, "ConsistentRead": True}
        if start:
            kwargs["ExclusiveStartKey"] = start
        page = aws.dynamodb().scan(**kwargs)
        yield from page.get("Items", [])
        start = page.get("LastEvaluatedKey")
        if not start:
            return


def _write(name: str, items: list[dict[str, Any]]) -> None:
    pending: Any = {name: [{"PutRequest": {"Item": item}} for item in items]}
    for _ in range(ATTEMPTS):
        response = aws.dynamodb().batch_write_item(RequestItems=pending)
        pending = response.get("UnprocessedItems") or {}
        if not pending:
            return
    raise RuntimeError("items left unprocessed after retries")


def copy(source: str, target: str, *, write: bool) -> int:
    count = 0
    batch: list[dict[str, Any]] = []
    for item in _scan(source):
        count += 1
        if write:
            batch.append(item)
            if len(batch) == BATCH:
                _write(target, batch)
                batch = []
    if write and batch:
        _write(target, batch)
    return count


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--source", required=True, help="the restored table")
    parser.add_argument("--target", required=True, help="the live table")
    parser.add_argument("--write", action="store_true", help="really write (default: count only)")
    args = parser.parse_args(argv)
    if args.source == args.target:
        print("refused: source and target are the same table", file=sys.stderr)
        return 2
    count = copy(args.source, args.target, write=args.write)
    if args.write:
        print(f"{count} items written")
    else:
        print(f"dry run: {count} items would be written; add --write to copy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
