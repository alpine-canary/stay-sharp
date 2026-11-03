"""The CDK execution policy is narrow (task T016, research R13): never an account admin."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

POLICY = Path(__file__).resolve().parents[1] / "bootstrap" / "execution-policy.json"


def statements() -> list[dict[str, Any]]:
    data: dict[str, Any] = json.loads(POLICY.read_text())
    result: list[dict[str, Any]] = data["Statement"]
    return result


def actions(statement: dict[str, Any]) -> list[str]:
    value = statement["Action"]
    return [value] if isinstance(value, str) else list(value)


def test_no_full_admin_and_no_iam_wildcard() -> None:
    for statement in statements():
        if statement["Effect"] != "Allow":
            continue
        for action in actions(statement):
            assert action != "*"
            assert action not in ("iam:*", "sts:*", "organizations:*", "kms:*")
            assert not action.startswith("bedrock")


def test_role_changes_are_limited_to_project_roles() -> None:
    for statement in statements():
        if statement["Effect"] != "Allow":
            continue
        role_actions = [a for a in actions(statement) if a.startswith("iam:") and "Role" in a]
        role_actions = [a for a in role_actions if a != "iam:CreateServiceLinkedRole"]
        if role_actions:
            assert statement["Resource"] == ["arn:aws:iam::*:role/staysharp-*"]


def test_bedrock_is_explicitly_denied() -> None:
    denied = [a for s in statements() if s["Effect"] == "Deny" for a in actions(s)]
    assert "bedrock:*" in denied
    assert "iam:CreateUser" in denied


def test_every_stack_role_name_fits_the_allowed_prefix(template: Any) -> None:
    from aws_cdk import cx_api  # noqa: F401 - imported for the fixture type only

    # Role names CDK generates start with the stack name; named roles start with staysharp-.
    from tests.conftest import resources

    for stack in ("staysharp-account", "staysharp-dev-api", "staysharp-dev-web"):
        for role in resources(template(stack), "AWS::IAM::Role").values():
            name = role["Properties"].get("RoleName")
            assert name is None or str(name).startswith("staysharp-")
