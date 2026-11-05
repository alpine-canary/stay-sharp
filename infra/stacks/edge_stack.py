"""Account-wide resources that must live in us-east-1 (tasks T017 and T018, R11, R14).

- The ACM certificate for the public site name, validated by DNS. The lumineth.com zone is
  outside this account: on the first deploy the stack waits until the maintainer adds the
  validation CNAME shown in the ACM console (docs/runbooks/account-setup.md, step 4).
- The AWS Budget of USD 20 a month, with an e-mail through SNS when actual cost passes USD 20 or
  the forecast passes USD 16 (FR-031). ``AWS::Budgets::Budget`` is not available in eu-central-2.
- The WAF web ACL (R9) joins this stack later.

No game data lives in this region.
"""

from __future__ import annotations

from typing import Any

from aws_cdk import Aws, Stack
from aws_cdk import aws_budgets as budgets
from aws_cdk import aws_certificatemanager as acm
from aws_cdk import aws_iam as iam
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sns_subscriptions as subscriptions
from constructs import Construct

from stacks.ops_stack import alarm_email, allow_cloudwatch

SITE_DOMAIN = "stay-sharp.lumineth.com"
BUDGET_USD = 20
FORECAST_USD = 16


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
