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


# --- accounts (M2: tasks T206, T207) ---------------------------------------------------------


def routes(template: TemplateOf, stage: str) -> dict[str, dict[str, object]]:
    found = resources(template(f"staysharp-{stage}-api"), "AWS::ApiGatewayV2::Route")
    return {r["Properties"]["RouteKey"]: r["Properties"] for r in found.values()}


@pytest.mark.parametrize("stage", STAGES)
def test_jwt_authorizer_bound_to_the_stage_pool_and_client(
    template: TemplateOf, stage: str
) -> None:
    (authorizer,) = resources(
        template(f"staysharp-{stage}-api"), "AWS::ApiGatewayV2::Authorizer"
    ).values()
    props = authorizer["Properties"]
    assert props["AuthorizerType"] == "JWT"
    assert props["IdentitySource"] == ["$request.header.Authorization"]
    text = json.dumps(props["JwtConfiguration"])
    assert "cognito-idp.eu-central-2.amazonaws.com" in text
    assert "PlayersWebsite" in json.dumps(props["JwtConfiguration"]["Audience"])


@pytest.mark.parametrize("stage", STAGES)
def test_only_account_routes_need_a_token(template: TemplateOf, stage: str) -> None:
    found = routes(template, stage)
    account = {key for key in found if key.split(" ")[-1].startswith("/api/v1/me")}
    assert account == {
        "GET /api/v1/me",
        "PUT /api/v1/me",
        "DELETE /api/v1/me",
        "POST /api/v1/me/adopt",
        "GET /api/v1/me/progress",
        "PUT /api/v1/me/progress",
    }
    for key, props in found.items():
        if key in account:
            assert props["AuthorizationType"] == "JWT", key
        else:
            assert props.get("AuthorizationType", "NONE") == "NONE", key
    # M1 routes keep going through the open default route.
    assert "$default" in found


def _statements_of_role(template: TemplateOf, stage: str, function_name: str) -> list[object]:
    t = template(f"staysharp-{stage}-api")
    functions = resources(t, "AWS::Lambda::Function")
    (fn,) = [f for f in functions.values() if f["Properties"].get("FunctionName") == function_name]
    role_id = fn["Properties"]["Role"]["Fn::GetAtt"][0]
    statements: list[object] = []
    for policy in resources(t, "AWS::IAM::Policy").values():
        if {"Ref": role_id} in policy["Properties"]["Roles"]:
            statements += policy["Properties"]["PolicyDocument"]["Statement"]
    return statements


@pytest.mark.parametrize("stage", STAGES)
def test_the_api_role_cannot_call_cognito(template: TemplateOf, stage: str) -> None:
    text = json.dumps(_statements_of_role(template, stage, f"staysharp-{stage}-api"))
    assert "cognito-idp" not in text


@pytest.mark.parametrize("stage", STAGES)
def test_only_the_delete_function_deletes_cognito_users(template: TemplateOf, stage: str) -> None:
    statements = _statements_of_role(template, stage, f"staysharp-{stage}-account-delete")
    cognito = [s for s in statements if "cognito-idp" in json.dumps(s)]
    assert len(cognito) == 1
    (statement,) = cognito
    assert statement["Action"] == "cognito-idp:AdminDeleteUser"  # type: ignore[index]
    # The stage's own pool, never "*".
    assert "PlayersCF26CFA0Arn" in json.dumps(statement["Resource"])  # type: ignore[index]
    everything = json.dumps(resources(template(f"staysharp-{stage}-api"), "AWS::IAM::Policy"))
    assert everything.count("cognito-idp:") == 1


@pytest.mark.parametrize("stage", STAGES)
def test_delete_route_goes_to_the_delete_function(template: TemplateOf, stage: str) -> None:
    t = template(f"staysharp-{stage}-api")
    target = json.dumps(routes(template, stage)["DELETE /api/v1/me"]["Target"])
    integrations = resources(t, "AWS::ApiGatewayV2::Integration")
    (logical,) = [k for k in integrations if k in target]
    uri = json.dumps(integrations[logical]["Properties"]["IntegrationUri"])
    functions = resources(t, "AWS::Lambda::Function")
    (delete_id,) = [
        k
        for k, f in functions.items()
        if f["Properties"].get("FunctionName") == f"staysharp-{stage}-account-delete"
    ]
    assert delete_id in uri
