"""Check a whole batch before anything is written (research R4, W14, FR-024, FR-025, V7).

A batch is every question file and every ``schedule.yaml`` under a content folder. Any problem
refuses the whole batch. Each problem names the question id (or the schedule and date) and a
reason built from field names and rules only: reasons go to CI logs, so they never quote a
prompt, a choice, an answer or an explanation.

Checks: both JSON schemas; deck belongs to the level; duplicate ids; date-like ids; answer lines
within the code; scheduled questions exist, are approved, daily eligible and not samples; the
day follows the FR-001 deck order with questions of the schedule's level; a question is
scheduled on one date only; every deck of the level has a target time; one schedule per level
and date; and, when the stored versions are given, an edit that changes what players see has a
new ``change_reason``.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from functools import cache
from importlib import resources
from pathlib import Path
from typing import Any, cast

from staysharp.domain.models import DECKS, Level, Question, code_line_count
from staysharp.publish import versions
from staysharp.tools.content import question_files, schedule_files


@dataclass(frozen=True)
class Authored:
    """One authoring file: its parsed data and its path (for messages)."""

    data: dict[str, Any]
    path: str


@dataclass(frozen=True)
class Content:
    questions: list[Authored] = field(default_factory=list)
    schedules: list[Authored] = field(default_factory=list)


@dataclass(frozen=True, order=True)
class Problem:
    id: str
    reason: str


# --- Loading ----------------------------------------------------------------------------------


def load(root: Path) -> Content:
    import yaml  # tool-only dependency

    def read(path: Path) -> Authored:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return Authored(data if isinstance(data, dict) else {}, str(path.relative_to(root)))

    return Content(
        questions=[read(p) for p in question_files(root)],
        schedules=[read(p) for p in schedule_files(root)],
    )


def schema_text(name: str) -> str:
    return resources.files("staysharp.publish").joinpath("schemas", name).read_text("utf-8")


@cache
def _validator(name: str) -> Any:
    import jsonschema

    schema = json.loads(schema_text(name))
    return jsonschema.Draft202012Validator(
        schema, format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER
    )


# --- Single rules -----------------------------------------------------------------------------

_DATE_TOKENS = frozenset(
    {
        *("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "sept", "oct", "nov"),
        *("dec", "january", "february", "march", "april", "june", "july", "august"),
        *("september", "october", "november", "december"),
        *("mon", "tue", "tues", "wed", "thu", "thur", "thurs", "fri", "sat", "sun"),
        *("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"),
        *("today", "tomorrow"),
    }
)
_DATE_PATTERNS = (
    re.compile(r"(?<!\d)(19|20)\d{2}(?!\d)"),  # a year
    re.compile(r"(?<!\d)(\d{6}|\d{8})(?!\d)"),  # 261201, 20261201
    re.compile(r"^(w|wk|week|d|day)\d{1,3}$"),  # w49, day3
)


def date_like(qid: str) -> bool:
    """True if an id carries date or schedule information (ids must be meaningless, R4)."""
    if _DATE_PATTERNS[0].search(qid) or _DATE_PATTERNS[1].search(qid):
        return True
    tokens = qid.split("_")
    if any(t in _DATE_TOKENS or _DATE_PATTERNS[2].match(t) for t in tokens):
        return True
    # Two numeric tokens in a row read like a day and a month: x_12_01.
    return any(a.isdigit() and b.isdigit() for a, b in zip(tokens, tokens[1:], strict=False))


_RULE_TEXT = {
    "required": "is required",
    "minItems": "has too few items",
    "maxItems": "has too many items",
    "uniqueItems": "has repeated items",
    "minLength": "is too short",
    "maxLength": "is too long",
    "pattern": "does not match the pattern",
    "enum": "is not an allowed value",
    "const": "is not the required value",
    "type": "has the wrong type",
    "additionalProperties": "has an unknown field",
    "format": "has the wrong format",
    "minimum": "is too small",
    "maximum": "is too large",
    "propertyNames": "has a key that does not match",
}


def _schema_problems(owner: str, data: Mapping[str, Any], schema: str) -> list[Problem]:
    problems: list[Problem] = []
    for error in _validator(schema).iter_errors(data):
        where = "/".join(str(p) for p in error.absolute_path) or "file"
        rule = str(error.validator)
        if rule == "required":
            # The missing field's name is the only part of the message we keep.
            missing = re.findall(r"'([a-z_]+)' is a required property", error.message)
            where = "/".join([*map(str, error.absolute_path), *missing]) or where
        problems.append(Problem(owner, f"{where} {_RULE_TEXT.get(rule, 'breaks ' + rule)}"))
    return problems


def _question_problems(q: Authored) -> list[Problem]:
    data = q.data
    qid = str(data.get("id", q.path))
    problems = _schema_problems(qid, data, "question.schema.json")
    level, deck = data.get("level"), data.get("deck")
    if level in DECKS and deck is not None and deck not in DECKS[level]:
        problems.append(Problem(qid, f"deck {deck} is not a {level} deck"))
    if isinstance(data.get("id"), str) and date_like(data["id"]):
        problems.append(Problem(qid, "id looks like a date or carries schedule information"))
    answer = data.get("answer")
    if isinstance(answer, dict) and isinstance(answer.get("lines"), list):
        count = code_line_count(data.get("code"))
        if any(not isinstance(n, int) or n > count for n in answer["lines"]):
            problems.append(Problem(qid, f"answer line outside the code ({count} lines)"))
    return problems


# --- The batch --------------------------------------------------------------------------------


def validate(content: Content, *, existing: Mapping[str, Question] | None = None) -> list[Problem]:
    """Every problem of the batch, sorted; an empty list means it may be published."""
    problems: list[Problem] = []
    by_id: dict[str, Authored] = {}
    counts = Counter(str(q.data.get("id")) for q in content.questions)
    for q in content.questions:
        problems += _question_problems(q)
        qid = str(q.data.get("id"))
        if counts[qid] > 1:
            problems.append(Problem(qid, f"duplicate id ({counts[qid]} files)"))
        by_id.setdefault(qid, q)
    broken = {p.id for p in problems}

    problems += _edit_problems(by_id, existing or {}, broken)
    problems += _schedule_problems(content.schedules, by_id)
    return sorted(set(problems))


def _edit_problems(
    by_id: Mapping[str, Authored], existing: Mapping[str, Question], broken: set[str]
) -> list[Problem]:
    problems: list[Problem] = []
    for qid, latest in existing.items():
        authored = by_id.get(qid)
        if authored is None or qid in broken or authored.data.get("status") != "approved":
            continue
        try:
            new = versions.next_version(authored.data, latest)
        except versions.VersionError as error:
            problems.append(Problem(qid, str(error)))
            continue
        if new is None:
            continue
        reason = authored.data.get("change_reason")
        if not reason or reason == latest.change_reason:
            problems.append(
                Problem(qid, f"edit of version {latest.version} needs a new change_reason")
            )
    return problems


def _schedule_problems(
    schedules: Sequence[Authored], by_id: Mapping[str, Authored]
) -> list[Problem]:
    problems: list[Problem] = []
    dates_of: dict[str, list[str]] = defaultdict(list)
    seen_days: Counter[tuple[str, str]] = Counter()
    for schedule in schedules:
        data = schedule.data
        level = data.get("level")
        owner = f"schedule {level or schedule.path}"
        schema = _schema_problems(owner, data, "schedule.schema.json")
        problems += schema
        if level not in DECKS or schema:
            continue
        targets = data.get("targets") or {}
        for deck in DECKS[level]:
            if deck not in targets:
                problems.append(Problem(owner, f"no target time for deck {deck}"))
        for deck in targets:
            if deck not in DECKS[level]:
                problems.append(Problem(owner, f"target for {deck}, not a {level} deck"))
        for day, qids in data["days"].items():
            seen_days[(level, day)] += 1
            problems += _day_problems(level, day, qids, by_id)
            for qid in qids:
                dates_of[qid].append(f"{level} {day}")
    for (level, day), n in seen_days.items():
        if n > 1:
            problems.append(Problem(f"{level} {day}", f"scheduled in {n} files"))
    for qid, places in dates_of.items():
        if len(places) > 1:
            problems.append(Problem(qid, f"scheduled on two dates or more ({len(places)})"))
    return problems


def _day_problems(
    level: str, day: str, qids: Sequence[str], by_id: Mapping[str, Authored]
) -> list[Problem]:
    owner = f"{level} {day}"
    problems: list[Problem] = []
    decks: list[Any] = []
    for qid in qids:
        authored = by_id.get(qid)
        if authored is None:
            problems.append(Problem(qid, f"scheduled on {owner} but no question has this id"))
            decks.append(None)
            continue
        data = authored.data
        decks.append(data.get("deck"))
        if data.get("level") != level:
            problems.append(Problem(qid, f"level {data.get('level')} in a {level} schedule"))
        if data.get("sample") or data.get("daily_eligible", True) is not True:
            problems.append(Problem(qid, "not daily_eligible (sample or already public)"))
        if data.get("status") != "approved":
            problems.append(Problem(qid, f"status {data.get('status')}: only approved questions"))
    order = DECKS[cast(Level, level)]
    if tuple(decks) != order:
        problems.append(Problem(owner, f"deck order must be {', '.join(order)}"))
    return problems
