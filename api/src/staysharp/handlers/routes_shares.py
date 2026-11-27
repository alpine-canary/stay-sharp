"""``POST /shares``: the player copied or shared their result card (campaign 2026-11).

Counted as an aggregate, plus once per campaign network when the visit has one. Nothing is
stored and nothing about the player is recorded; the answer is an empty 204, so the site can
send it and forget it.
"""

from __future__ import annotations

from http import HTTPStatus

from aws_lambda_powertools.event_handler import Response
from aws_lambda_powertools.event_handler.router import APIGatewayHttpRouter

from staysharp import metrics
from staysharp.handlers.http import campaign_source

router = APIGatewayHttpRouter()


@router.post("/shares")
def shared() -> Response[str]:
    metrics.counted("ResultsShared", campaign_source(router.current_event.headers))
    return Response(status_code=HTTPStatus.NO_CONTENT, body="")
