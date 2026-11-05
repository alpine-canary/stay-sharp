"""Practice routes (task T110, Story 5, FR-021 to FR-023, contracts/openapi.yaml).

Same view builder and grading as the daily (``domain/views.py``, ``domain/grading.py``): the
answer, the explanation and the source leave the server only after the answer is stored.
Practice writes only ``PRA#`` and ``PRACOUNT#`` items, never a play, so it cannot change the
streak, the freeze or a daily result (FR-023).
"""

from __future__ import annotations

import json
import re
from http import HTTPStatus
from typing import Any

from aws_lambda_powertools.event_handler import Response
from aws_lambda_powertools.event_handler.router import APIGatewayHttpRouter
from botocore.exceptions import BotoCoreError, ClientError
from pydantic import BaseModel

from staysharp import clock
from staysharp.domain import grading
from staysharp.domain.cancellation import Outcome
from staysharp.domain.models import (
    DECKS,
    AnswerRequest,
    PracticeNextRequest,
    QuestionView,
)
from staysharp.domain.views import question_view
from staysharp.handlers.http import JSON, ApiError
from staysharp.handlers.routes_plays import (
    check_submission,
    result_of,
    scoring_failure,
)
from staysharp.obs import bind_question
from staysharp.store import answers, practice, questions, table

router = APIGatewayHttpRouter()

ATTEMPT_ID = re.compile(r"^[A-Z2-7]{16}$")


def _player() -> str:
    player_id: str = router.context["player_id"]
    return player_id


def _json(data: Any, status: int = HTTPStatus.OK) -> Response[str]:
    body = (
        data.model_dump_json(by_alias=True, exclude_none=True)
        if isinstance(data, BaseModel)
        else json.dumps(data, separators=(",", ":"))
    )
    return Response(status_code=status, content_type=JSON, body=body)


@router.post("/practice/next")
def next_question() -> Response[str]:
    request = PracticeNextRequest.model_validate_json(router.current_event.decoded_body or "{}")
    if request.deck is not None and request.deck not in DECKS[request.level]:
        raise ApiError(HTTPStatus.BAD_REQUEST, "invalid_request", "That deck is not in this level.")
    now = clock.now()
    try:
        picked = practice.pick(_player(), request.level, request.deck, request.prefer, now)
    except practice.Empty as error:
        raise ApiError(
            HTTPStatus.NOT_FOUND, "not_ready", "There are no past questions to practise yet."
        ) from error
    except practice.Limited as error:
        raise ApiError(
            HTTPStatus.TOO_MANY_REQUESTS,
            "rate_limited",
            "That is 200 practice questions today. Come back tomorrow.",
        ) from error
    bind_question(picked.served.qid)
    question = questions.question(picked.served.qid, picked.served.version)
    view = QuestionView.model_validate(
        question_view(
            question.model_dump(mode="json"),
            index=0,
            served_at=table.iso_ms(picked.served.served_at),
            target_seconds=None,
        )
    )
    payload = {
        "attemptId": picked.attempt_id,
        "qid": picked.served.qid,
        "question": view.model_dump(mode="json", by_alias=True, exclude_none=True),
    }
    return _json(payload)


@router.post("/practice/<attempt_id>/answer")
def answer(attempt_id: str) -> Response[str]:
    request = AnswerRequest.model_validate_json(router.current_event.decoded_body or "{}")
    now = clock.now()
    served = practice.read(_player(), attempt_id, now) if ATTEMPT_ID.fullmatch(attempt_id) else None
    if served is None:
        raise ApiError(
            HTTPStatus.BAD_REQUEST, "invalid_request", "This practice question is no longer open."
        )
    bind_question(served.qid)
    question = questions.question(served.qid, served.version)
    submission = check_submission(question, request)
    key = grading.AnswerKey(question.answer_choice_id, frozenset(question.answer_lines))
    try:
        graded = practice.answer(_player(), attempt_id, served, submission, key, now)
    except answers.NotOpened as error:
        raise ApiError(
            HTTPStatus.BAD_REQUEST, "invalid_request", "This practice question is no longer open."
        ) from error
    except answers.ScoringFailure as error:
        raise scoring_failure("practice retries exhausted") from error
    except (table.StoreError, ClientError, BotoCoreError) as error:
        raise scoring_failure(type(error).__name__) from error

    if graded.outcome is Outcome.CONFLICT:
        recorded = result_of(question, graded.served, duplicate=False)
        return _json(
            {
                "code": "conflict",
                "recorded": recorded.model_dump(mode="json", by_alias=True, exclude_none=True),
            },
            HTTPStatus.CONFLICT,
        )
    duplicate = graded.outcome is Outcome.DUPLICATE
    return _json(result_of(question, graded.served, duplicate=duplicate))
