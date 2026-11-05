"""CloudFront 5xx alarm per stage, in us-east-1 where CloudFront metrics live (task T079, R11, W6).

CloudWatch alarms can only watch metrics of their own region and notify a topic of their own
region, so this alarm notifies the account alert topic of the edge stack.
"""

from __future__ import annotations

from typing import Any

from aws_cdk import Duration, Stack
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_sns as sns
from constructs import Construct

from stacks.ops_stack import make_alarm

ERROR_RATE_PERCENT = 5


class CdnAlarmsStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        stage: str,
        distribution_id: str,
        topic: sns.ITopic,
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        make_alarm(
            self,
            "CloudFront5xxRate",
            topic=topic,
            metric=cloudwatch.Metric(
                namespace="AWS/CloudFront",
                metric_name="5xxErrorRate",
                dimensions_map={"DistributionId": distribution_id, "Region": "Global"},
                statistic="Average",
                period=Duration.minutes(5),
            ),
            threshold=ERROR_RATE_PERCENT,
            evaluation_periods=3,
            datapoints_to_alarm=2,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
            description=f"{stage}: CloudFront answered 5xx to more than 5 % of requests.",
        )
