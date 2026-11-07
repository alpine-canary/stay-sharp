"""Account routes (tasks T225, T244; contracts/accounts.openapi.yaml, research A6).

Every route here sits behind the API Gateway JWT authorizer; the caller is the ``sub`` of the
access token (``caller_sub``). ``DELETE /me`` runs in its own function (account_delete.py).
No response ever contains an e-mail address: the account has none.
"""

from __future__ import annotations

from http import HTTPStatus

from aws_lambda_powertools.event_handler import Response
from aws_lambda_powertools.event_handler.router import APIGatewayHttpRouter

from staysharp import clock
from staysharp.domain import names
from staysharp.domain.accounts import Adopt, Adopted, Me, Merged, MeUpdate, Progress
from staysharp.domain.models import parse_player_id
from staysharp.handlers.http import ApiError, json_response
from staysharp.store import accounts

router = APIGatewayHttpRouter()

DELETING = "Your account is being deleted."


def _sub() -> str:
    sub: str = router.context["account_sub"]
    return sub


def _active(sub: str) -> accounts.Account:
    account = accounts.get(sub)
    if account is None:
        raise ApiError(HTTPStatus.NOT_FOUND, "not_found", "No account yet.")
    if account.state == "deleting":
        raise ApiError(HTTPStatus.CONFLICT, "deleting", DELETING)
    return account


def _me(account: accounts.Account) -> Me:
    return Me(
        primary_player_id=account.primary_player,
        display_name=account.display_name,
        created_at=account.created_at,
    )


@router.get("/me")
def get_me() -> Response[str]:
    account = _active(_sub())
    accounts.touch(account.sub, clock.now(), known=account.last_active_month)
    return json_response(_me(account))


@router.put("/me")
def put_me() -> Response[str]:
    request = MeUpdate.model_validate_json(router.current_event.decoded_body or "{}")
    account = _active(_sub())
    try:
        name = names.check(request.display_name)
    except names.BadName as error:
        raise ApiError(HTTPStatus.BAD_REQUEST, "invalid_request", str(error)) from error
    accounts.set_display_name(account.sub, name)
    return json_response(_me(accounts.get(account.sub) or account))


@router.post("/me/adopt")
def adopt() -> Response[str]:
    Adopt.model_validate_json(router.current_event.decoded_body or "{}")
    try:
        player_id = str(parse_player_id(router.current_event.headers.get("x-player-id")))
    except ValueError as error:
        raise ApiError(
            HTTPStatus.BAD_REQUEST, "invalid_request", "Missing or invalid player id."
        ) from error
    try:
        result = accounts.adopt(_sub(), player_id, clock.now())
    except accounts.Deleting as error:
        raise ApiError(HTTPStatus.CONFLICT, "deleting", DELETING) from error
    except accounts.OtherAccount as error:
        raise ApiError(
            HTTPStatus.CONFLICT,
            "conflict",
            "This browser is signed in to another account. Sign out there first.",
        ) from error
    return json_response(
        Adopted(
            primary_player_id=result.primary_player,
            created=result.created,
            merged=Merged(plays=result.plays, replays=result.replays),
        )
    )


@router.get("/me/progress")
def get_progress() -> Response[str]:
    account = _active(_sub())
    # Opening the game signed in pulls the progress: that is activity too (FR-120).
    accounts.touch(account.sub, clock.now(), known=account.last_active_month)
    copy = accounts.get_progress(account.sub)
    return json_response(Progress(version=copy.version, body=copy.body))


@router.put("/me/progress")
def put_progress() -> Response[str]:
    request = Progress.model_validate_json(router.current_event.decoded_body or "{}")
    account = _active(_sub())
    now = clock.now()
    try:
        stored = accounts.put_progress(account.sub, request.version, request.body, now)
    except accounts.TooLarge as error:
        raise ApiError(
            HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "too_large", "Progress over 64 KB."
        ) from error
    except accounts.BadProgress as error:
        raise ApiError(HTTPStatus.BAD_REQUEST, "invalid_request", "Invalid progress.") from error
    except accounts.Deleting as error:  # deletion started after the check above
        raise ApiError(HTTPStatus.CONFLICT, "deleting", DELETING) from error
    except accounts.VersionConflict as conflict:
        return json_response(
            Progress(version=conflict.stored.version, body=conflict.stored.body),
            HTTPStatus.CONFLICT,
        )
    accounts.touch(account.sub, now, known=account.last_active_month)
    return json_response(Progress(version=stored.version, body=stored.body))
