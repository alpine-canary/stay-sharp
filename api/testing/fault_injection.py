"""Dev-only wrapper around the API handler for the drills (task T077, research R10, W11).

Packaged only in the dev build (the CDK asset leaves this folder out for prod, and a CDK test
checks it) and refused at runtime when ``STAGE=prod``.

- **Fault injection (V8)**: while the SSM parameter ``/staysharp/<stage>/fault-injection`` holds
  a future time (ISO 8601 with offset), every answer fails as a scoring failure: 503 to the
  player, ``ScoringFailures`` +1. The time is capped at 30 minutes after it was set, so a
  forgotten drill switches itself off; ``FaultInjectionActive`` is counted on each injected
  request and an alarm fires if it keeps going for 30 minutes.
- **Canary drill (V9)**: ``STAYSHARP_DRILL`` set on one deployed version makes that version fail
  its self-check (``selfcheck-fail``) or fail every request (``fail-traffic``). The variable only
  exists when the dev stack is deployed with the drill context.
"""

from __future__ import annotations

import datetime as dt
import os
import time
from typing import Any

import boto3

from staysharp import aws, config, metrics, obs
from staysharp.handlers import api
from staysharp.store import answers

MAX_ON = dt.timedelta(minutes=30)
CACHE_SECONDS = 10.0
DRILLS = ("selfcheck-fail", "fail-traffic")

_cache: dict[str, tuple[float, dt.datetime | None]] = {}


class Refused(RuntimeError):
    """Fault injection is never allowed in prod."""


def _refuse_prod() -> None:
    if config.stage() == "prod":
        raise Refused("fault injection is not allowed in prod")


def parameter_name() -> str:
    return f"/staysharp/{config.stage()}/fault-injection"


def _read_until() -> dt.datetime | None:
    """The injection end time, capped at 30 minutes after the parameter was last changed."""
    client = boto3.client("ssm", config=aws.CONFIG)
    try:
        found = client.get_parameter(Name=parameter_name())["Parameter"]
    except client.exceptions.ParameterNotFound:
        return None
    value = str(found.get("Value", "")).strip()
    if not value or value == "off":
        return None
    until = dt.datetime.fromisoformat(value)
    if until.tzinfo is None:
        return None
    changed = found.get("LastModifiedDate")
    if isinstance(changed, dt.datetime):
        until = min(until, changed + MAX_ON)
    return until


def injection_until(now: float | None = None) -> dt.datetime | None:
    moment = time.monotonic() if now is None else now
    cached = _cache.get("until")
    if cached is None or moment - cached[0] > CACHE_SECONDS:
        _cache["until"] = (moment, _read_until())
    return _cache["until"][1]


def injecting(at: dt.datetime) -> bool:
    until = injection_until()
    return until is not None and at < until


def _fail_answers(*_args: Any, **_kwargs: Any) -> answers.Graded:
    raise answers.ScoringFailure("fault injection drill")


def handler(event: dict[str, Any], context: Any) -> Any:
    _refuse_prod()
    drill = os.environ.get("STAYSHARP_DRILL")
    if drill is not None and drill not in DRILLS:
        raise Refused(f"unknown drill {drill!r}")

    if event.get("selfcheck") is True:
        if drill == "selfcheck-fail":
            if obs.metrics.default_dimensions.get("Stage") != config.stage():
                obs.metrics.set_default_dimensions(Stage=config.stage())
            metrics.emit("SelfCheckFailures")
            obs.metrics.flush_metrics()
            return {"ok": False, "failed": ["drill"], "reason": "canary drill"}
        return api.handler(event, context)

    if drill == "fail-traffic":
        raise RuntimeError("canary drill: this version fails under traffic")

    if not injecting(dt.datetime.now(dt.UTC)):
        return api.handler(event, context)

    real = answers.answer
    answers.answer = _fail_answers
    try:
        metrics.emit("FaultInjectionActive")
        return api.handler(event, context)
    finally:
        answers.answer = real
