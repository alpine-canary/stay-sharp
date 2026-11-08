"""Sign-in settings per stage (tasks T204, T205; research A1 to A3)."""

from __future__ import annotations

import json
import re
from typing import Any

import pytest
from aws_cdk import assertions

from app import build_app
from tests.conftest import TemplateOf, cdk_context, resources


def pool(t: assertions.Template) -> dict[str, Any]:
    (found,) = resources(t, "AWS::Cognito::UserPool").values()
    result: dict[str, Any] = found
    return result


def client(t: assertions.Template) -> dict[str, Any]:
    (found,) = resources(t, "AWS::Cognito::UserPoolClient").values()
    props: dict[str, Any] = found["Properties"]
    return props


@pytest.mark.parametrize("stage", ["dev", "prod"])
def test_passwordless_sign_in(template: TemplateOf, stage: str) -> None:
    props = pool(template(f"staysharp-{stage}-auth"))["Properties"]
    assert props["UserPoolName"] == f"staysharp-{stage}"
    assert props["UserPoolTier"] == "ESSENTIALS"
    # Cognito needs PASSWORD in the list; players never get one (sign-up sends no password and
    # the app client allows only USER_AUTH, where a user without a password cannot pick it).
    factors = props["Policies"]["SignInPolicy"]["AllowedFirstAuthFactors"]
    assert "EMAIL_OTP" in factors
    assert set(factors) <= {"PASSWORD", "EMAIL_OTP", "WEB_AUTHN"}
    assert props["MfaConfiguration"] == "OFF"
    assert props["AdminCreateUserConfig"]["AllowAdminCreateUserOnly"] is False
    assert props["UsernameAttributes"] == ["email"]
    assert props["UsernameConfiguration"] == {"CaseSensitive": False}
    assert props["AutoVerifiedAttributes"] == ["email"]
    assert props["AccountRecoverySetting"]["RecoveryMechanisms"] == [
        {"Name": "admin_only", "Priority": 1}
    ]


@pytest.mark.parametrize("stage", ["dev", "prod"])
def test_codes_leave_from_zurich_through_our_sender(template: TemplateOf, stage: str) -> None:
    t = template(f"staysharp-{stage}-auth")
    props = pool(t)["Properties"]
    # Cognito never mails by itself (in eu-central-2 it could only use SES in Frankfurt or
    # London): every code goes, KMS-encrypted, to the sender function in this Region.
    assert props.get("EmailConfiguration", {}).get("EmailSendingAccount", "COGNITO_DEFAULT") == (
        "COGNITO_DEFAULT"
    )
    assert "SourceArn" not in props.get("EmailConfiguration", {})
    triggers = props["LambdaConfig"]
    assert "CustomEmailSender" in triggers
    assert "KMSKeyID" in triggers
    (fn,) = [
        f["Properties"]
        for f in resources(t, "AWS::Lambda::Function").values()
        if f["Properties"].get("FunctionName") == f"staysharp-{stage}-mail-sender"
    ]
    assert fn["Handler"] == "staysharp.handlers.mail_sender.handler"
    assert fn["Environment"]["Variables"]["SENDER"] == "stay-sharp@lumineth.com"
    policies = json.dumps(resources(t, "AWS::IAM::Policy"))
    assert '"ses:SendEmail"' in policies
    assert ":identity/*" in policies
    assert '"ses:FromAddress": "stay-sharp@lumineth.com"' in policies
    (key,) = resources(t, "AWS::KMS::Key").values()
    assert key["Properties"]["EnableKeyRotation"] is True
    assert key["DeletionPolicy"] == ("Retain" if stage == "prod" else "Delete")


def test_app_client_is_public_and_user_auth_only(template: TemplateOf) -> None:
    props = client(template("staysharp-prod-auth"))
    assert props.get("GenerateSecret") in (None, False)
    assert sorted(props["ExplicitAuthFlows"]) == ["ALLOW_REFRESH_TOKEN_AUTH", "ALLOW_USER_AUTH"]
    assert props["PreventUserExistenceErrors"] == "ENABLED"
    assert props["EnableTokenRevocation"] is True
    assert props.get("AllowedOAuthFlowsUserPoolClient") in (None, False)
    assert props["AccessTokenValidity"] == 60
    assert props["TokenValidityUnits"]["AccessToken"] == "minutes"
    assert props["RefreshTokenValidity"] == 30 * 24 * 60
    # The client reads nothing about the user but the e-mail (needed by the account page).
    assert props["ReadAttributes"] == ["email", "email_verified"]
    assert props["WriteAttributes"] == ["email"]


def test_passkeys_bound_to_the_public_host_in_prod(template: TemplateOf) -> None:
    props = pool(template("staysharp-prod-auth"))["Properties"]
    assert props["WebAuthnRelyingPartyID"] == "stay-sharp.lumineth.com"
    assert "WEB_AUTHN" in props["Policies"]["SignInPolicy"]["AllowedFirstAuthFactors"]


