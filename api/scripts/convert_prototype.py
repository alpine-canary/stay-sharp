"""Convert the M0 prototype's 14 days into sample questions (task T037, FR-024c).

The prototype is public already, so its questions may live in this repository, but only as
samples: ``sample: true`` and ``daily_eligible: false``, never schedulable. Each file keeps the
prototype day it was played on (2026-10-23 to 2026-11-05) in ``schedule.yaml`` (schedule format),
which the seed tool uses for the practice pool.

Needs Node.js (to read the prototype's data arrays). Run once:

    uv run python scripts/convert_prototype.py
"""

from __future__ import annotations

import datetime as dt
import json
import subprocess  # noqa: S404 - runs node on a file of this repository
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
PROTOTYPE = ROOT / "prototype" / "stay-sharp.html"
OUT = ROOT / "content" / "samples" / "prototype"
START = dt.date(2026, 10, 23)

DECK = {"SPOT": "spot", "BETTER": "better", "FAIL": "fail", "ACR": "acronym", "NEWS": "news"}
# Prompts the prototype showed from the deck description when a question had none.
DEFAULT_PROMPT = {
    "spot": "Pick the worst line and say what is wrong with it.",
    "fail": "What happens next?",
}
# FR-005b initial Senior targets, in seconds.
TARGETS = {"spot": 60, "better": 45, "fail": 45, "acronym": 20, "news": 30}
LANGUAGES = {"python", "typescript", "php", "sql", "cdk"}

NODE_DUMP = r"""
const fs = require("fs");
const html = fs.readFileSync(process.argv[1], "utf8");
const start = html.indexOf("const SPOT = [");
const end = html.indexOf("/* ---------- helpers");
const body = html.slice(start, end);
const data = new Function(body + "; return {SPOT, BETTER, FAIL, ACR, NEWS};")();
process.stdout.write(JSON.stringify(data));
"""


def read_prototype() -> dict[str, list[dict[str, Any]]]:
    out = subprocess.run(  # noqa: S603
        ["node", "-e", NODE_DUMP, str(PROTOTYPE)],  # noqa: S607
        check=True,
        capture_output=True,
        text=True,
    )
    data: dict[str, list[dict[str, Any]]] = json.loads(out.stdout)
    return data


def convert(raw: dict[str, Any], deck: str) -> dict[str, Any]:
    question: dict[str, Any] = {
        "id": f"proto_{raw['id']}",
        "level": "senior",
        "deck": deck,
    }
    language = raw.get("lang")
    if raw.get("code"):
        question["language"] = language if language in LANGUAGES else "text"
    question["prompt"] = raw.get("prompt") or DEFAULT_PROMPT[deck]
    if raw.get("code"):
        question["code"] = raw["code"]
    question["choices"] = list(raw["choices"])
    answer: dict[str, Any] = {"choice": raw["answer"]}
    if deck == "spot":
        answer["lines"] = list(raw["lines"])
    question["answer"] = answer
    question["explanation"] = raw["explain"]
    if raw.get("src"):
        question["source"] = {"url": raw["src"]["url"], "date": raw["src"]["date"]}
    question["sample"] = True
    question["daily_eligible"] = False
    question["status"] = "approved"
    question["approved_by"] = "maintainer"
    question["approved_at"] = "2026-10-23T00:00:00Z"
    return question


def _block_strings(dumper: yaml.SafeDumper, value: str) -> yaml.ScalarNode:
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


class Dumper(yaml.SafeDumper):
    pass


Dumper.add_representer(str, _block_strings)


def dump(data: dict[str, Any]) -> str:
    return yaml.dump(data, Dumper=Dumper, sort_keys=False, allow_unicode=True, width=100)


def main() -> int:
    data = read_prototype()
    OUT.mkdir(parents=True, exist_ok=True)
    days: dict[str, list[str]] = {}
    count = 0
    for array, deck in DECK.items():
        for n, raw in enumerate(data[array]):
            question = convert(raw, deck)
            (OUT / f"{question['id']}.yaml").write_text(dump(question), encoding="utf-8")
            days.setdefault((START + dt.timedelta(days=n)).isoformat(), []).append(question["id"])
            count += 1
    schedule = {"level": "senior", "targets": TARGETS, "days": days}
    (OUT / "schedule.yaml").write_text(dump(schedule), encoding="utf-8")
    print(f"{count} prototype questions and {len(days)} days written to {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
