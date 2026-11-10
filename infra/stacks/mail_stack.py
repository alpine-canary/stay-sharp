"""Once per AWS account, in eu-central-2: the SES domain identity for lumineth.com (research A2).

Cognito sends the sign-in codes of both stages from ``stay-sharp@lumineth.com`` through this
identity. The DKIM records go into the ``lumineth.com`` zone, which is not in this account: the
maintainer adds them by hand (task T210, runbook ``docs/runbooks/account-setup.md`` section 5);
``make dkim-records`` prints them from the deployed identity.

While the account is in the SES sandbox, the senders can go out through the SMTP server of the
mailbox instead (context ``smtpHost``, see ``use_smtp``). Its login lives in the secret
``staysharp/smtp``, made here with a placeholder: the maintainer puts the real
``{"username", "password"}`` in it once (runbook ``docs/runbooks/account-setup.md`` section 7).
"""

from __future__ import annotations

import json
from typing import Any

from aws_cdk import CfnOutput, RemovalPolicy, Stack
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_secretsmanager as secretsmanager
from aws_cdk import aws_ses as ses
from constructs import Construct

MAIL_DOMAIN = "lumineth.com"
SENDER = f"stay-sharp@{MAIL_DOMAIN}"
SMTP_SECRET_NAME = "staysharp/smtp"  # noqa: S105 - a name, not a password


def use_smtp(fn: lambda_.Function, host: str) -> None:
    """Send ``fn``'s e-mail through ``host`` (staysharp.mail), logged in with the SMTP secret."""
    secret = secretsmanager.Secret.from_secret_name_v2(fn, "SmtpLogin", SMTP_SECRET_NAME)
    secret.grant_read(fn)
    fn.add_environment("SMTP_HOST", host)
    fn.add_environment("SMTP_SECRET_ID", SMTP_SECRET_NAME)


class MailStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs: Any) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.identity = ses.EmailIdentity(
            self,
            "Domain",
            identity=ses.Identity.domain(MAIL_DOMAIN),
            dkim_signing=True,
        )
        secretsmanager.Secret(
            self,
            "SmtpLogin",
            secret_name=SMTP_SECRET_NAME,
            description="SMTP login of the sender's mailbox: {username, password}, set by hand",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template=json.dumps({"username": SENDER}),
                generate_string_key="password",
                exclude_punctuation=True,
            ),
            removal_policy=RemovalPolicy.RETAIN,
        )
        CfnOutput(self, "MailDomain", value=MAIL_DOMAIN)
