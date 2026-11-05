"""Deployed once per AWS account, in eu-central-2 (task T018, research R13).

- The GitHub OIDC provider and four roles, each trusted by one exact ``sub``:
  read-only diff (pull requests of this repository), dev deploy (``main``), prod deploy (the
  ``production`` environment) and content publish (``main`` of the private content repository).
- The private bucket that holds the leak-guard fingerprint file (research R4).

The USD 20 budget lives in the edge stack: AWS::Budgets::Budget is not available in
eu-central-2. No role has any Bedrock permission (Principle III). Account ids never appear here:
CDK reads the account from the SSO profile at deploy time.
"""

from __future__ import annotations

from typing import Any

from aws_cdk import Aws, Duration, RemovalPolicy, Stack
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3 as s3
from constructs import Construct

GITHUB_OIDC = "token.actions.githubusercontent.com"
MAIN_REGION = "eu-central-2"
CDK_QUALIFIER = "hnb659fds"
FINGERPRINT_KEY = "leak-guard/fingerprints.json"
LEAK_GUARD_PARAMETER = "/staysharp/prod/leak-guard/last-pass"
CONTENT_KEY_PREFIXES = ("Q#*", "DAILY#*", "POOL#*", "STOCK#*")


class AccountStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        github_owner: str,
        repository: str = "stay-sharp",
        content_repository: str = "stay-sharp-content",
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # --- Fingerprint bucket (leak guard, R4) ------------------------------------------------
        self.fingerprints = s3.Bucket(
            self,
            "Fingerprints",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            versioned=True,
            object_ownership=s3.ObjectOwnership.BUCKET_OWNER_ENFORCED,
            removal_policy=RemovalPolicy.RETAIN,
        )
        fingerprint_object = self.fingerprints.arn_for_objects(FINGERPRINT_KEY)

        # --- GitHub OIDC and roles ------------------------------------------------------------
        provider = iam.OpenIdConnectProvider(
            self, "GitHub", url=f"https://{GITHUB_OIDC}", client_ids=["sts.amazonaws.com"]
        )

        def github_role(name: str, sub: str, description: str) -> iam.Role:
            principal = iam.WebIdentityPrincipal(
                provider.open_id_connect_provider_arn,
                conditions={
                    "StringEquals": {
                        f"{GITHUB_OIDC}:aud": "sts.amazonaws.com",
                        f"{GITHUB_OIDC}:sub": sub,
                    }
                },
            )
            return iam.Role(
                self,
                name,
                role_name=f"staysharp-github-{name.lower()}",
                assumed_by=principal,
                description=description,
                max_session_duration=Duration.hours(1),
            )

        repo = f"repo:{github_owner}/{repository}"

        def cdk_role(kind: str) -> str:
            return (
                f"arn:{Aws.PARTITION}:iam::{Aws.ACCOUNT_ID}:role/cdk-{CDK_QUALIFIER}-{kind}-role-*"
            )

        # Read-only diff for pull requests (constitution V): no write action at all.
        self.diff_role = github_role(
            "Diff", f"{repo}:pull_request", "cdk diff on pull requests, read only"
        )
        self.diff_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "cloudformation:DescribeStacks",
                    "cloudformation:DescribeStackResources",
                    "cloudformation:DescribeStackEvents",
                    "cloudformation:GetTemplate",
                    "cloudformation:GetTemplateSummary",
                ],
                resources=["*"],
            )
        )
        self.diff_role.add_to_policy(
            iam.PolicyStatement(actions=["sts:AssumeRole"], resources=[cdk_role("lookup")])
        )
        self.diff_role.add_to_policy(
            iam.PolicyStatement(
                actions=["ssm:GetParameter"],
                resources=[
                    f"arn:{Aws.PARTITION}:ssm:*:{Aws.ACCOUNT_ID}:parameter/cdk-bootstrap/{CDK_QUALIFIER}/version"
                ],
            )
        )

        # Deploy roles: they only assume the CDK bootstrap roles, whose execution policy is
        # narrowed at bootstrap (infra/bootstrap/execution-policy.json).
        deploy_targets = [cdk_role(kind) for kind in ("deploy", "file-publishing", "lookup")]
        self.dev_deploy_role = github_role(
            "DevDeploy", f"{repo}:ref:refs/heads/main", "deploy dev from main"
        )
        self.prod_deploy_role = github_role(
            "ProdDeploy", f"{repo}:environment:production", "deploy prod after approval"
        )
        for role in (self.dev_deploy_role, self.prod_deploy_role):
            role.add_to_policy(
                iam.PolicyStatement(actions=["sts:AssumeRole"], resources=deploy_targets)
            )

        # The public leak scan reads the fingerprint file (pull requests and main).
        for role in (self.diff_role, self.dev_deploy_role):
            role.add_to_policy(
                iam.PolicyStatement(actions=["s3:GetObject"], resources=[fingerprint_object])
            )

        # Dev only: the deploy workflow seeds the sample questions into the dev table so the
        # end-to-end tests always have a set for today. Content keys only, never player data.
        dev_table = (
            f"arn:{Aws.PARTITION}:dynamodb:{MAIN_REGION}:{Aws.ACCOUNT_ID}:table/staysharp-dev"
        )
        self.dev_deploy_role.add_to_policy(
            iam.PolicyStatement(
                actions=["dynamodb:BatchWriteItem", "dynamodb:PutItem"],
                resources=[dev_table],
                conditions={
                    "ForAllValues:StringLike": {"dynamodb:LeadingKeys": list(CONTENT_KEY_PREFIXES)}
                },
            )
        )

        # The prod release gate reads the leak-guard timestamp (R4, SC-002a).
        leak_guard = (
            f"arn:{Aws.PARTITION}:ssm:{MAIN_REGION}:{Aws.ACCOUNT_ID}"
            f":parameter{LEAK_GUARD_PARAMETER}"
        )
        self.prod_deploy_role.add_to_policy(
            iam.PolicyStatement(actions=["ssm:GetParameter"], resources=[leak_guard])
        )

        # Content publish: prod table, content keys only.
        self.content_role = github_role(
            "ContentPublish",
            f"repo:{github_owner}/{content_repository}:ref:refs/heads/main",
            "publish questions and daily sets to prod",
        )
        prod_table = (
            f"arn:{Aws.PARTITION}:dynamodb:{MAIN_REGION}:{Aws.ACCOUNT_ID}:table/staysharp-prod"
        )
        self.content_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:Query",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:ConditionCheckItem",
                    "dynamodb:BatchWriteItem",
                ],
                resources=[prod_table],
                conditions={
                    "ForAllValues:StringLike": {"dynamodb:LeadingKeys": list(CONTENT_KEY_PREFIXES)}
                },
            )
        )
        self.content_role.add_to_policy(
            iam.PolicyStatement(actions=["ssm:PutParameter"], resources=[leak_guard])
        )
        self.content_role.add_to_policy(
            iam.PolicyStatement(actions=["s3:PutObject"], resources=[fingerprint_object])
        )
