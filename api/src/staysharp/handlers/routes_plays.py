"""Play routes (task T062, contracts/openapi.yaml): start or resume, read, relaxed, open, answer.

Questions leave the server only through ``domain/views.question_view`` (R1). The answer, the
explanation and the source are returned only by ``answer``, after the answer is stored.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from http import HTTPStatus
from typing import Any

from aws_lambda_powertools.event_handler import Response
from aws_lambda_powertools.event_handler.router import APIGatewayHttpRouter
from botocore.exceptions import BotoCoreError, ClientError

from staysharp import clock, metrics
from staysharp.domain import calendar, grading
from staysharp.domain.cancellation import Outcome
from staysharp.domain.models import (
    LINE_DECKS,
    AnswerRequest,
    AnswerResult,
    DailySet,
    PlayState,
    Question,
    QuestionView,
    StartPlayRequest,
    code_line_count,
)
from staysharp.domain.views import question_view
from staysharp.handlers.http import ApiError, json_response
from staysharp.obs import bind_question, logger
from staysharp.store import answers, plays, questions, table
from staysharp.store.plays import Play, PlayRef

router = APIGatewayHttpRouter()

PLAY_ID = re.compile(r"^\d{4}-\d{2}-\d{2}\.(senior|starter)\.(daily|replay)$")
NOT_READY = "Today's set is not ready yet. Please come back a little later."


# --- Helpers ---------------------------------------------------------------------------------


def _player() -> str:
    player_id: str = router.context["player_id"]
    return player_id


def _body() -> str:
    return router.current_event.decoded_body or "{}"


def _ref(play_id: str) -> PlayRef:
    if not PLAY_ID.fullmatch(play_id):
        raise ApiError(HTTPStatus.BAD_REQUEST, "invalid_request", "Invalid play id.")
    try:
        return PlayRef.parse(play_id)
    except ValueError as error:
        raise ApiError(HTTPStatus.BAD_REQUEST, "invalid_request", "Invalid play id.") from error


def _index(raw: str) -> int:
    if raw not in ("0", "1", "2", "3", "4"):
        raise ApiError(HTTPStatus.BAD_REQUEST, "invalid_request", "Invalid question index.")
    return int(raw)


def _play(play_id: str, now: dt.datetime) -> Play:
    play = plays.get(_player(), _ref(play_id), now)
    if play is None:
        raise ApiError(HTTPStatus.NOT_FOUND, "not_found", "No such play.")
    return play


def _still_open(play: Play, now: dt.datetime) -> None:
    today = calendar.zurich_today(now)
    if not calendar.play_date_allowed(
        play.ref.mode, play.ref.date, today, challenge=play.challenge_id is not None
    ):
        raise ApiError(
            HTTPStatus.BAD_REQUEST, "invalid_request", "This set can no longer be played."
        )


def _daily(play: Play) -> DailySet:
    daily = questions.daily_set(play.ref.date, play.ref.level)
    if isinstance(daily, questions.NotReady):
        raise table.StoreError(f"daily set of play {play.play_id} is missing")
    return daily


def _view(play: Play, daily: DailySet, index: int, now: dt.datetime) -> QuestionView:
    served = answers.open_question(_player(), play, daily.items[index], now)
    question = questions.question(served.qid, served.version)
    view = question_view(
        question.model_dump(mode="json"),
        index=index,
        served_at=table.iso_ms(served.served_at),
        target_seconds=None if play.relaxed else served.target_seconds,
    )
    return QuestionView.model_validate(view)


def _state(play: Play, question: QuestionView | None = None) -> PlayState:
    return PlayState(
        play_id=play.play_id,
        date=play.ref.date,
        level=play.ref.level,
        mode=play.ref.mode,
        game_number=play.game_number,
        relaxed=play.relaxed,
        grades=[float(play.grades[i]) if i in play.grades else None for i in range(5)],
        score=float(play.score),
        bonus=float(play.bonus),
        elapsed_ms=play.elapsed_ms,
        finished=play.finished,
        challenge_id=play.challenge_id,
        question=question,
    )


def _result(question: Question, served: answers.Served, *, duplicate: bool) -> AnswerResult:
    if served.grade is None or served.bonus is None or served.elapsed_ms is None:
        raise table.StoreError("graded answer is missing its grade")
    return AnswerResult(
        grade=float(served.grade),
        bonus=float(served.bonus),
        elapsed_ms=served.elapsed_ms,
        correct_choice_id=question.answer_choice_id,
        correct_lines=sorted(question.answer_lines) if question.deck in LINE_DECKS else None,
        explanation=question.explanation,
        source_url=question.source_url,
        source_date=question.source_date,
        duplicate=duplicate,
    )


def _check_submission(question: Question, request: AnswerRequest) -> grading.Submission:
    if request.choice_id not in {choice.id for choice in question.choices}:
        raise ApiError(HTTPStatus.BAD_REQUEST, "invalid_request", "Unknown choice.")
    if question.deck in LINE_DECKS:
        if request.line is None:
            raise ApiError(HTTPStatus.BAD_REQUEST, "invalid_request", "Pick a line as well.")
        if request.line > code_line_count(question.code):
            raise ApiError(HTTPStatus.BAD_REQUEST, "invalid_request", "No such line.")
    elif request.line is not None:
        raise ApiError(HTTPStatus.BAD_REQUEST, "invalid_request", "This question has no lines.")
    return grading.Submission(request.choice_id, request.line)


def _scoring_failure(reason: str) -> ApiError:
    version = getattr(router.lambda_context, "function_version", "$LATEST")
    metrics.emit("ScoringFailures", dimension=("FunctionVersion", str(version)))
    logger.error("scoring failure", extra={"reason": reason})
    return ApiError(
        HTTPStatus.SERVICE_UNAVAILABLE,
        "unavailable",
        "Your answer could not be saved. Please try again.",
    )


# --- Routes ----------------------------------------------------------------------------------


@router.post("/plays")
def start_play() -> Response[str]:
    request = StartPlayRequest.model_validate_json(_body())
    if request.challenge_id is not None:
        # Challenge plays arrive with Story 4 (T090 onward).
        raise ApiError(HTTPStatus.BAD_REQUEST, "invalid_request", "Challenges are not open yet.")
    now = clock.now()
    today = calendar.zurich_today(now)
    day = request.date or today
    if not calendar.start_date_allowed(request.mode, day, today, challenge=False):
        raise ApiError(HTTPStatus.BAD_REQUEST, "invalid_request", "This date cannot be played.")

    daily = questions.daily_set(day, request.level)
    if isinstance(daily, questions.NotReady):
        message = NOT_READY if day == today else "There is no set for that day."
        raise ApiError(HTTPStatus.NOT_FOUND, "not_ready", message)

    ref = PlayRef(day, request.level, request.mode)
    try:
        play, created = plays.start(
            _player(),
            ref,
            game_number=daily.game_number,
            relaxed=request.relaxed,
            lock_replay=calendar.play_date_allowed("daily", day, today, challenge=False),
            now=now,
        )
    except plays.ReplayLocked as error:
        raise ApiError(
            HTTPStatus.CONFLICT, "conflict", "Finish this set before replaying it."
        ) from error
    if created:
        metrics.emit("PlaysStarted")

    question = None
    if play.next_index is not None and calendar.play_date_allowed(
        ref.mode, day, today, challenge=False
    ):
        question = _view(play, daily, play.next_index, now)
    status = HTTPStatus.CREATED if created else HTTPStatus.OK
    return json_response(_state(play, question), status)


@router.get("/plays/<play_id>")
def get_play(play_id: str) -> Response[str]:
    return json_response(_state(_play(play_id, clock.now())))


@router.post("/plays/<play_id>/relaxed")
def relax(play_id: str) -> Response[str]:
    play = _play(play_id, clock.now())
    return json_response(_state(plays.relax(_player(), play)))


@router.post("/plays/<play_id>/questions/<index>/open")
def open_question(play_id: str, index: str) -> Response[str]:
    now = clock.now()
    position = _index(index)
    play = _play(play_id, now)
    _still_open(play, now)
    first_open = play.next_index
    if first_open is not None and position > first_open:
        raise ApiError(HTTPStatus.CONFLICT, "conflict", "Answer the previous question first.")
    return json_response(_view(play, _daily(play), position, now))


@router.post("/plays/<play_id>/questions/<index>/answer")
def answer(play_id: str, index: str) -> Response[str]:
    request = AnswerRequest.model_validate_json(_body())
    now = clock.now()
    position = _index(index)
    play = _play(play_id, now)
    _still_open(play, now)

    served = answers.read(_player(), play, position)
    if served is None:
        raise ApiError(HTTPStatus.BAD_REQUEST, "invalid_request", "Open the question first.")
    bind_question(served.qid)
    question = questions.question(served.qid, served.version)
    submission = _check_submission(question, request)
    key = grading.AnswerKey(question.answer_choice_id, frozenset(question.answer_lines))

    try:
        graded = answers.answer(_player(), play, served, submission, key, now)
    except answers.NotOpened as error:
        raise ApiError(
            HTTPStatus.BAD_REQUEST, "invalid_request", "Open the question first."
        ) from error
    except answers.ScoringFailure as error:
        raise _scoring_failure("retries exhausted") from error
    except (table.StoreError, ClientError, BotoCoreError) as error:
        raise _scoring_failure(type(error).__name__) from error

    if graded.outcome is Outcome.CONFLICT:
        recorded = _result(question, graded.served, duplicate=False)
        body: dict[str, Any] = {
            "code": "conflict",
            "recorded": recorded.model_dump(mode="json", by_alias=True, exclude_none=True),
        }
        return Response(
            status_code=HTTPStatus.CONFLICT,
            content_type="application/json",
            body=json.dumps(body, separators=(",", ":")),
        )
    if graded.outcome is Outcome.DUPLICATE:
        metrics.emit("DuplicateAnswers")
        return json_response(_result(question, graded.served, duplicate=True))

    metrics.emit("AnswersGraded")
    if graded.suspiciously_fast:
        metrics.emit("SuspiciouslyFast", dimension=("Deck", served.deck))
    if graded.finished_play:
        metrics.emit("PlaysFinished")
        duration = int((now - play.started_at).total_seconds() * 1000)
        metrics.emit("PlayDurationMs", max(0, duration))
    return json_response(_result(question, graded.served, duplicate=False))
