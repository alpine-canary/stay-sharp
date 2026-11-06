"""Canary, pre-traffic hook, rollback and paging alarms (T074, research R10, R11, V11)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from aws_cdk import assertions

from app import build_app
from stacks import api_stack
from stacks.bundling import copy_package
from tests.conftest import TemplateOf, actions_of, all_policy_statements, cdk_context, resources

STAGES = ("dev", "prod")


def api(template: TemplateOf, stage: str) -> assertions.Template:
    return template(f"staysharp-{stage}-api")


def group(t: assertions.Template) -> dict[str, Any]:
    (found,) = resources(t, "AWS::CodeDeploy::DeploymentGroup").values()
    props: dict[str, Any] = found["Properties"]
    return props


def alarms(t: assertions.Template) -> dict[str, dict[str, Any]]:
    return {k: v["Properties"] for k, v in resources(t, "AWS::CloudWatch::Alarm").items()}


def dims(alarm: dict[str, Any]) -> dict[str, Any]:
    return {d["Name"]: d["Value"] for d in alarm.get("Dimensions", [])}


def function_named(t: assertions.Template, name: str) -> tuple[str, dict[str, Any]]:
    for key, fn in resources(t, "AWS::Lambda::Function").items():
        if fn["Properties"].get("FunctionName") == name:
            return key, fn["Properties"]
    raise AssertionError(f"no function {name}")


@pytest.mark.parametrize(
    ("stage", "config"),
    [
        ("prod", "CodeDeployDefault.LambdaCanary10Percent5Minutes"),
        ("dev", "CodeDeployDefault.LambdaAllAtOnce"),
    ],
)
def test_deployment_config(template: TemplateOf, stage: str, config: str) -> None:
    props = group(api(template, stage))
    assert props["DeploymentConfigName"] == config
    assert set(props["AutoRollbackConfiguration"]["Events"]) >= {
        "DEPLOYMENT_FAILURE",
        "DEPLOYMENT_STOP_ON_ALARM",
    }


@pytest.mark.parametrize("stage", STAGES)
def test_rollback_alarms_are_version_scoped_and_fast(template: TemplateOf, stage: str) -> None:
    t = api(template, stage)
    attached = {a["Name"]["Ref"] for a in group(t)["AlarmConfiguration"]["Alarms"]}
    found = alarms(t)
    assert len(attached) == 3
    by_metric = {found[key]["MetricName"]: found[key] for key in attached}
    assert set(by_metric) == {"Errors", "ScoringFailures", "5xx"}
    for alarm in by_metric.values():
        assert alarm["Period"] == 60
        assert alarm["EvaluationPeriods"] == 1
        assert alarm["DatapointsToAlarm"] == 1
        assert alarm["TreatMissingData"] == "notBreaching"
        assert alarm["AlarmActions"], "each rollback alarm also notifies the maintainer"

    errors = dims(by_metric["Errors"])
    assert set(errors) == {"FunctionName", "Resource", "ExecutedVersion"}
    assert errors["ExecutedVersion"]["Fn::GetAtt"][1] == "Version"
    assert errors["Resource"] == {
        "Fn::Join": ["", [{"Ref": errors["FunctionName"]["Ref"]}, ":live"]]
    }
    scoring = dims(by_metric["ScoringFailures"])
    assert scoring["Stage"] == stage
    assert scoring["FunctionVersion"]["Fn::GetAtt"][1] == "Version"
    assert set(dims(by_metric["5xx"])) == {"ApiId", "Stage"}


@pytest.mark.parametrize("stage", STAGES)
def test_paging_alarm_sums_versions_and_is_not_a_rollback_alarm(
    template: TemplateOf, stage: str
) -> None:
    ops = alarms(template(f"staysharp-{stage}-ops"))
    paging = [a for a in ops.values() if a["MetricName"] == "ScoringFailures"]
    assert len(paging) == 1
    assert dims(paging[0]) == {"Stage": stage}
    assert paging[0]["Period"] == 60
    assert paging[0]["EvaluationPeriods"] == 5
    assert paging[0]["DatapointsToAlarm"] == 1
    # The API stack's deployment group can only reference alarms of its own stack.
    attached = group(api(template, stage))["AlarmConfiguration"]["Alarms"]
    assert all("Ref" in a["Name"] for a in attached)


@pytest.mark.parametrize("stage", STAGES)
def test_stage_alarms(template: TemplateOf, stage: str) -> None:
    names = {a["MetricName"] for a in alarms(template(f"staysharp-{stage}-ops")).values()}
    expected = {"ScoringFailures", "SelfCheckFailures", "Errors", "Throttles", "StockDaysAhead"}
    expected.add("Invocations")
    if stage == "dev":
        expected.add("FaultInjectionActive")
    assert names == expected
    cdn = alarms(template(f"staysharp-{stage}-cdn-alarms"))
    assert [a["MetricName"] for a in cdn.values()] == ["5xxErrorRate"]


@pytest.mark.parametrize("stage", STAGES)
def test_pre_traffic_hook_can_invoke_only_the_new_version(template: TemplateOf, stage: str) -> None:
    t = api(template, stage)
    key, hook = function_named(t, f"staysharp-{stage}-pre-traffic")
    target = hook["Environment"]["Variables"]["TARGET_FUNCTION_ARN"]
    assert "Ref" in target, "the qualified ARN of an AWS::Lambda::Version"
    version_key = target["Ref"]
    assert resources(t, "AWS::Lambda::Version")[version_key]

    role = hook["Role"]["Fn::GetAtt"][0]
    invokes = [
        s
        for p in resources(t, "AWS::IAM::Policy").values()
        if {"Ref": role} in p["Properties"]["Roles"]
        for s in p["Properties"]["PolicyDocument"]["Statement"]
        if "lambda:InvokeFunction" in actions_of(s)
    ]
    assert invokes == [
        {"Action": "lambda:InvokeFunction", "Effect": "Allow", "Resource": {"Ref": version_key}}
    ]
    assert group(t)["DeploymentStyle"]["DeploymentType"] == "BLUE_GREEN"
    del key


@pytest.mark.parametrize("stage", STAGES)
def test_failed_and_rolled_back_deployments_reach_the_maintainer(
    template: TemplateOf, stage: str
) -> None:
    (trigger,) = group(api(template, stage))["TriggerConfigurations"]
    assert set(trigger["TriggerEvents"]) == {"DeploymentFailure", "DeploymentRollback"}
    hook_config = resources(api(template, stage), "AWS::Lambda::EventInvokeConfig")
    (config,) = hook_config.values()
    assert config["Properties"]["MaximumRetryAttempts"] == 0
    assert "OnFailure" in config["Properties"]["DestinationConfig"]


@pytest.mark.parametrize("stage", STAGES)
def test_alarm_topics_let_cloudwatch_publish(template: TemplateOf, stage: str) -> None:
    statements = all_policy_statements(template(f"staysharp-{stage}-ops"))
    for policy in resources(template(f"staysharp-{stage}-ops"), "AWS::SNS::TopicPolicy").values():
        statements += policy["Properties"]["PolicyDocument"]["Statement"]
    assert any(
        s.get("Principal") == {"Service": "cloudwatch.amazonaws.com"} and s["Effect"] == "Allow"
        for s in statements
    )


def test_prod_runs_the_plain_handler_and_dev_the_drill_wrapper(template: TemplateOf) -> None:
    _, prod = function_named(api(template, "prod"), "staysharp-prod-api")
    _, dev = function_named(api(template, "dev"), "staysharp-dev-api")
    assert prod["Handler"] == api_stack.API_HANDLER
    assert dev["Handler"] == api_stack.DEV_HANDLER
    assert "STAYSHARP_DRILL" not in prod["Environment"]["Variables"]
    assert prod["Code"]["S3Key"] != dev["Code"]["S3Key"], "prod never reuses the dev bundle"
    prod_text = json.dumps(api(template, "prod").to_json())
    assert "fault-injection" not in prod_text


def test_prod_asset_has_no_fault_injection_file(tmp_path: Path) -> None:
    copy_package(tmp_path / "prod", with_testing=False)
    copy_package(tmp_path / "dev", with_testing=True)
    assert not list((tmp_path / "prod").rglob("fault_injection*"))
    assert (tmp_path / "prod" / "staysharp" / "selfcheck" / "fixtures" / "questions.json").exists()
    assert (tmp_path / "dev" / "testing" / "fault_injection.py").exists()
    assert not list((tmp_path / "prod").rglob("tools"))


def test_drill_context_reaches_dev_only() -> None:
    context = {
        **cdk_context(),
        "drill": "fail-traffic",
        "devDeploymentConfig": "LambdaCanary10Percent5Minutes",
    }
    assembly = build_app(context).synth()
    dev = assertions.Template.from_json(assembly.get_stack_by_name("staysharp-dev-api").template)
    prod = assertions.Template.from_json(assembly.get_stack_by_name("staysharp-prod-api").template)
    _, dev_fn = function_named(dev, "staysharp-dev-api")
    _, prod_fn = function_named(prod, "staysharp-prod-api")
    assert dev_fn["Environment"]["Variables"]["STAYSHARP_DRILL"] == "fail-traffic"
    assert "STAYSHARP_DRILL" not in prod_fn["Environment"]["Variables"]
    assert group(dev)["DeploymentConfigName"] == "CodeDeployDefault.LambdaCanary10Percent5Minutes"


def test_prod_refuses_drills() -> None:
    from aws_cdk import App, Stack
    from aws_cdk import aws_cognito as cognito
    from aws_cdk import aws_dynamodb as dynamodb
    from aws_cdk import aws_secretsmanager as secretsmanager
    from aws_cdk import aws_sns as sns

    app = App(context={"aws:cdk:bundling-stacks": []})
    base = Stack(app, "base")
    table = dynamodb.TableV2(
        base, "T", partition_key=dynamodb.Attribute(name="PK", type=dynamodb.AttributeType.STRING)
    )
    secret = secretsmanager.Secret(base, "S")
    topic = sns.Topic(base, "Topic")
    pool = cognito.UserPool(base, "Pool")
    client = pool.add_client("Client")
    with pytest.raises(ValueError, match="prod"):
        api_stack.ApiStack(
            app,
            "p",
            stage="prod",
            table=table,
            pepper=secret,
            launch_date=None,
            topic=topic,
            user_pool=pool,
            user_pool_client=client,
            drill="fail-traffic",
        )


@pytest.mark.parametrize("stage", STAGES)
def test_alias_waits_for_codedeploy_permissions(template: TemplateOf, stage: str) -> None:
    t = api(template, stage)
    (alias,) = resources(t, "AWS::Lambda::Alias").values()
    policies = resources(t, "AWS::IAM::Policy")
    waits_for = set(alias.get("DependsOn", []))
    invoke_hook = [
        k
        for k, p in policies.items()
        if any(
            "lambda:InvokeFunction" in actions_of(s)
            for s in p["Properties"]["PolicyDocument"]["Statement"]
        )
        and k.startswith("DeploymentServiceRole")
    ]
    assert invoke_hook
    assert set(invoke_hook) <= waits_for


@pytest.mark.parametrize("stage", STAGES)
def test_no_powertools_service_variable(template: TemplateOf, stage: str) -> None:
    """It would add a "service" dimension and the alarms would never match (fault drill V8)."""
    for fn in resources(api(template, stage), "AWS::Lambda::Function").values():
        variables = fn["Properties"].get("Environment", {}).get("Variables", {})
        assert "POWERTOOLS_SERVICE_NAME" not in variables
