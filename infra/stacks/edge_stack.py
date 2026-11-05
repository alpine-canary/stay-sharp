"""Account-wide resources that must live in us-east-1 (tasks T017 and T018, R11, R14).

- The ACM certificate for the public site name, validated by DNS. The lumineth.com zone is
  outside this account: on the first deploy the stack waits until the maintainer adds the
  validation CNAME shown in the ACM console (docs/runbooks/account-setup.md, step 4).
- The AWS Budget of USD 20 a month, with an e-mail through SNS when actual cost passes USD 20 or
  the forecast passes USD 16 (FR-031). ``AWS::Budgets::Budget`` is not available in eu-central-2.
- The WAF web ACL (R9, T116), CloudFront scope, shared by the dev and prod distributions: a rate
  rule of 1,000 requests per 5 minutes per IP on ``/api/*`` with the JSON 429 body, a rule
  refusing ``/api/*`` bodies over 2 KB, and the AWS managed common rule set. No logging and no
  sampled requests: both would keep IP addresses.

No game data lives in this region.
"""

from __future__ import annotations

import json
from typing import Any

from aws_cdk import Aws, Stack
from aws_cdk import aws_budgets as budgets
from aws_cdk import aws_certificatemanager as acm
from aws_cdk import aws_iam as iam
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sns_subscriptions as subscriptions
from aws_cdk import aws_wafv2 as waf
from constructs import Construct

from stacks.ops_stack import alarm_email, allow_cloudwatch

SITE_DOMAIN = "stay-sharp.lumineth.com"
BUDGET_USD = 20
FORECAST_USD = 16
API_RATE_PER_5_MIN = 1_000
API_MAX_BODY_BYTES = 2_048
RATE_LIMITED = {"code": "rate_limited", "message": "Too many requests. Try again in a few minutes."}
TOO_LARGE = {"code": "invalid_request", "message": "Request too large."}


class EdgeStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs: Any) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.certificate = acm.Certificate(
            self,
            "SiteCertificate",
            domain_name=SITE_DOMAIN,
            validation=acm.CertificateValidation.from_dns(),
        )
        self._budget()
        self.web_acl = self._web_acl()

    def _web_acl(self) -> waf.CfnWebACL:
        def visibility(name: str) -> waf.CfnWebACL.VisibilityConfigProperty:
            return waf.CfnWebACL.VisibilityConfigProperty(
                cloud_watch_metrics_enabled=True,
                metric_name=name,
                sampled_requests_enabled=False,
            )

        api_path = waf.CfnWebACL.StatementProperty(
            byte_match_statement=waf.CfnWebACL.ByteMatchStatementProperty(
                field_to_match=waf.CfnWebACL.FieldToMatchProperty(uri_path={}),
                positional_constraint="STARTS_WITH",
                search_string="/api/",
                text_transformations=[
                    waf.CfnWebACL.TextTransformationProperty(priority=0, type="NONE")
                ],
            )
        )

        def block(status: int, body_key: str) -> waf.CfnWebACL.RuleActionProperty:
            return waf.CfnWebACL.RuleActionProperty(
                block=waf.CfnWebACL.BlockActionProperty(
                    custom_response=waf.CfnWebACL.CustomResponseProperty(
                        response_code=status, custom_response_body_key=body_key
                    )
                )
            )

        def json_body(content: dict[str, str]) -> waf.CfnWebACL.CustomResponseBodyProperty:
            return waf.CfnWebACL.CustomResponseBodyProperty(
                content_type="APPLICATION_JSON",
                content=json.dumps(content, separators=(",", ":")),
            )

        return waf.CfnWebACL(
            self,
            "WebAcl",
            name="staysharp-web",
            scope="CLOUDFRONT",
            default_action=waf.CfnWebACL.DefaultActionProperty(allow={}),
            visibility_config=visibility("staysharp-web"),
            custom_response_bodies={
                "rate_limited": json_body(RATE_LIMITED),
                "too_large": json_body(TOO_LARGE),
            },
            rules=[
                waf.CfnWebACL.RuleProperty(
                    name="ApiRatePerIp",
                    priority=0,
                    action=block(429, "rate_limited"),
                    statement=waf.CfnWebACL.StatementProperty(
                        rate_based_statement=waf.CfnWebACL.RateBasedStatementProperty(
                            limit=API_RATE_PER_5_MIN,
                            evaluation_window_sec=300,
                            aggregate_key_type="IP",
                            scope_down_statement=api_path,
                        )
                    ),
                    visibility_config=visibility("ApiRatePerIp"),
                ),
                waf.CfnWebACL.RuleProperty(
                    name="ApiBodyOver2KB",
                    priority=1,
                    action=block(413, "too_large"),
                    statement=waf.CfnWebACL.StatementProperty(
                        and_statement=waf.CfnWebACL.AndStatementProperty(
                            statements=[
                                api_path,
                                waf.CfnWebACL.StatementProperty(
                                    size_constraint_statement=waf.CfnWebACL.SizeConstraintStatementProperty(
                                        field_to_match=waf.CfnWebACL.FieldToMatchProperty(
                                            body=waf.CfnWebACL.BodyProperty(
                                                oversize_handling="MATCH"
                                            )
                                        ),
                                        comparison_operator="GT",
                                        size=API_MAX_BODY_BYTES,
                                        text_transformations=[
                                            waf.CfnWebACL.TextTransformationProperty(
                                                priority=0, type="NONE"
                                            )
                                        ],
                                    )
                                ),
                            ]
                        )
                    ),
                    visibility_config=visibility("ApiBodyOver2KB"),
                ),
                waf.CfnWebACL.RuleProperty(
                    name="AwsCommonRuleSet",
                    priority=2,
                    override_action=waf.CfnWebACL.OverrideActionProperty(none={}),
                    statement=waf.CfnWebACL.StatementProperty(
                        managed_rule_group_statement=waf.CfnWebACL.ManagedRuleGroupStatementProperty(
                            vendor_name="AWS", name="AWSManagedRulesCommonRuleSet"
                        )
                    ),
                    visibility_config=visibility("AwsCommonRuleSet"),
                ),
            ],
        )

    def _budget(self) -> None:
        topic = sns.Topic(
            self,
            "AccountAlerts",
            topic_name="staysharp-account-alerts",
            display_name="Stay Sharp account alerts",
            enforce_ssl=True,
        )
        topic.add_subscription(
            subscriptions.EmailSubscription(alarm_email(self, "/staysharp/account/alarm-email"))
        )
        allow_cloudwatch(topic)
        self.alerts = topic
        topic.add_to_resource_policy(
            iam.PolicyStatement(
                principals=[iam.ServicePrincipal("budgets.amazonaws.com")],
                actions=["sns:Publish"],
                resources=[topic.topic_arn],
                conditions={"StringEquals": {"aws:SourceAccount": Aws.ACCOUNT_ID}},
            )
        )

        def notification(
            kind: str, amount: int
        ) -> budgets.CfnBudget.NotificationWithSubscribersProperty:
            return budgets.CfnBudget.NotificationWithSubscribersProperty(
                notification=budgets.CfnBudget.NotificationProperty(
                    notification_type=kind,
                    comparison_operator="GREATER_THAN",
                    threshold=amount,
                    threshold_type="ABSOLUTE_VALUE",
                ),
                subscribers=[
                    budgets.CfnBudget.SubscriberProperty(
                        subscription_type="SNS", address=topic.topic_arn
                    )
                ],
            )

        budgets.CfnBudget(
            self,
            "MonthlyBudget",
            budget=budgets.CfnBudget.BudgetDataProperty(
                budget_name="staysharp-monthly",
                budget_type="COST",
                time_unit="MONTHLY",
                budget_limit=budgets.CfnBudget.SpendProperty(amount=BUDGET_USD, unit="USD"),
            ),
            notifications_with_subscribers=[
                notification("ACTUAL", BUDGET_USD),
                notification("FORECASTED", FORECAST_USD),
            ],
        )
