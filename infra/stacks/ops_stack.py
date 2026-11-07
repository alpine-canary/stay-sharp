"""Per-stage operations: the alarm topic, one way to make alarms, and the stage alarms
(tasks T019, T079, research R11).

Alarms here use metrics found by name (Stage, function name), so this stack needs nothing from
the API stack: paging ``ScoringFailures`` summed over versions, ``SelfCheckFailures``, Lambda
errors and throttles, and in dev the fault injection left on. It also runs the daily stock check
(T092, FR-026, W8) with its own role and alarms. The rollback alarms and the API
5xx alarm live in the API stack (they need the version and the API id); the CloudFront 5xx alarm
lives in us-east-1, where CloudFront metrics are (``CdnAlarmsStack``).

The maintainer's e-mail is read at deploy time from the SSM parameter
``/staysharp/<stage>/alarm-email`` (created by hand, see docs/runbooks/account-setup.md), so it
never appears in this repository or in a synthesized template.
"""

from __future__ import annotations

from typing import Any

from aws_cdk import Aws, Duration, RemovalPolicy, Stack
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_cloudwatch_actions as actions
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_destinations as destinations
from aws_cdk import aws_logs as logs
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sns_subscriptions as subscriptions
from aws_cdk import aws_ssm as ssm
from constructs import Construct

from stacks.bundling import api_code

MAIN_REGION = "eu-central-2"
# FR-026: warn below 7 days in prod. Dev only holds a few fixture days, so it checks the
# mechanism with a threshold of 1 instead of being in alarm all the time.
STOCK_THRESHOLD = {"prod": 7, "dev": 1}


def alarm_email(scope: Construct, path: str) -> str:
    """Deploy-time value of an SSM parameter: a CloudFormation parameter, not a lookup."""
    return ssm.StringParameter.value_for_string_parameter(scope, path)


