"""Per-stage sign-in: the Cognito user pool and the website's app client (tasks T205; A1 to A3).

- Essentials plan, choice-based sign-in (``USER_AUTH``) with an e-mail code and, once the
  site's host is known, passkeys. Cognito requires ``PASSWORD`` in the allowed first factors,
  but players never have one: the website signs up without a password and the app client allows
  only ``USER_AUTH`` (and refresh), so a password challenge is never offered.
- E-mail as the user name, case-insensitive; no password recovery (there is no password);
  MFA off (Cognito does not combine MFA with passwordless sign-in).
- Codes are sent by SES from ``stay-sharp@lumineth.com`` (identity in the mail stack).
- Passkeys belong to the site's host (relying party id): the public name in prod, the dev
  CloudFront host in dev, given as context ``devSiteHost`` after the first web deploy.
- Prod: deletion protection and retained on stack removal. Dev: removable.

Outputs carry the pool and client ids (not secrets, no account id): the web stack writes them
to ``/auth.json`` for the account pages.
"""

from __future__ import annotations

from typing import Any

from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_cognito as cognito
from constructs import Construct

from stacks.mail_stack import MAIL_DOMAIN, SENDER


class AuthStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        stage: str,
        site_host: str | None,
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        prod = stage == "prod"
        passkeys = site_host is not None

        self.user_pool = cognito.UserPool(
            self,
            "Players",
            user_pool_name=f"staysharp-{stage}",
            feature_plan=cognito.FeaturePlan.ESSENTIALS,
            self_sign_up_enabled=True,
            sign_in_aliases=cognito.SignInAliases(email=True),
            sign_in_case_sensitive=False,
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(required=True, mutable=True)
            ),
            sign_in_policy=cognito.SignInPolicy(
                allowed_first_auth_factors=cognito.AllowedFirstAuthFactors(
                    password=True, email_otp=True, passkey=passkeys
                )
            ),
            passkey_relying_party_id=site_host,
            mfa=cognito.Mfa.OFF,
            account_recovery=cognito.AccountRecovery.NONE,
            email=cognito.UserPoolEmail.with_ses(
                from_email=SENDER,
                from_name="Stay Sharp",
                ses_verified_domain=MAIL_DOMAIN,
                ses_region=self.region,
            ),
            user_verification=cognito.UserVerificationConfig(
                email_subject="Your Stay Sharp code",
                email_body="Your Stay Sharp code is {####}. It works for 10 minutes.",
                email_style=cognito.VerificationEmailStyle.CODE,
            ),
            deletion_protection=prod,
            removal_policy=RemovalPolicy.RETAIN if prod else RemovalPolicy.DESTROY,
        )

        self.client = self.user_pool.add_client(
            "Website",
            user_pool_client_name=f"staysharp-{stage}-website",
            generate_secret=False,
            auth_flows=cognito.AuthFlow(user=True),
            disable_o_auth=True,
            prevent_user_existence_errors=True,
            enable_token_revocation=True,
            access_token_validity=Duration.hours(1),
            id_token_validity=Duration.hours(1),
            refresh_token_validity=Duration.days(30),
            read_attributes=cognito.ClientAttributes().with_standard_attributes(
                email=True, email_verified=True
            ),
            write_attributes=cognito.ClientAttributes().with_standard_attributes(email=True),
        )

        CfnOutput(self, "UserPoolId", value=self.user_pool.user_pool_id)
        CfnOutput(self, "ClientId", value=self.client.user_pool_client_id)
