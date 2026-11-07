"""The one place boto3 clients are made (research R8).

Every client has short timeouts and a limited number of attempts, so a slow dependency gives a
quick, counted failure instead of a hung Lambda. In tests, ``DYNAMODB_ENDPOINT`` points DynamoDB
at DynamoDB Local.
"""

from __future__ import annotations

import os
from functools import cache
from typing import TYPE_CHECKING

import boto3
from botocore.config import Config

if TYPE_CHECKING:
    from mypy_boto3_cognito_idp import CognitoIdentityProviderClient
    from mypy_boto3_dynamodb import DynamoDBClient
    from mypy_boto3_secretsmanager import SecretsManagerClient
    from mypy_boto3_sesv2 import SESV2Client

CONFIG = Config(
    connect_timeout=2,
    read_timeout=3,
    retries={"mode": "standard", "total_max_attempts": 3},  # first call + 2 retries
)


def _region() -> str:
    return os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "eu-central-2"


@cache
def dynamodb() -> DynamoDBClient:
    endpoint = os.environ.get("DYNAMODB_ENDPOINT") or None
    return boto3.client("dynamodb", region_name=_region(), endpoint_url=endpoint, config=CONFIG)


@cache
def secretsmanager() -> SecretsManagerClient:
    return boto3.client("secretsmanager", region_name=_region(), config=CONFIG)


@cache
def cognito() -> CognitoIdentityProviderClient:
    """Only for the account delete and jobs functions (delete, get and list users)."""
    return boto3.client("cognito-idp", region_name=_region(), config=CONFIG)


@cache
def sesv2() -> SESV2Client:
    """Plain-text e-mail (staysharp.mail), in the stage's own Region (eu-central-2)."""
    return boto3.client("sesv2", region_name=_region(), config=CONFIG)


def reset() -> None:
    """Forget cached clients (tests that change the environment)."""
    dynamodb.cache_clear()
    secretsmanager.cache_clear()
    cognito.cache_clear()
    sesv2.cache_clear()
