"""Per-stage operations: the alarm topic and one way to make alarms (task T019, research R11).

The maintainer's e-mail is read at deploy time from the SSM parameter
``/staysharp/<stage>/alarm-email`` (created by hand, see docs/runbooks/account-setup.md), so it
never appears in this repository or in a synthesized template.
"""

from __future__ import annotations

from typing import Any

from aws_cdk import Duration, Stack
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_cloudwatch_actions as actions
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sns_subscriptions as subscriptions
from aws_cdk import aws_ssm as ssm
from constructs import Construct


def alarm_email(scope: Construct, path: str) -> str:
    """Deploy-time value of an SSM parameter: a CloudFormation parameter, not a lookup."""
    return ssm.StringParameter.value_for_string_parameter(scope, path)


def make_alarm(
    scope: Construct,
    construct_id: str,
    *,
    topic: sns.ITopic,
    metric: cloudwatch.IMetric,
    threshold: float,
    treat_missing_data: cloudwatch.TreatMissingData,
    comparison: cloudwatch.ComparisonOperator = (
        cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD
    ),
    evaluation_periods: int = 1,
    datapoints_to_alarm: int = 1,
    description: str,
) -> cloudwatch.Alarm:
    """Every alarm in this project goes through here: missing data is always a decision."""
    alarm = cloudwatch.Alarm(
        scope,
        construct_id,
        metric=metric,
        threshold=threshold,
        comparison_operator=comparison,
        evaluation_periods=evaluation_periods,
        datapoints_to_alarm=datapoints_to_alarm,
        treat_missing_data=treat_missing_data,
        alarm_description=description,
    )
    alarm.add_alarm_action(actions.SnsAction(topic))
    alarm.add_ok_action(actions.SnsAction(topic))
    return alarm


class OpsStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, *, stage: str, **kwargs: Any) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.stage = stage
        self.topic = sns.Topic(
            self,
            "Alarms",
            topic_name=f"staysharp-{stage}-alarms",
            display_name=f"Stay Sharp {stage} alarms",
            enforce_ssl=True,
        )
        self.topic.add_subscription(
            subscriptions.EmailSubscription(alarm_email(self, f"/staysharp/{stage}/alarm-email"))
        )

    def alarm(
        self,
        construct_id: str,
        *,
        metric: cloudwatch.IMetric,
        threshold: float,
        treat_missing_data: cloudwatch.TreatMissingData,
        description: str,
        comparison: cloudwatch.ComparisonOperator = (
            cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD
        ),
        period: Duration | None = None,
    ) -> cloudwatch.Alarm:
        del period  # the metric carries its own period
        return make_alarm(
            self,
            construct_id,
            topic=self.topic,
            metric=metric,
            threshold=threshold,
            treat_missing_data=treat_missing_data,
            comparison=comparison,
            description=description,
        )
