"""Once per AWS account, in eu-central-2: the SES domain identity for lumineth.com (research A2).

Cognito sends the sign-in codes of both stages from ``stay-sharp@lumineth.com`` through this
identity. The DKIM records go into the ``lumineth.com`` zone, which is not in this account: the
maintainer adds them by hand (task T210, runbook ``docs/runbooks/account-setup.md`` section 5);
``make dkim-records`` prints them from the deployed identity.
"""

from __future__ import annotations

from typing import Any

from aws_cdk import CfnOutput, Stack
from aws_cdk import aws_ses as ses
from constructs import Construct

MAIL_DOMAIN = "lumineth.com"
SENDER = f"stay-sharp@{MAIL_DOMAIN}"


class MailStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs: Any) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.identity = ses.EmailIdentity(
            self,
            "Domain",
            identity=ses.Identity.domain(MAIL_DOMAIN),
            dkim_signing=True,
        )
        CfnOutput(self, "MailDomain", value=MAIL_DOMAIN)
