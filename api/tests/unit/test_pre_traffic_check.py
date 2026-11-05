"""The CodeDeploy pre-traffic hook (T073, research R10)."""

from __future__ import annotations

import io
import json
from typing import Any

import pytest
from botocore.exceptions import ReadTimeoutError

from staysharp.handlers import pre_traffic_check as hook

ARN = "arn:aws:lambda:eu-central-2:000000000000:function:staysharp-dev-api:42"
EVENT = {"DeploymentId": "d-123", "LifecycleEventHookExecutionId": "hook-1"}


class FakeLambda:
    def __init__(self, response: dict[str, Any] | Exception) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def invoke(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class FakeCodeDeploy:
    def __init__(self, fail: bool = False) -> None:
        self.reports: list[dict[str, Any]] = []
        self.fail = fail

    def put_lifecycle_event_hook_execution_status(self, **kwargs: Any) -> dict[str, Any]:
        if self.fail:
            raise RuntimeError("codedeploy down")
        self.reports.append(kwargs)
        return {}


def ok(body: Any, **extra: Any) -> dict[str, Any]:
    raw = body if isinstance(body, bytes) else json.dumps(body).encode()
    return {"StatusCode": 200, "Payload": io.BytesIO(raw), **extra}


@pytest.fixture
def deploy(monkeypatch: pytest.MonkeyPatch) -> FakeCodeDeploy:
    monkeypatch.setenv("TARGET_FUNCTION_ARN", ARN)
    fake = FakeCodeDeploy()
    monkeypatch.setattr(hook, "_codedeploy", lambda: fake)
    return fake


def install(monkeypatch: pytest.MonkeyPatch, response: dict[str, Any] | Exception) -> FakeLambda:
    fake = FakeLambda(response)
    monkeypatch.setattr(hook, "_lambda", lambda: fake)
    return fake


def test_succeeds_when_the_new_version_passes(
    monkeypatch: pytest.MonkeyPatch, deploy: FakeCodeDeploy
) -> None:
    fn = install(monkeypatch, ok({"ok": True, "checks": {}, "failed": []}))
    assert hook.handler(EVENT, None) == "Succeeded"
    assert fn.calls == [
        {
            "FunctionName": ARN,
            "InvocationType": "RequestResponse",
            "Payload": b'{"selfcheck": true}',
        }
    ]
    assert deploy.reports == [
        {"deploymentId": "d-123", "lifecycleEventHookExecutionId": "hook-1", "status": "Succeeded"}
    ]


@pytest.mark.parametrize(
    "response",
    [
        ok({"ok": False, "failed": ["grading"]}),
        ok({"ok": "true"}),
        ok(b"not json"),
        ok([1, 2]),
        ok({"errorMessage": "boom"}, FunctionError="Unhandled"),
        {"StatusCode": 500, "Payload": io.BytesIO(b"{}")},
        ReadTimeoutError(endpoint_url="https://lambda"),
    ],
    ids=[
        "check-failed",
        "ok-not-bool",
        "unreadable",
        "not-object",
        "function-error",
        "500",
        "timeout",
    ],
)
def test_reports_failed_and_raises(
    monkeypatch: pytest.MonkeyPatch, deploy: FakeCodeDeploy, response: Any
) -> None:
    install(monkeypatch, response)
    with pytest.raises(Exception):  # noqa: B017, PT011 - any error, as long as it is raised
        hook.handler(EVENT, None)
    assert [r["status"] for r in deploy.reports] == ["Failed"]


@pytest.mark.parametrize(
    "arn",
    [
        "",
        "arn:aws:lambda:eu-central-2:000000000000:function:staysharp-dev-api",
        "arn:aws:lambda:eu-central-2:000000000000:function:staysharp-dev-api:live",
        "arn:aws:lambda:eu-central-2:000000000000:function:staysharp-dev-api:$LATEST",
    ],
)
def test_invokes_only_a_qualified_version(
    monkeypatch: pytest.MonkeyPatch, deploy: FakeCodeDeploy, arn: str
) -> None:
    monkeypatch.setenv("TARGET_FUNCTION_ARN", arn)
    fn = install(monkeypatch, ok({"ok": True}))
    with pytest.raises(hook.CheckFailed):
        hook.handler(EVENT, None)
    assert fn.calls == []
    assert [r["status"] for r in deploy.reports] == ["Failed"]


def test_a_failed_report_is_not_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TARGET_FUNCTION_ARN", ARN)
    install(monkeypatch, ok({"ok": True}))
    monkeypatch.setattr(hook, "_codedeploy", lambda: FakeCodeDeploy(fail=True))
    with pytest.raises(RuntimeError, match="codedeploy down"):
        hook.handler(EVENT, None)


def test_the_invoke_client_never_retries_and_waits_for_a_cold_start() -> None:
    config: Any = hook.INVOKE_CONFIG
    assert config.retries == {"total_max_attempts": 1}
    assert config.read_timeout >= 20
