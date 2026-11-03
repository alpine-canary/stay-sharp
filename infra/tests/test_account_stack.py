"""Budget, OIDC roles and permissions (task T020, scenario V12, research R13)."""

from __future__ import annotations

import json
from typing import Any

import pytest
from aws_cdk import cx_api

from tests.conftest import TemplateOf, actions_of, all_policy_statements, resources

OWNER = "alpine-canary"


def test_one_budget_with_actual_and_forecast_alerts(template: TemplateOf) -> None:
    budgets = resources(template("staysharp-edge"), "AWS::Budgets::Budget")
    assert len(budgets) == 1
    (budget,) = budgets.values()
    props = budget["Properties"]
    assert props["Budget"]["BudgetLimit"] == {"Amount": 20, "Unit": "USD"}
    assert props["Budget"]["TimeUnit"] == "MONTHLY"
    notes = {
        (n["Notification"]["NotificationType"], n["Notification"]["Threshold"])
        for n in props["NotificationsWithSubscribers"]
    }
    assert notes == {("ACTUAL", 20), ("FORECASTED", 16)}
    for n in props["NotificationsWithSubscribers"]:
        assert n["Notification"]["ThresholdType"] == "ABSOLUTE_VALUE"
        assert n["Subscribers"][0]["SubscriptionType"] == "SNS"


def test_no_other_stack_has_a_budget(assembly: cx_api.CloudAssembly) -> None:
    for stack in assembly.stacks:
        if stack.stack_name != "staysharp-edge":
            assert "AWS::Budgets::Budget" not in json.dumps(stack.template)


def github_roles(template: TemplateOf) -> dict[str, Any]:
    """The four GitHub roles (named); CDK's own helper roles have no name."""
    roles = resources(template("staysharp-account"), "AWS::IAM::Role")
    return {
        k: v
        for k, v in roles.items()
        if str(v["Properties"].get("RoleName", "")).startswith("staysharp-github-")
    }


def role_subs(template: TemplateOf) -> dict[str, Any]:
    subs: dict[str, Any] = {}
    for role in github_roles(template).values():
        props = role["Properties"]
        (statement,) = props["AssumeRolePolicyDocument"]["Statement"]
        condition = statement["Condition"]
        assert set(condition) == {"StringEquals"}, "only exact matches, never StringLike"
        assert condition["StringEquals"]["token.actions.githubusercontent.com:aud"] == (
            "sts.amazonaws.com"
        )
        subs[props["RoleName"]] = condition["StringEquals"][
            "token.actions.githubusercontent.com:sub"
        ]
    return subs


def test_four_roles_each_trusted_by_one_exact_sub(template: TemplateOf) -> None:
    assert role_subs(template) == {
        "staysharp-github-diff": f"repo:{OWNER}/stay-sharp:pull_request",
        "staysharp-github-devdeploy": f"repo:{OWNER}/stay-sharp:ref:refs/heads/main",
        "staysharp-github-proddeploy": f"repo:{OWNER}/stay-sharp:environment:production",
        "staysharp-github-contentpublish": f"repo:{OWNER}/stay-sharp-content:ref:refs/heads/main",
    }


def statements_of_role(template: TemplateOf, role_name: str) -> list[dict[str, Any]]:
    t = template("staysharp-account")
    roles = github_roles(template)
    (logical_id,) = [k for k, v in roles.items() if v["Properties"]["RoleName"] == role_name]
    statements: list[dict[str, Any]] = []
    for policy in resources(t, "AWS::IAM::Policy").values():
        if {"Ref": logical_id} in policy["Properties"]["Roles"]:
            statements += policy["Properties"]["PolicyDocument"]["Statement"]
    return statements


READ_ONLY = (
    "cloudformation:Describe",
    "cloudformation:GetTemplate",
    "sts:AssumeRole",
    "ssm:GetParameter",
    "s3:GetObject",
)


def test_diff_role_has_no_write_action(template: TemplateOf) -> None:
    statements = statements_of_role(template, "staysharp-github-diff")
    assert statements
    for statement in statements:
        assert statement["Effect"] == "Allow"
        for action in actions_of(statement):
            assert action.startswith(READ_ONLY), action
            assert "*" not in action.split(":")[1] or action.startswith("cloudformation:")
        if "sts:AssumeRole" in actions_of(statement):
            assert "lookup-role" in json.dumps(statement["Resource"])


def test_content_role_writes_content_keys_only(template: TemplateOf) -> None:
    statements = statements_of_role(template, "staysharp-github-contentpublish")
    (dynamo,) = [s for s in statements if any(a.startswith("dynamodb:") for a in actions_of(s))]
    leading = dynamo["Condition"]["ForAllValues:StringLike"]["dynamodb:LeadingKeys"]
    assert sorted(leading) == ["DAILY#*", "POOL#*", "Q#*", "STOCK#*"]
    assert "staysharp-prod" in json.dumps(dynamo["Resource"])
    assert "dynamodb:DeleteItem" not in actions_of(dynamo)


@pytest.mark.parametrize(
    "stack",
    [
        "staysharp-account",
        "staysharp-edge",
        "staysharp-dev-api",
        "staysharp-prod-api",
        "staysharp-dev-web",
        "staysharp-prod-web",
        "staysharp-dev-data",
        "staysharp-prod-data",
    ],
)
def test_no_bedrock_and_no_admin_anywhere(template: TemplateOf, stack: str) -> None:
    for statement in all_policy_statements(template(stack)):
        for action in actions_of(statement):
            assert not action.lower().startswith("bedrock"), action
            assert action != "*", stack
        managed = json.dumps(template(stack).to_json())
        assert "AdministratorAccess" not in managed