def allow_cloudwatch(topic: sns.Topic) -> None:
    """A topic with its own policy (enforce_ssl) loses the default one: let alarms publish."""
    topic.add_to_resource_policy(
        iam.PolicyStatement(
            principals=[iam.ServicePrincipal("cloudwatch.amazonaws.com")],
            actions=["sns:Publish"],
            resources=[topic.topic_arn],
            conditions={"StringEquals": {"aws:SourceAccount": Aws.ACCOUNT_ID}},
        )
    )


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
        allow_cloudwatch(self.topic)
        self._alarms(stage)
        self._stock_check(stage)

    def _alarms(self, stage: str) -> None:
        minute = Duration.minutes(1)
        five = Duration.minutes(5)
        quiet = cloudwatch.TreatMissingData.NOT_BREACHING

        def ours(name: str, period: Duration) -> cloudwatch.Metric:
            return cloudwatch.Metric(
                namespace="StaySharp",
                metric_name=name,
                dimensions_map={"Stage": stage},
                statistic="Sum",
                period=period,
            )

        def lambda_metric(name: str) -> cloudwatch.Metric:
            return cloudwatch.Metric(
                namespace="AWS/Lambda",
                metric_name=name,
                dimensions_map={"FunctionName": f"staysharp-{stage}-api"},
                statistic="Sum",
                period=five,
            )

        # FR-028, SC-004: one failure in any of the last 5 minutes pages the maintainer. Never
        # attached to CodeDeploy (that is the version-scoped alarm in the API stack).
        make_alarm(
            self,
            "PagingScoringFailures",
            topic=self.topic,
            metric=ours("ScoringFailures", minute),
            threshold=1,
            evaluation_periods=5,
            datapoints_to_alarm=1,
            treat_missing_data=quiet,
            description="PAGE: answers could not be scored (all versions). See rollback.md.",
        )
        make_alarm(
            self,
            "SelfCheckFailures",
            topic=self.topic,
            metric=ours("SelfCheckFailures", five),
            threshold=1,
            treat_missing_data=quiet,
            description="A new version failed its self-check and was stopped before traffic.",
        )
        make_alarm(
            self,
            "LambdaErrors",
            topic=self.topic,
            metric=lambda_metric("Errors"),
            threshold=1,
            treat_missing_data=quiet,
            description="The API function raised errors (all versions).",
        )
        make_alarm(
            self,
            "LambdaThrottles",
            topic=self.topic,
            metric=lambda_metric("Throttles"),
            threshold=1,
            treat_missing_data=quiet,
            description="The API function hit its reserved concurrency (players got 5xx).",
        )
        if stage == "prod":
            # SES watches the account's reputation in eu-central-2 (the code e-mails and the
            # inactivity warning) and pauses sending past 10 % bounces or 0.5 % complaints.
            # Warn well before: at 4 % and 0.08 %. One account, so prod watches it.
            for name, threshold, what in (
                ("BounceRate", 0.04, "bounces"),
                ("ComplaintRate", 0.0008, "complaints"),
            ):
                make_alarm(
                    self,
                    f"Ses{name}",
                    topic=self.topic,
                    metric=cloudwatch.Metric(
                        namespace="AWS/SES",
                        metric_name=f"Reputation.{name}",
                        statistic="Maximum",
                        period=Duration.hours(1),
                    ),
                    threshold=threshold,
                    treat_missing_data=quiet,
                    description=(
                        f"Sign-in e-mails: too many {what}. SES pauses sending past its limit "
                        "(docs/runbooks/accounts.md)."
                    ),
                )
        if stage == "dev":
            make_alarm(
                self,
                "FaultInjectionLeftOn",
                topic=self.topic,
                metric=ours("FaultInjectionActive", five),
                threshold=1,
                evaluation_periods=6,
                datapoints_to_alarm=6,
                treat_missing_data=quiet,
                description="Dev fault injection has been on for 30 minutes: switch it off.",
            )

    def _stock_check(self, stage: str) -> None:
        name = f"staysharp-{stage}-stock-check"
        log_group = logs.LogGroup(
            self,
            "StockCheckLogs",
            log_group_name=f"/aws/lambda/{name}",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY,
        )
        function = lambda_.Function(
            self,
            "StockCheck",
            function_name=name,
            runtime=lambda_.Runtime.PYTHON_3_13,
            architecture=lambda_.Architecture.ARM_64,
            handler="staysharp.handlers.stock_check.handler",
            code=api_code(stage),
            memory_size=256,
            timeout=Duration.seconds(30),
            environment={"STAGE": stage, "TABLE_NAME": f"staysharp-{stage}"},
            log_group=log_group,
            logging_format=lambda_.LoggingFormat.JSON,
            retry_attempts=2,
            max_event_age=Duration.hours(2),
            on_failure=destinations.SnsDestination(self.topic),
        )
        # Its own role: future-day markers only, nothing else of the table (R8).
        table_arn = (
            f"arn:{Aws.PARTITION}:dynamodb:{MAIN_REGION}:{Aws.ACCOUNT_ID}:table/staysharp-{stage}"
        )
        function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:Query"],
                resources=[table_arn],
                conditions={"ForAllValues:StringLike": {"dynamodb:LeadingKeys": ["STOCK#*"]}},
            )
        )
        # Once a day, early morning in Zurich. An EventBridge rule invokes asynchronously, so
        # retries and the on-failure destination apply.
        events.Rule(
            self,
            "StockCheckDaily",
            schedule=events.Schedule.cron(minute="0", hour="5"),
            targets=[targets.LambdaFunction(function, retry_attempts=2)],
        )

        day = Duration.days(1)
        breaching = cloudwatch.TreatMissingData.BREACHING

        def lambda_named(metric: str, period: Duration) -> cloudwatch.Metric:
            return cloudwatch.Metric(
                namespace="AWS/Lambda",
                metric_name=metric,
                dimensions_map={"FunctionName": name},
                statistic="Sum",
                period=period,
            )

        for level in ("senior", "junior", "starter"):
            make_alarm(
                self,
                f"StockLow{level.capitalize()}",
                topic=self.topic,
                metric=cloudwatch.Metric(
                    namespace="StaySharp",
                    metric_name="StockDaysAhead",
                    dimensions_map={"Stage": stage, "Level": level},
                    statistic="Minimum",
                    period=day,
                ),
                threshold=STOCK_THRESHOLD[stage],
                comparison=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
                treat_missing_data=breaching,
                description=(
                    f"Fewer than {STOCK_THRESHOLD[stage]} days of {level} sets ahead, or no "
                    "stock value today. Publish more days (docs/runbooks/publish.md)."
                ),
            )
        make_alarm(
            self,
            "StockCheckErrors",
            topic=self.topic,
            metric=lambda_named("Errors", Duration.minutes(5)),
            threshold=1,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
            description="The stock check failed: the stock value may be missing or stale.",
        )
        make_alarm(
            self,
            "StockCheckMissed",
            topic=self.topic,
            metric=lambda_named("Invocations", day),
            threshold=1,
            comparison=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
            treat_missing_data=breaching,
            description="The stock check did not run in the last day (schedule broken?).",
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
