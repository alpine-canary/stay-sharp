"""Logs, metrics and the player hash (research R3, R11, R16).

Logs carry ``request_id``, ``question_id`` and ``player_hash`` only: never the raw player id,
IP addresses, headers or input values. ``player_hash`` is ``HMAC-SHA256(pepper, playerId)``; the
pepper is read once per cold start from Secrets Manager and kept in memory.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from functools import cache

from aws_lambda_powertools import Logger, Metrics

from staysharp import aws, config

logger = Logger(service="staysharp")
metrics = Metrics(namespace="StaySharp")

# Only for STAGE=local and tests, where no secret exists. Refused anywhere else.
LOCAL_PEPPER = b"local-pepper-not-secret"


@cache
def pepper() -> bytes:
    arn = os.environ.get("PEPPER_SECRET_ARN")
    if not arn:
        if config.stage() == "local":
            return LOCAL_PEPPER
        raise RuntimeError("PEPPER_SECRET_ARN is not set")
    response = aws.secretsmanager().get_secret_value(SecretId=arn)
    secret = response.get("SecretString")
    if not isinstance(secret, str) or len(secret) < 32:
        raise RuntimeError("pepper secret is missing or too short")
    return secret.encode()


def player_hash(player_id: str) -> str:
    return hmac.new(pepper(), player_id.encode(), hashlib.sha256).hexdigest()


def bind_request(request_id: str | None) -> None:
    """Start a request: only ids from here on."""
    logger.remove_keys(["question_id", "player_hash"])
    logger.append_keys(request_id=request_id)


def bind_player(player_id: str) -> None:
    logger.append_keys(player_hash=player_hash(player_id))


def bind_question(question_id: str) -> None:
    logger.append_keys(question_id=question_id)
