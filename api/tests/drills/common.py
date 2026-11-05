"""Shared helpers for the dev drills: find dev, call the public API, wait for a condition."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import boto3

REGION = "eu-central-2"


def refuse_prod(stage: str) -> None:
    if stage != "dev":
        raise SystemExit("refused: drills run against dev only")


def site_domain(stage: str) -> str:
    cfn = boto3.client("cloudformation", region_name=REGION)
    found = cfn.describe_stack_resources(StackName=f"staysharp-{stage}-web")["StackResources"]
    (dist,) = [r for r in found if r["ResourceType"] == "AWS::CloudFront::Distribution"]
    cloudfront = boto3.client("cloudfront")
    return str(
        cloudfront.get_distribution(Id=dist["PhysicalResourceId"])["Distribution"]["DomainName"]
    )


@dataclass
class Reply:
    status: int
    body: Any


def call(domain: str, method: str, path: str, player: str | None, body: Any = None) -> Reply:
    headers = {"Content-Type": "application/json"}
    if player:
        headers["X-Player-Id"] = player
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(  # noqa: S310 - https URL built from our own stack
        f"https://{domain}/api/v1{path}", data=data, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:  # noqa: S310
            raw = response.read()
            return Reply(response.status, json.loads(raw) if raw else None)
    except urllib.error.HTTPError as error:
        raw = error.read()
        try:
            parsed = json.loads(raw) if raw else None
        except ValueError:
            parsed = raw.decode(errors="replace")
        return Reply(error.code, parsed)


def new_player() -> str:
    return str(uuid.uuid4())


def wait_for[T](
    what: str, check: Callable[[], T | None], *, timeout_s: float, every_s: float = 10
) -> T:
    start = time.monotonic()
    while True:
        value = check()
        if value is not None:
            print(f"  ok after {time.monotonic() - start:.0f} s: {what}")
            return value
        if time.monotonic() - start > timeout_s:
            raise SystemExit(f"FAILED: {what} not seen within {timeout_s:.0f} s")
        time.sleep(every_s)


def alarm_state(prefix: str) -> str:
    cloudwatch = boto3.client("cloudwatch", region_name=REGION)
    alarms = cloudwatch.describe_alarms(AlarmNamePrefix=prefix)["MetricAlarms"]
    if len(alarms) != 1:
        raise SystemExit(f"expected one alarm named {prefix}*, found {len(alarms)}")
    return str(alarms[0]["StateValue"])
