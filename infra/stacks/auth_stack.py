"""Per-stage sign-in: the Cognito user pool and the website's app client (tasks T205; A1 to A3).

- Essentials plan, choice-based sign-in (``USER_AUTH``) with an e-mail code and, once the
  site's host is known, passkeys. Cognito requires ``PASSWORD`` in the allowed first factors,
  but players never have one: the website signs up without a password and the app client allows
  only ``USER_AUTH`` (and refresh), so a password challenge is never offered.
- E-mail as the user name, case-insensitive; no password recovery (there is no password);
  MFA off (Cognito does not combine MFA with passwordless sign-in).
- Codes leave from Zurich: a pool in eu-central-2 may only use SES in Frankfurt or London, so
  Cognito encrypts each code with the stage's KMS key and hands it to a custom e-mail sender
  function here, which sends it with SES in eu-central-2 from ``stay-sharp@lumineth.com``
  (identity in the mail stack; handler ``staysharp.handlers.mail_sender``).
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
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_kms as kms
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

from stacks.bundling import mailer_code
from stacks.mail_stack import SENDER

MAILER_HANDLER = "staysharp.handlers.mail_sender.handler"


class AuthStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        stage: str,
        site_host: str | None,
        table: dynamodb.ITableV2,
        pepper: secretsmanager.ISecret,
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        prod = stage == "prod"
        passkeys = site_host is not None
        removal = RemovalPolicy.RETAIN if prod else RemovalPolicy.DESTROY

        self.code_key = kms.Key(
            self,
            "CodeKey",
            alias=f"staysharp-{stage}-signin-codes",
            description="Encrypts sign-in codes between Cognito and the e-mail sender",
            enable_key_rotation=True,
            removal_policy=removal,
        )
        self.code_key.add_to_resource_policy(
            iam.PolicyStatement(
                principals=[iam.ServicePrincipal("cognito-idp.amazonaws.com")],
                actions=["kms:Encrypt"],
                resources=["*"],
                conditions={"StringEquals": {"aws:SourceAccount": self.account}},
            )
        )
        # Cognito creates a grant on the key with the deploying role's rights. The key policy
        # lets the CDK deploy role do exactly that, only through Cognito, so the execution
        # policy itself needs no KMS grant rights.
        self.code_key.add_to_resource_policy(
            iam.PolicyStatement(
                principals=[
                    iam.ArnPrincipal(
                        f"arn:{self.partition}:iam::{self.account}:role/"
                        f"cdk-hnb659fds-cfn-exec-role-{self.account}-{self.region}"
                    )
                ],
                actions=["kms:CreateGrant", "kms:DescribeKey"],
                resources=["*"],
                conditions={
                    "StringEquals": {"kms:ViaService": f"cognito-idp.{self.region}.amazonaws.com"}
                },
            )
        )
        name = f"staysharp-{stage}-mail-sender"
        self.mailer = lambda_.Function(
            self,
            "MailSender",
            function_name=name,
            runtime=lambda_.Runtime.PYTHON_3_13,
            architecture=lambda_.Architecture.ARM_64,
            handler=MAILER_HANDLER,
            code=mailer_code(stage),
            memory_size=256,
            timeout=Duration.seconds(10),
            environment={
                "STAGE": stage,
                "SENDER": SENDER,
                "KEY_ARN": self.code_key.key_arn,
                "TABLE_NAME": table.table_name,
                "PEPPER_SECRET_ARN": pepper.secret_arn,
                "POWERTOOLS_SERVICE_NAME": "mail-sender",
                "POWERTOOLS_LOGGER_LOG_EVENT": "false",
            },
            log_group=logs.LogGroup(
                self,
                "MailSenderLogs",
                log_group_name=f"/aws/lambda/{name}",
                retention=logs.RetentionDays.ONE_MONTH,
                removal_policy=removal,
            ),
            logging_format=lambda_.LoggingFormat.JSON,
        )
        self.code_key.grant_decrypt(self.mailer)
        # The send counters (store/mail_limits.py): their own keys only, never player data.
        pepper.grant_read(self.mailer)
        self.mailer.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:UpdateItem"],
                resources=[table.table_arn],
                conditions={"ForAllValues:StringLike": {"dynamodb:LeadingKeys": ["MAIL#*"]}},
            )
        )
        self.mailer.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ses:SendEmail"],
                # SES checks the sender's identity and, while the account is in the SES
                # sandbox, the recipient's too: any identity of this account, but only ever
                # from our address.
                resources=[self.format_arn(service="ses", resource="identity", resource_name="*")],
                conditions={"StringEquals": {"ses:FromAddress": SENDER}},
            )
        )

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
            # Cognito never sends mail itself: every code goes through the sender above.
            email=cognito.UserPoolEmail.with_cognito(),
            custom_sender_kms_key=self.code_key,
            lambda_triggers=cognito.UserPoolTriggers(custom_email_sender=self.mailer),
            user_verification=cognito.UserVerificationConfig(
                email_style=cognito.VerificationEmailStyle.CODE,
            ),
            deletion_protection=prod,
            removal_policy=removal,
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
