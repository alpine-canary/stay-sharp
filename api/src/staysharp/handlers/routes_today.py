"""``GET /health`` and ``GET /today`` (contracts/openapi.yaml)."""

from __future__ import annotations

import datetime as dt

from aws_lambda_powertools.event_handler import Response
from aws_lambda_powertools.event_handler.router import APIGatewayHttpRouter

from staysharp import config
from staysharp.domain import calendar
from staysharp.domain.models import DECKS, LevelReady, Today
from staysharp.handlers.http import JSON, json_response
from staysharp.store import questions

router = APIGatewayHttpRouter()


def now() -> dt.datetime:
    """The Lambda clock. Tests replace this function."""
    return dt.datetime.now(dt.UTC)


@router.get("/health")
def health() -> Response[str]:
    return Response(status_code=200, content_type=JSON, body='{"status":"ok"}')


@router.get("/today")
def today() -> Response[str]:
    day = calendar.zurich_today(now())
    levels = [
        LevelReady(
            level=level, ready=not isinstance(questions.daily_set(day, level), questions.NotReady)
        )
        for level in DECKS
    ]
    return json_response(
        Today(
            date=day,
            game_number=calendar.game_number(day, config.launch_date()),
            week_start=calendar.week_start(day),
            levels=levels,
        )
    )
