"""A seeded game on DynamoDB Local, played through the real API handler with a fixed clock."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any

import pytest

from staysharp import clock
from staysharp.domain import calendar
from staysharp.domain.models import Question
from staysharp.store import answers, questions
from staysharp.tools import seed
from tests.events import PLAYER, body, call

TODAY = dt.date(2026, 11, 20)
# 12:00 in Zurich on TODAY.
NOON = dt.datetime(2026, 11, 20, 11, 0, tzinfo=dt.UTC)
LAUNCH = TODAY - dt.timedelta(days=4)
WRONG_LINE = 1


@dataclass
class Game:
    now: dt.datetime = NOON
    player: str = PLAYER
    level: str = "senior"
    mode: str = "daily"
    day: dt.date = TODAY
    calls: list[str] = field(default_factory=list)
    # The X-Source header the site sends for a campaign visit (utm_source), or none.
    source: str | None = None

    @property
    def play_id(self) -> str:
        return f"{self.day.isoformat()}.{self.level}.{self.mode}"

    def later(self, seconds: float) -> None:
        self.now += dt.timedelta(seconds=seconds)

    def question(self, index: int) -> Question:
        daily = questions.daily_set(self.day, self.level)  # type: ignore[arg-type]
        assert not isinstance(daily, questions.NotReady)
        item = daily.items[index]
        return questions.question(item.qid, item.version)

    def right(self, index: int) -> dict[str, Any]:
        q = self.question(index)
        answer: dict[str, Any] = {"choiceId": q.answer_choice_id}
        if q.answer_lines:
            answer["line"] = q.answer_lines[0]
        return answer

    def wrong(self, index: int) -> dict[str, Any]:
        q = self.question(index)
        choice = next(c.id for c in q.choices if c.id != q.answer_choice_id)
        answer: dict[str, Any] = {"choiceId": choice}
        if q.answer_lines:
            answer["line"] = next(
                n for n in range(1, len((q.code or "").splitlines()) + 1) if n not in q.answer_lines
            )
        return answer

    # --- API calls ---------------------------------------------------------------------------

    @property
    def headers(self) -> dict[str, str]:
        return {"x-source": self.source} if self.source else {}

    def start(self, **extra: Any) -> dict[str, Any]:
        payload = {"level": self.level, "mode": self.mode, **extra}
        if self.day != calendar.zurich_today(self.now) and "date" not in payload:
            payload["date"] = self.day.isoformat()
        return call("POST", "/api/v1/plays", body=payload, player=self.player, headers=self.headers)

    def get(self) -> dict[str, Any]:
        return call(
            "GET", f"/api/v1/plays/{self.play_id}", player=self.player, headers=self.headers
        )

    def relax(self) -> dict[str, Any]:
        return call(
            "POST",
            f"/api/v1/plays/{self.play_id}/relaxed",
            player=self.player,
            headers=self.headers,
        )

    def open(self, index: int) -> dict[str, Any]:
        return call(
            "POST",
            f"/api/v1/plays/{self.play_id}/questions/{index}/open",
            player=self.player,
            headers=self.headers,
        )

    def answer(self, index: int, payload: dict[str, Any] | str) -> dict[str, Any]:
        return call(
            "POST",
            f"/api/v1/plays/{self.play_id}/questions/{index}/answer",
            body=payload,
            player=self.player,
            headers=self.headers,
        )

    def play_all(self, *, right: bool = True, think_s: float = 5) -> list[dict[str, Any]]:
        results = []
        self.start()
        for index in range(5):
            self.open(index)
            self.later(think_s)
            result = self.answer(index, self.right(index) if right else self.wrong(index))
            assert result["statusCode"] == 200, result
            results.append(body(result))
        return results


@pytest.fixture
def game(table: str, monkeypatch: pytest.MonkeyPatch) -> Game:
    monkeypatch.setenv("STAGE", "local")
    monkeypatch.setenv("LAUNCH_DATE", LAUNCH.isoformat())
    seed.seed(seed.SAMPLES, today=TODAY, days=2, launch=LAUNCH)
    state = Game()
    monkeypatch.setattr(clock, "now", lambda: state.now)
    monkeypatch.setattr(answers, "sleep", lambda _s: None)
    return state
