"""CodeDeploy pre-traffic hook (task T076, research R10).

Invokes the new version only (its qualified ARN comes from ``TARGET_FUNCTION_ARN``, set by the
same CDK construct; IAM allows invoking that ARN and nothing else) with the synthetic
``{"selfcheck": true}`` event, then reports ``Succeeded`` or ``Failed`` to CodeDeploy.

Anything unexpected (no target, a timeout, a function error, an unreadable answer) reports
``Failed``; the error is then raised again, so it is never swallowed: the invocation counts as a
Lambda error and goes to the on-failure destination.
"""

from __future__ import annotations

import json
import os
import re
from functools import cache
from typing import TYPE_CHECKING, Any, Literal

import boto3
from botocore.config import Config

from staysharp.obs import logger

if TYPE_CHECKING:
    from mypy_boto3_codedeploy import CodeDeployClient
    from mypy_boto3_lambda import LambdaClient

# The self-check runs on a cold version: allow it time, but never retry it blindly.
INVOKE_CONFIG = Config(connect_timeout=2, read_timeout=25, retries={"total_max_attempts": 1})
REPORT_CONFIG = Config(
    connect_timeout=2, read_timeout=5, retries={"mode": "standard", "total_max_attempts": 3}
)
QUALIFIED = re.compile(r"^arn:aws[a-z-]*:lambda:[a-z0-9-]+:\d{12}:function:[\w-]+:\d+$")


class CheckFailed(RuntimeError):
    """The new version did not prove itself healthy."""


@cache
def _lambda() -> LambdaClient:
    return boto3.client("lambda", config=INVOKE_CONFIG)


@cache
def _codedeploy() -> CodeDeployClient:
    return boto3.client("codedeploy", config=REPORT_CONFIG)


def target() -> str:
    arn = os.environ.get("TARGET_FUNCTION_ARN", "")
    if not QUALIFIED.fullmatch(arn):
        raise CheckFailed("TARGET_FUNCTION_ARN is not a qualified version ARN")
    return arn


def run_selfcheck(arn: str) -> dict[str, Any]:
    response = _lambda().invoke(
        FunctionName=arn,
        InvocationType="RequestResponse",
        Payload=json.dumps({"selfcheck": True}).encode(),
    )
    if response.get("StatusCode") != 200:
        raise CheckFailed(f"invoke returned status {response.get('StatusCode')}")
    if response.get("FunctionError"):
        raise CheckFailed(f"the new version raised: {response['FunctionError']}")
    try:
        body = json.loads(response["Payload"].read())
    except (KeyError, ValueError) as error:
        raise CheckFailed("the self-check answer is unreadable") from error
    if not isinstance(body, dict):
        raise CheckFailed("the self-check answer is not an object")
    return body


def handler(event: dict[str, Any], _context: Any) -> str:
    deployment_id = event["DeploymentId"]
    hook_id = event["LifecycleEventHookExecutionId"]
    status: Literal["Succeeded", "Failed"] = "Failed"
    error: Exception | None = None
    try:
        result = run_selfcheck(target())
        if result.get("ok") is True:
            status = "Succeeded"
        else:
            failed = result.get("failed") or result.get("reason") or "unknown"
            error = CheckFailed(f"self-check failed: {failed}")
    except Exception as caught:  # noqa: BLE001 - reported to CodeDeploy, then raised below
        error = caught
    logger.info("pre-traffic check", extra={"status": status, "deployment_id": deployment_id})
    _codedeploy().put_lifecycle_event_hook_execution_status(
        deploymentId=deployment_id,
        lifecycleEventHookExecutionId=hook_id,
        status=status,
    )
    if error is not None:
        logger.error("pre-traffic check failed", extra={"error_type": type(error).__name__})
        raise error
    return status
