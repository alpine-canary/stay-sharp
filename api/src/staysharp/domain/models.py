"""Strict Pydantic models: stored content, request bodies and responses.

Response and request models named like a schema in ``contracts/openapi.yaml`` must expose
exactly that schema's fields; ``scripts/gen_models.py`` fails CI on drift. Every model refuses
unknown fields (``extra="forbid"``). Field names are snake_case in Python and camelCase on the
wire.
"""

from __future__ import annotations

import datetime as dt
import re
import uuid
from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)
from pydantic.alias_generators import to_camel

Level = Literal["senior", "junior", "starter"]
Mode = Literal["daily", "replay"]
SeniorDeck = Literal["spot", "better", "fail", "acronym", "news"]
StarterDeck = Literal["logic", "readcode", "whatif", "words", "aisense"]
Deck = SeniorDeck | StarterDeck
Language = Literal["python", "typescript", "php", "sql", "cdk", "text"]

# FR-001: one question per deck, in this order.
DECKS: dict[Level, tuple[Deck, ...]] = {
    "senior": ("spot", "better", "fail", "acronym", "news"),
    # Junior plays Senior's decks with easier questions: a deck no longer tells the level.
    "junior": ("spot", "better", "fail", "acronym", "news"),
    "starter": ("logic", "readcode", "whatif", "words", "aisense"),
}
# Decks where the player also picks a line (grade 0.5 possible).
LINE_DECKS: frozenset[Deck] = frozenset({"spot"})

Qid = Annotated[str, StringConstraints(pattern=r"^[a-z0-9_]{3,64}$")]
ChoiceId = Annotated[str, StringConstraints(pattern=r"^[A-Z2-7]{8}$")]
ChallengeId = Annotated[str, StringConstraints(pattern=r"^[A-Z2-7]{12}$")]
PlayId = Annotated[
    str, StringConstraints(pattern=r"^\d{4}-\d{2}-\d{2}\.(senior|junior|starter)\.(daily|replay)$")
]
Line = Annotated[int, Field(ge=1, le=30)]

_GRADES = (0.0, 0.5, 1.0)


def _check_grade(value: float) -> float:
    if value not in _GRADES:
        raise ValueError("grade must be 0, 0.5 or 1")
    return value


def _check_bonus(value: float) -> float:
    if value not in (0.0, 0.2):
        raise ValueError("bonus must be 0 or 0.2")
    return value


Grade = Annotated[float, AfterValidator(_check_grade)]
Bonus = Annotated[float, AfterValidator(_check_bonus)]


class Strict(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        alias_generator=to_camel,
        populate_by_name=True,
        frozen=True,
    )


def code_line_count(code: str | None) -> int:
    """Lines a player can pick: every line of the code, a final newline excluded."""
    return len(code.splitlines()) if code else 0


def parse_player_id(value: str | None) -> uuid.UUID:
    """Check the ``X-Player-Id`` header: a UUIDv4 in canonical form, nothing else."""
    if value is None or not re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", value
    ):
        raise ValueError("X-Player-Id must be a lowercase UUIDv4")
    return uuid.UUID(value)


# --- Stored content -------------------------------------------------------------------------


class Choice(Strict):
    id: ChoiceId
    text: Annotated[str, StringConstraints(min_length=1, max_length=240)]


class Question(Strict):
    """One version of a question as stored (``Q#<qid>`` / ``V#<n>``). Never sent as is."""

    qid: Qid
    version: Annotated[int, Field(ge=1)]
    level: Level
    deck: Deck
    prompt: Annotated[str, StringConstraints(min_length=1, max_length=400)]
    code: Annotated[str, StringConstraints(max_length=3100)] | None = None
    language: Language | None = None
    choices: Annotated[list[Choice], Field(min_length=4, max_length=4)]
    # Choice ids in authoring order, so a new version keeps the ids of version 1 (R4).
    choice_order: Annotated[list[ChoiceId], Field(min_length=4, max_length=4)] | None = None
    answer_choice_id: ChoiceId
    answer_lines: list[Line] = []
    explanation: Annotated[str, StringConstraints(min_length=1, max_length=1200)]
    source_url: Annotated[str, StringConstraints(pattern=r"^https://")] | None = None
    source_date: dt.date | None = None
    daily_eligible: bool = True
    approved_by: str | None = None
    approved_at: dt.datetime | None = None
    second_reader: str | None = None
    change_reason: Annotated[str, StringConstraints(min_length=3)] | None = None
    published_at: dt.datetime | None = None

    @model_validator(mode="after")
    def _rules(self) -> Self:
        if self.deck not in DECKS[self.level]:
            raise ValueError(f"deck {self.deck} is not a {self.level} deck")
        ids = [choice.id for choice in self.choices]
        if len(set(ids)) != 4:
            raise ValueError("choice ids must be unique")
        if self.answer_choice_id not in ids:
            raise ValueError("answer_choice_id must be one of the choices")
        if self.choice_order is not None and sorted(self.choice_order) != sorted(ids):
            raise ValueError("choice_order must list the choice ids")
        if self.deck in LINE_DECKS:
            if not self.code or not self.answer_lines:
                raise ValueError(f"{self.deck} needs code and answer_lines")
            if max(self.answer_lines) > code_line_count(self.code):
                raise ValueError("answer_lines must be within the code")
        elif self.answer_lines:
            raise ValueError(f"{self.deck} has no answer lines")
        if self.deck in ("better", "readcode") and not self.code:
            raise ValueError(f"{self.deck} needs code")
        if self.deck == "news" and (self.source_url is None or self.source_date is None):
            raise ValueError("news needs source_url and source_date")
        if self.level == "starter" and self.daily_eligible and not self.second_reader:
            raise ValueError("starter questions need a second reader")
        if self.version > 1 and not self.change_reason:
            raise ValueError("a new version needs a change reason")
        return self


