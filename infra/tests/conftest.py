"""Synthesize the whole app once, as the CLI would, but without credentials or bundling."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from aws_cdk import assertions, cx_api

from app import build_app

CDK_JSON = Path(__file__).resolve().parents[1] / "cdk.json"


def cdk_context() -> dict[str, Any]:
    context: dict[str, Any] = json.loads(CDK_JSON.read_text())["context"]
    # Skip asset bundling (uv, wheels) in unit tests: templates are what we check.
    context["aws:cdk:bundling-stacks"] = []
    return context


@pytest.fixture(scope="session")
def assembly() -> cx_api.CloudAssembly:
    return build_app(cdk_context()).synth()


TemplateOf = Callable[[str], assertions.Template]


@pytest.fixture(scope="session")
def template(assembly: cx_api.CloudAssembly) -> TemplateOf:
    cache: dict[str, assertions.Template] = {}

    def get(stack_name: str) -> assertions.Template:
        if stack_name not in cache:
            artifact = assembly.get_stack_by_name(stack_name)
            cache[stack_name] = assertions.Template.from_json(artifact.template)
        return cache[stack_name]

    return get


def resources(t: assertions.Template, kind: str) -> dict[str, Any]:
    found: dict[str, Any] = dict(t.find_resources(kind))
    return found


def all_policy_statements(t: assertions.Template) -> list[dict[str, Any]]:
    statements: list[dict[str, Any]] = []
    for policy in resources(t, "AWS::IAM::Policy").values():
        statements += policy["Properties"]["PolicyDocument"]["Statement"]
    for role in resources(t, "AWS::IAM::Role").values():
        for inline in role["Properties"].get("Policies", []):
            statements += inline["PolicyDocument"]["Statement"]
    return statements


def actions_of(statement: dict[str, Any]) -> list[str]:
    action = statement.get("Action", [])
    return [action] if isinstance(action, str) else list(action)