def test_dev_passkeys_wait_for_the_dev_host() -> None:
    # The dev CloudFront host is known only after the first web deploy (context devSiteHost).
    context = {k: v for k, v in cdk_context().items() if k not in ("devSiteHost", "devPublicName")}
    stack = build_app(context).synth().get_stack_by_name("staysharp-dev-auth")
    props = pool(assertions.Template.from_json(stack.template))["Properties"]
    assert "WebAuthnRelyingPartyID" not in props
    assert "WEB_AUTHN" not in props["Policies"]["SignInPolicy"]["AllowedFirstAuthFactors"]


def test_dev_passkeys_with_the_dev_host() -> None:
    context = cdk_context() | {"devSiteHost": "d1234abcd.cloudfront.net", "devPublicName": False}
    stack = build_app(context).synth().get_stack_by_name("staysharp-dev-auth")
    props = pool(assertions.Template.from_json(stack.template))["Properties"]
    assert props["WebAuthnRelyingPartyID"] == "d1234abcd.cloudfront.net"
    assert "WEB_AUTHN" in props["Policies"]["SignInPolicy"]["AllowedFirstAuthFactors"]


def test_dev_passkeys_on_the_public_name_while_dev_has_it() -> None:
    context = cdk_context() | {"devSiteHost": "d1234abcd.cloudfront.net", "devPublicName": True}
    stack = build_app(context).synth().get_stack_by_name("staysharp-dev-auth")
    props = pool(assertions.Template.from_json(stack.template))["Properties"]
    assert props["WebAuthnRelyingPartyID"] == "stay-sharp.lumineth.com"


def test_deletion_protection_and_retention_in_prod_only(template: TemplateOf) -> None:
    prod = pool(template("staysharp-prod-auth"))
    dev = pool(template("staysharp-dev-auth"))
    assert prod["Properties"]["DeletionProtection"] == "ACTIVE"
    assert prod["DeletionPolicy"] == "Retain"
    assert dev["Properties"].get("DeletionProtection", "INACTIVE") == "INACTIVE"
    assert dev["DeletionPolicy"] == "Delete"


def test_one_ses_domain_identity_per_account(template: TemplateOf) -> None:
    (identity,) = resources(template("staysharp-mail"), "AWS::SES::EmailIdentity").values()
    props = identity["Properties"]
    assert props["EmailIdentity"] == "lumineth.com"
    assert props["DkimAttributes"] == {"SigningEnabled": True}
    for stage in ("dev", "prod"):
        assert not resources(template(f"staysharp-{stage}-auth"), "AWS::SES::EmailIdentity")


@pytest.mark.parametrize("stack", ["staysharp-dev-auth", "staysharp-prod-auth", "staysharp-mail"])
def test_no_output_shows_an_account_id(template: TemplateOf, stack: str) -> None:
    outputs = json.dumps(template(stack).to_json().get("Outputs", {}))
    assert not re.search(r"\b\d{12}\b", outputs)


@pytest.mark.parametrize("stage", ["dev", "prod"])
def test_the_sender_counts_its_e_mails_under_its_own_keys_only(
    template: TemplateOf, stage: str
) -> None:
    t = template(f"staysharp-{stage}-auth")
    functions = resources(t, "AWS::Lambda::Function")
    (mailer,) = [
        f
        for f in functions.values()
        if f["Properties"].get("FunctionName") == f"staysharp-{stage}-mail-sender"
    ]
    env = mailer["Properties"]["Environment"]["Variables"]
    assert "TABLE_NAME" in env
    assert "PEPPER_SECRET_ARN" in env
    statements = [
        s
        for p in resources(t, "AWS::IAM::Policy").values()
        for s in p["Properties"]["PolicyDocument"]["Statement"]
    ]
    dynamo = [s for s in statements if "dynamodb:" in json.dumps(s["Action"])]
    assert len(dynamo) == 1
    (statement,) = dynamo
    assert statement["Action"] == "dynamodb:UpdateItem"
    assert statement["Condition"] == {
        "ForAllValues:StringLike": {"dynamodb:LeadingKeys": ["MAIL#*"]}
    }


@pytest.mark.parametrize("stage", ["dev", "prod"])
def test_the_maintainer_hears_when_codes_do_not_go_out(template: TemplateOf, stage: str) -> None:
    t = template(f"staysharp-{stage}-auth")
    alarms = {
        a["Properties"]["MetricName"]: a["Properties"]
        for a in resources(t, "AWS::CloudWatch::Alarm").values()
    }
    assert alarms["Errors"]["Dimensions"] == [
        {"Name": "FunctionName", "Value": f"staysharp-{stage}-mail-sender"}
    ]
    assert alarms["SignInMailLimited"]["Threshold"] == 20
    assert all(a["AlarmActions"] for a in alarms.values())
    (metric_filter,) = resources(t, "AWS::Logs::MetricFilter").values()
    assert "sign-in e-mail limited" in metric_filter["Properties"]["FilterPattern"]


def test_a_new_address_replaces_the_old_one_only_once_verified(template: TemplateOf) -> None:
    props = pool(template("staysharp-prod-auth"))["Properties"]
    assert props["UserAttributeUpdateSettings"] == {
        "AttributesRequireVerificationBeforeUpdate": ["email"]
    }
