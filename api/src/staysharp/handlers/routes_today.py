"""``GET /health`` and ``GET /today`` (contracts/openapi.yaml)."""

from __future__ import annotations

import datetime as dt

from aws_lambda_powertools.event_handler import Response
from aws_lambda_powertools.event_handler.router import APIGatewayHttpRouter

from staysharp import clock, config
from staysharp.domain import calendar
from staysharp.domain.models import DECKS, LevelReady, Today
from staysharp.handlers.http import JSON, json_response
from staysharp.store import questions

router = APIGatewayHttpRouter()


def now() -> dt.datetime:
    """The Lambda clock (``staysharp.clock``). Tests replace this function."""
    return clock.now()


@router.get("/health")
def health() -> Response[str]:
    return Response(status_code=200, content_type=JSON, body='{"status":"ok"}')


@router.get("/today")
def today() -> Response[str]:
    day = calendar.zurich_today(now())
    launch = config.launch_date()
    if day < launch:
        # Before the launch nothing is published: game #1 is coming, every level is not ready.
        return json_response(
            Today(
                date=day,
                game_number=1,
                week_start=calendar.week_start(day),
                levels=[LevelReady(level=level, ready=False) for level in DECKS],
            )
        )
    levels = [
        LevelReady(
            level=level, ready=not isinstance(questions.daily_set(day, level), questions.NotReady)
        )
        for level in DECKS
    ]
    return json_response(
        Today(
            date=day,
            game_number=calendar.game_number(day, launch),
            week_start=calendar.week_start(day),
            levels=levels,
        )
    )
