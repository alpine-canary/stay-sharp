"""Challenge routes (task T106, Story 4, FR-018 to FR-020, contracts/openapi.yaml).

``POST /challenges`` creates (or returns) the challenge of a finished daily. ``GET
/challenges/{id}`` shows it as the caller may see it: the owner sees their result and the
colleagues who finished; a colleague sees only the owner's score until they finish, then both
results. Unknown and malformed ids get the same plain 404; an expired one says ``expired``.
"""

from __future__ import annotations

import re
from http import HTTPStatus

from aws_lambda_powertools.event_handler import Response
from aws_lambda_powertools.event_handler.router import APIGatewayHttpRouter

from staysharp import clock, metrics
from staysharp.domain.models import ChallengeCreated, ChallengeView, CreateChallengeRequest
from staysharp.handlers.http import ApiError, campaign_source, json_response
from staysharp.obs import player_hash
from staysharp.store import challenges, plays
from staysharp.store.plays import PlayRef

router = APIGatewayHttpRouter()

CHALLENGE_ID = re.compile(r"^[A-Z2-7]{12}$")
GONE = "This challenge link does not work. You can still play today's set."
EXPIRED = "This challenge has ended: links last 30 days. You can still play today's set."


def _player() -> str:
    player_id: str = router.context["player_id"]
    return player_id


def _source() -> str | None:
    return campaign_source(router.current_event.headers)


def load(challenge_id: str) -> challenges.Challenge:
    """The challenge, or the plain 404 every bad link gets (FR-020)."""
    if not CHALLENGE_ID.fullmatch(challenge_id):
        raise ApiError(HTTPStatus.NOT_FOUND, "not_found", GONE)
    try:
        return challenges.get(challenge_id, clock.now())
    except challenges.Unknown as error:
        raise ApiError(HTTPStatus.NOT_FOUND, "not_found", GONE) from error
    except challenges.Expired as error:
        raise ApiError(HTTPStatus.NOT_FOUND, "expired", EXPIRED) from error


@router.post("/challenges")
def create() -> Response[str]:
    request = CreateChallengeRequest.model_validate_json(router.current_event.decoded_body or "{}")
    ref = PlayRef.parse(request.play_id)
    if ref.mode != "daily":
        raise ApiError(
            HTTPStatus.BAD_REQUEST, "invalid_request", "Only a daily can be a challenge."
        )
    now = clock.now()
    play = plays.get(_player(), ref, now)
    if play is None:
        raise ApiError(HTTPStatus.NOT_FOUND, "not_found", "No such play.")
    if not play.finished:
        raise ApiError(
            HTTPStatus.CONFLICT, "conflict", "Finish the set before challenging someone."
        )
    challenge_id = challenges.create(_player(), play, now)
    if challenge_id != play.created_challenge_id:
        metrics.counted("ChallengesCreated", _source())
    return json_response(ChallengeCreated(challenge_id=challenge_id, path=f"/c/{challenge_id}"))


def _own_finished_play(challenge: challenges.Challenge) -> plays.Play | None:
    """The caller's finished play of that set: their daily, else a replay (Story 4, 3a)."""
    now = clock.now()
    for mode in ("daily", "replay"):
        play = plays.get(_player(), PlayRef(challenge.date, challenge.level, mode), now)
        if play is not None and play.finished:
            return play
    return None


@router.get("/challenges/<challenge_id>")
def view(challenge_id: str) -> Response[str]:
    challenge = load(challenge_id)
    base = {
        "challenge_id": challenge.challenge_id,
        "date": challenge.date,
        "level": challenge.level,
        "game_number": challenge.game_number,
        "owner_score": challenge.owner.score,
    }
    if player_hash(_player()) == challenge.owner_hash:
        colleagues = challenges.results(challenge.challenge_id)
        return json_response(
            ChallengeView(
                **base,
                viewer="owner",
                owner=challenge.owner,
                colleagues=colleagues,
                others=len(colleagues),
            )
        )

    metrics.counted("ChallengesOpened", _source())
    others = challenge.results
    you = challenges.result(challenge.challenge_id, _player())
    if you is None:
        play = _own_finished_play(challenge)
        if play is not None:
            you = challenges.snapshot(play)
            if challenges.record(challenge, _player(), you, clock.now()):
                metrics.counted("ChallengesFinished", _source())
                others += 1
    if you is None:
        return json_response(ChallengeView(**base, viewer="colleague_before", others=others))
    return json_response(
        ChallengeView(
            **base, viewer="colleague_after", owner=challenge.owner, you=you, others=others
        )
    )
