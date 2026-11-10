"""Stay Sharp CDK app (task T045, research R13, R14).

Stages ``dev`` and ``prod`` live in one AWS account dedicated to the project (constitution 1.0.1),
with ``staysharp-<stage>-*`` names. The account is never written here: it comes from the SSO
profile at deploy time (``CDK_DEFAULT_ACCOUNT``). Without credentials (pull-request CI, tests) a
placeholder account is used so the templates still synthesize; nothing can be deployed that way.

Stacks:
- ``staysharp-account`` (eu-central-2): GitHub OIDC roles, fingerprint bucket. Once.
- ``staysharp-mail`` (eu-central-2): SES domain identity for the sign-in codes. Once.
- ``staysharp-edge`` (us-east-1): certificate for the public name and the USD 20 budget. Once,
  deployed first, removed last.
- per stage, in eu-central-2: ``-ops``, ``-data``, ``-auth``, ``-api``, ``-web``. Only prod uses
  the public name and certificate (cross-region reference); dev uses its CloudFront domain.
- per stage, in us-east-1: ``-cdn-alarms`` (CloudFront metrics exist only there).

Context ``devSiteHost``: the dev CloudFront host, for dev passkeys (set after the first web
deploy; without it dev signs in with e-mail codes only).

Context ``devPublicName``: while prod is not live, dev answers on the public name too (so SES and
players can see a real address), with the edge certificate; passkeys and the inactivity link then
use the public name. A name can be on one distribution only: set it to ``false`` and redeploy
``staysharp-dev-web`` before the first prod deploy (docs/runbooks/account-setup.md).

Context for drills in dev only: ``devDeploymentConfig`` (for example
``LambdaCanary10Percent5Minutes``) and ``drill`` (``selfcheck-fail`` or ``fail-traffic``).
"""

from __future__ import annotations

import os
from typing import Any

import aws_cdk as cdk

from stacks.account_stack import AccountStack
from stacks.api_stack import ApiStack
from stacks.auth_stack import AuthStack
from stacks.cdn_alarms_stack import CdnAlarmsStack
from stacks.data_stack import DataStack
from stacks.edge_stack import SITE_DOMAIN, EdgeStack
from stacks.mail_stack import MailStack
from stacks.ops_stack import OpsStack
from stacks.web_stack import WebStack

REGION = "eu-central-2"
EDGE_REGION = "us-east-1"
STAGES = ("dev", "prod")
PLACEHOLDER_ACCOUNT = "000000000000"


def _context(app: cdk.App, name: str) -> Any:
    return app.node.try_get_context(name)


def build_app(context: dict[str, Any] | None = None) -> cdk.App:
    app = cdk.App(context=context)
    cdk.Tags.of(app).add("project", "stay-sharp")
    account = os.environ.get("CDK_DEFAULT_ACCOUNT") or PLACEHOLDER_ACCOUNT
    main_env = cdk.Environment(account=account, region=REGION)
    edge_env = cdk.Environment(account=account, region=EDGE_REGION)

    AccountStack(
        app,
        "staysharp-account",
        env=main_env,
        github_owner=_context(app, "githubOwner"),
        description="Stay Sharp: GitHub OIDC roles, leak-guard bucket (once per account)",
    )
    mail = MailStack(
        app,
        "staysharp-mail",
        env=main_env,
        description="Stay Sharp: SES identity for sign-in e-mails (once per account)",
    )
    edge = EdgeStack(
        app,
        "staysharp-edge",
        env=edge_env,
        cross_region_references=True,
        description="Stay Sharp: us-east-1 resources (certificate, budget, WAF)",
    )

    launch_dates: dict[str, str | None] = _context(app, "launchDate") or {}
    site_commit = _context(app, "siteCommit") or "initial"
    # Path of the built front end (front/dist); only the deploy workflow sets it.
    site_dist = _context(app, "siteDist")
    # Sign-in and warning e-mails go out through this SMTP server (the sender's mailbox) when
    # set, through SES otherwise: the way out while the account is in the SES sandbox.
    smtp_host = _context(app, "smtpHost")
    for stage in STAGES:
        prefix = f"staysharp-{stage}"
        prod = stage == "prod"
        ops = OpsStack(app, f"{prefix}-ops", stage=stage, env=main_env)
        data = DataStack(app, f"{prefix}-data", stage=stage, env=main_env)
        # The players' address: the public domain in prod (and in dev while devPublicName is
        # set), the CloudFront host in dev otherwise.
        public = prod or bool(_context(app, "devPublicName"))
        dev_host = _context(app, "devSiteHost")
        site_host = SITE_DOMAIN if public or not dev_host else dev_host
        auth = AuthStack(
            app,
            f"{prefix}-auth",
            stage=stage,
            site_host=SITE_DOMAIN if public else dev_host,
            table=data.table,
            pepper=data.pepper,
            topic=ops.topic,
            smtp_host=smtp_host,
            env=main_env,
        )
        auth.add_dependency(mail)
        api = ApiStack(
            app,
            f"{prefix}-api",
            stage=stage,
            table=data.table,
            pepper=data.pepper,
            launch_date=launch_dates.get(stage),
            topic=ops.topic,
            user_pool=auth.user_pool,
            user_pool_client=auth.client,
            site_url=f"https://{site_host}",
            deployment_config=None if prod else _context(app, "devDeploymentConfig"),
            drill=None if prod else _context(app, "drill"),
            smtp_host=smtp_host,
            env=main_env,
        )
        web = WebStack(
            app,
            f"{prefix}-web",
            stage=stage,
            api_domain=api.api_domain,
            site_commit=site_commit,
            site_dist=site_dist,
            domain_name=SITE_DOMAIN if public else None,
            certificate=edge.certificate if public else None,
            web_acl_arn=edge.web_acl.attr_arn,
            auth_config={
                "endpoint": f"https://cognito-idp.{REGION}.amazonaws.com/",
                "clientId": auth.client.user_pool_client_id,
            },
            env=main_env,
            cross_region_references=True,
        )
        # The certificate (public name) and the web ACL (both stages) come from the edge stack.
        web.add_stack_dependency(edge)
        CdnAlarmsStack(
            app,
            f"{prefix}-cdn-alarms",
            stage=stage,
            distribution_id=web.distribution.distribution_id,
            topic=edge.alerts,
            env=edge_env,
            cross_region_references=True,
        )
    return app


if __name__ == "__main__":
    build_app().synth()
