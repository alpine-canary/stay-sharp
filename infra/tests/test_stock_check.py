"""Stock check function, its role, schedule and alarms (T092, FR-026, R8, R11, W8)."""

from __future__ import annotations

import json
from typing import Any

import pytest
from aws_cdk import assertions

from tests.conftest import TemplateOf, actions_of, resources
from tests.test_delivery import alarms, dims, function_named

STAGES = ("dev", "prod")


def ops(template: TemplateOf, stage: str) -> assertions.Template:
    return template(f"staysharp-{stage}-ops")


def statements_of(t: assertions.Template, role_key: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for policy in resources(t, "AWS::IAM::Policy").values():
        if {"Ref": role_key} in policy["Properties"]["Roles"]:
            found += policy["Properties"]["PolicyDocument"]["Statement"]
    return found


@pytest.mark.parametrize("stage", STAGES)
def test_the_function_runs_the_stock_handler(template: TemplateOf, stage: str) -> None:
    _, fn = function_named(ops(template, stage), f"staysharp-{stage}-stock-check")
    assert fn["Handler"] == "staysharp.handlers.stock_check.handler"
    variables = fn["Environment"]["Variables"]
    assert variables["STAGE"] == stage
    assert variables["TABLE_NAME"] == f"staysharp-{stage}"
    assert "POWERTOOLS_SERVICE_NAME" not in variables


@pytest.mark.parametrize("stage", STAGES)
def test_its_role_reads_stock_keys_only(template: TemplateOf, stage: str) -> None:
    t = ops(template, stage)
    _, fn = function_named(t, f"staysharp-{stage}-stock-check")
    role_key = fn["Role"]["Fn::GetAtt"][0]
    statements = statements_of(t, role_key)
    dynamo = [s for s in statements if any(a.startswith("dynamodb:") for a in actions_of(s))]
    assert len(dynamo) == 1
    (only,) = dynamo
    assert actions_of(only) == ["dynamodb:Query"]
    assert only["Condition"]["ForAllValues:StringLike"]["dynamodb:LeadingKeys"] == ["STOCK#*"]
    assert f"table/staysharp-{stage}" in json.dumps(only["Resource"])
    everything = [a for s in statements for a in actions_of(s)]
    assert all(a.startswith(("dynamodb:Query", "sns:Publish")) for a in everything), everything


@pytest.mark.parametrize("stage", STAGES)
def test_failures_go_to_the_alarm_topic(template: TemplateOf, stage: str) -> None:
    t = ops(template, stage)
    (config,) = resources(t, "AWS::Lambda::EventInvokeConfig").values()
    target = config["Properties"]["DestinationConfig"]["OnFailure"]["Destination"]
    (topic_key,) = resources(t, "AWS::SNS::Topic")
    assert target == {"Ref": topic_key}


@pytest.mark.parametrize("stage", STAGES)
def test_it_runs_once_a_day(template: TemplateOf, stage: str) -> None:
    t = ops(template, stage)
    (rule,) = resources(t, "AWS::Events::Rule").values()
    assert rule["Properties"]["ScheduleExpression"] == "cron(0 5 * * ? *)"
    key, _ = function_named(t, f"staysharp-{stage}-stock-check")
    (target,) = rule["Properties"]["Targets"]
    assert target["Arn"] == {"Fn::GetAtt": [key, "Arn"]}


@pytest.mark.parametrize(("stage", "threshold"), [("dev", 1), ("prod", 7)])
def test_low_stock_alarm_per_level_and_missing_data_breaches(
    template: TemplateOf, stage: str, threshold: int
) -> None:
    every = alarms(ops(template, stage)).values()
    found = [a for a in every if a["MetricName"] == "StockDaysAhead"]
    assert sorted(dims(a)["Level"] for a in found) == ["senior", "starter"]
    for alarm in found:
        assert dims(alarm)["Stage"] == stage
        assert alarm["ComparisonOperator"] == "LessThanThreshold"
        assert alarm["Threshold"] == threshold
        assert alarm["TreatMissingData"] == "breaching"
        assert alarm["Period"] == 86400
        assert alarm["Statistic"] == "Minimum"


@pytest.mark.parametrize("stage", STAGES)
def test_errors_and_a_missed_day_alarm(template: TemplateOf, stage: str) -> None:
    name = f"staysharp-{stage}-stock-check"
    found = {
        a["MetricName"]: a
        for a in alarms(ops(template, stage)).values()
        if dims(a).get("FunctionName") == name
    }
    assert set(found) == {"Errors", "Invocations"}
    assert found["Errors"]["TreatMissingData"] == "notBreaching"
    missed = found["Invocations"]
    assert missed["ComparisonOperator"] == "LessThanThreshold"
    assert missed["Threshold"] == 1
    assert missed["Period"] == 86400
    assert missed["TreatMissingData"] == "breaching"
