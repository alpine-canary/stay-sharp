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
def test_mail_goes_through_ses_from_lumineth(template: TemplateOf, stage: str) -> None:
    email = pool(template(f"staysharp-{stage}-auth"))["Properties"]["EmailConfiguration"]
    assert email["EmailSendingAccount"] == "DEVELOPER"
    assert email["From"] == "Stay Sharp <stay-sharp@lumineth.com>"
    assert ":identity/lumineth.com" in json.dumps(email["SourceArn"])


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


def test_dev_passkeys_wait_for_the_dev_host(template: TemplateOf) -> None:
    # The dev CloudFront host is known only after the first web deploy (context devSiteHost).
    props = pool(template("staysharp-dev-auth"))["Properties"]
    assert "WebAuthnRelyingPartyID" not in props
    assert "WEB_AUTHN" not in props["Policies"]["SignInPolicy"]["AllowedFirstAuthFactors"]


def test_dev_passkeys_with_the_dev_host() -> None:
    context = cdk_context() | {"devSiteHost": "d1234abcd.cloudfront.net"}
    stack = build_app(context).synth().get_stack_by_name("staysharp-dev-auth")
    props = pool(assertions.Template.from_json(stack.template))["Properties"]
    assert props["WebAuthnRelyingPartyID"] == "d1234abcd.cloudfront.net"
    assert "WEB_AUTHN" in props["Policies"]["SignInPolicy"]["AllowedFirstAuthFactors"]


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