class DailyItem(Strict):
    index: Annotated[int, Field(ge=0, le=4)]
    deck: Deck
    qid: Qid
    version: Annotated[int, Field(ge=1)]
    target_seconds: Annotated[int, Field(ge=5, le=300)]


class DailySet(Strict):
    """``DAILY#<date>#<level>`` / ``SET``: five questions in FR-001 order."""

    date: dt.date
    level: Level
    game_number: Annotated[int, Field(ge=1)]
    items: Annotated[list[DailyItem], Field(min_length=5, max_length=5)]
    published_at: dt.datetime | None = None

    @model_validator(mode="after")
    def _order(self) -> Self:
        if [item.index for item in self.items] != [0, 1, 2, 3, 4]:
            raise ValueError("items must have indexes 0 to 4 in order")
        if tuple(item.deck for item in self.items) != DECKS[self.level]:
            raise ValueError(f"decks must follow the {self.level} order")
        if len({item.qid for item in self.items}) != 5:
            raise ValueError("a question appears once per set")
        return self


# --- Request bodies -------------------------------------------------------------------------


class StartPlayRequest(Strict):
    level: Level
    mode: Mode
    date: dt.date | None = None
    relaxed: bool = False
    challenge_id: ChallengeId | None = None


class AnswerRequest(Strict):
    choice_id: ChoiceId
    line: Line | None = None


class PracticeNextRequest(Strict):
    level: Level
    deck: Deck | None = None
    prefer: Annotated[list[Qid], Field(max_length=5)] = []


class CreateChallengeRequest(Strict):
    play_id: PlayId


# --- Responses (names and fields match contracts/openapi.yaml) ------------------------------

ErrorCode = Literal[
    "invalid_request",
    "not_found",
    "not_ready",
    "conflict",
    "expired",
    "rate_limited",
    "unavailable",
]


class Error(Strict):
    code: ErrorCode
    message: str
    request_id: str | None = None


class QuestionView(Strict):
    index: Annotated[int, Field(ge=0, le=4)]
    deck: Deck
    prompt: str
    code: str | None = None
    language: Language | None = None
    choices: Annotated[list[Choice], Field(min_length=4, max_length=4)]
    target_seconds: int | None = None
    served_at: dt.datetime


class AnswerResult(Strict):
    grade: Grade
    bonus: Bonus
    elapsed_ms: Annotated[int, Field(ge=0)]
    correct_choice_id: ChoiceId
    correct_lines: list[int] | None = None
    explanation: str
    source_url: str | None = None
    source_date: dt.date | None = None
    duplicate: bool


class PlayState(Strict):
    play_id: PlayId
    date: dt.date
    level: Level
    mode: Mode
    game_number: int
    relaxed: bool
    grades: Annotated[list[Grade | None], Field(max_length=5)]
    score: float
    bonus: float
    elapsed_ms: int | None = None
    finished: bool
    challenge_id: ChallengeId | None = None
    question: QuestionView | None = None


class ResultSnapshot(Strict):
    grades: Annotated[list[Grade], Field(min_length=5, max_length=5)]
    score: float
    bonus: float
    elapsed_ms: int
    relaxed: bool


class ChallengeCreated(Strict):
    challenge_id: ChallengeId
    path: Annotated[str, StringConstraints(pattern=r"^/c/[A-Z2-7]{12}$")]


ChallengeViewer = Literal["owner", "colleague_before", "colleague_after"]


class ChallengeView(Strict):
    challenge_id: ChallengeId
    date: dt.date
    level: Level
    game_number: int
    viewer: ChallengeViewer
    owner_score: float
    owner: ResultSnapshot | None = None
    you: ResultSnapshot | None = None
    colleagues: Annotated[list[ResultSnapshot], Field(max_length=50)] | None = None
    others: int


class LevelReady(Strict):
    level: Level
    ready: bool


class Today(Strict):
    date: dt.date
    game_number: int
    week_start: dt.date
    levels: list[LevelReady]
