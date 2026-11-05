"""API function, alias and HTTP API (task T046, scenario V11, research R8, R9)."""

from __future__ import annotations

import json

import pytest

from tests.conftest import TemplateOf, resources

STAGES = ("dev", "prod")


def our_functions(template: TemplateOf, stage: str) -> dict[str, dict[str, object]]:
    """The API function only (not the pre-traffic hook, not CDK helper functions)."""
    functions = resources(template(f"staysharp-{stage}-api"), "AWS::Lambda::Function")
    return {
        k: v
        for k, v in functions.items()
        if v["Properties"].get("FunctionName") == f"staysharp-{stage}-api"
    }


@pytest.mark.parametrize("stage", STAGES)
def test_api_function_settings(template: TemplateOf, stage: str) -> None:
    (fn,) = our_functions(template, stage).values()
    props: dict[str, object] = fn["Properties"]  # type: ignore[assignment]
    assert props["Runtime"] == "python3.13"
    assert props["Architectures"] == ["arm64"]
    assert props["MemorySize"] == 512
    assert props["Timeout"] == 10
    assert props["ReservedConcurrentExecutions"] == 20
    env = props["Environment"]["Variables"]  # type: ignore[index]
    assert env["POWERTOOLS_LOGGER_LOG_EVENT"] == "false"
    assert env["STAGE"] == stage
    assert "PEPPER_SECRET_ARN" in env
    assert "TABLE_NAME" in env


def test_dev_has_a_launch_date(template: TemplateOf) -> None:
    (fn,) = our_functions(template, "dev").values()
    assert fn["Properties"]["Environment"]["Variables"]["LAUNCH_DATE"] == "2026-11-01"  # type: ignore[index]


@pytest.mark.parametrize("stage", STAGES)
def test_one_role_per_function(template: TemplateOf, stage: str) -> None:
    functions = resources(template(f"staysharp-{stage}-api"), "AWS::Lambda::Function")
    roles = [json.dumps(f["Properties"]["Role"], sort_keys=True) for f in functions.values()]
    assert len(roles) == len(set(roles))


@pytest.mark.parametrize("stage", STAGES)
def test_alias_live(template: TemplateOf, stage: str) -> None:
    (alias,) = resources(template(f"staysharp-{stage}-api"), "AWS::Lambda::Alias").values()
    assert alias["Properties"]["Name"] == "live"


@pytest.mark.parametrize("stage", STAGES)
def test_throttling_and_access_logs_without_ip(template: TemplateOf, stage: str) -> None:
    (api_stage,) = resources(
        template(f"staysharp-{stage}-api"), "AWS::ApiGatewayV2::Stage"
    ).values()
    props = api_stage["Properties"]
    assert props["DefaultRouteSettings"]["ThrottlingBurstLimit"] == 50
    assert props["DefaultRouteSettings"]["ThrottlingRateLimit"] == 20
    log_format = props["AccessLogSettings"]["Format"]
    assert "requestId" in log_format
    for forbidden in ("sourceIp", "userAgent", "identity", "header"):
        assert forbidden not in log_format


@pytest.mark.parametrize("stage", STAGES)
def test_every_log_group_keeps_30_days(template: TemplateOf, stage: str) -> None:
    groups = resources(template(f"staysharp-{stage}-api"), "AWS::Logs::LogGroup")
    assert len(groups) >= 2
    for group in groups.values():
        assert group["Properties"]["RetentionInDays"] == 30


@pytest.mark.parametrize("stage", STAGES)
def test_function_can_read_its_secret_and_table_only(template: TemplateOf, stage: str) -> None:
    text = json.dumps(resources(template(f"staysharp-{stage}-api"), "AWS::IAM::Policy"))
    assert "secretsmanager:GetSecretValue" in text
    assert "dynamodb:" in text
    assert '"Resource": "*"' not in text
