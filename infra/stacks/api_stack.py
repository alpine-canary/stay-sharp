"""Per-stage API: one Lambda behind an HTTP API, deployed by CodeDeploy (tasks T043, T078).

- Function, version and alias ``live``; the HTTP API calls the alias.
- CodeDeploy: ``LambdaCanary10Percent5Minutes`` in prod, ``AllAtOnce`` in dev (the canary drill
  can ask for the canary in dev), automatic rollback on the three alarms of research R10.
- Pre-traffic hook: a small function that invokes the new version's self-check. It may invoke
  that version's ARN and nothing else; failures go to SNS and to an error alarm.
- CodeDeploy tells the maintainer about failed and rolled-back deployments (Story 6 scenario 2).
- Dev only: the handler is the fault-injection wrapper (``testing``), which reads one SSM
  parameter; prod has neither the code nor the permission (W11).
"""

from __future__ import annotations

from typing import Any

import jsii
from aws_cdk import Annotations, Duration, Stack
from aws_cdk import aws_apigateway as apigw_v1
from aws_cdk import aws_apigatewayv2 as apigw
from aws_cdk import aws_apigatewayv2_integrations as integrations
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_codedeploy as codedeploy
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_destinations as destinations
from aws_cdk import aws_logs as logs
from aws_cdk import aws_secretsmanager as secretsmanager
from aws_cdk import aws_sns as sns
from constructs import Construct

from stacks.bundling import api_code
from stacks.ops_stack import make_alarm

LOG_RETENTION = logs.RetentionDays.ONE_MONTH
RESERVED_CONCURRENCY = 20
THROTTLE_BURST = 50
THROTTLE_RATE = 20
API_HANDLER = "staysharp.handlers.api.handler"
DEV_HANDLER = "testing.fault_injection.handler"
DRILLS = ("selfcheck-fail", "fail-traffic")
DEPLOYMENT_CONFIGS = {
    "AllAtOnce": codedeploy.LambdaDeploymentConfig.ALL_AT_ONCE,
    "LambdaCanary10Percent5Minutes": codedeploy.LambdaDeploymentConfig.CANARY_10_PERCENT_5_MINUTES,
}

# Access log fields: ids, route, status and timings. Never sourceIp, user agent or headers.
ACCESS_LOG_FORMAT = {
    "requestId": "$context.requestId",
    "requestTime": "$context.requestTime",
    "routeKey": "$context.routeKey",
    "path": "$context.path",
    "status": "$context.status",
    "responseLength": "$context.responseLength",
    "responseLatency": "$context.responseLatency",
    "integrationLatency": "$context.integrationLatency",
    "integrationStatus": "$context.integrationStatus",
    "integrationError": "$context.integrationErrorMessage",
}


@jsii.implements(apigw.IAccessLogSettings)
class AccessLogs:
    def __init__(self, log_group: logs.ILogGroup) -> None:
        self._destination = apigw.LogGroupLogDestination(log_group)
        self._format = apigw_v1.AccessLogFormat.custom(_to_json(ACCESS_LOG_FORMAT))

    @property
    def destination(self) -> apigw.IAccessLogDestination:
        return self._destination

    @property
    def format(self) -> apigw_v1.AccessLogFormat:
        return self._format


def _to_json(fields: dict[str, str]) -> str:
    import json

    return json.dumps(fields, separators=(",", ":"))


class ApiStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        stage: str,
        table: dynamodb.ITableV2,
        pepper: secretsmanager.ISecret,
        launch_date: str | None,
        topic: sns.ITopic,
        deployment_config: str | None = None,
        drill: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        prod = stage == "prod"
        if prod and (drill or deployment_config not in (None, "LambdaCanary10Percent5Minutes")):
            raise ValueError("prod always deploys with the canary and never runs a drill")
        if drill is not None and drill not in DRILLS:
            raise ValueError(f"unknown drill {drill!r}")
        config_name = deployment_config or (
            "LambdaCanary10Percent5Minutes" if prod else "AllAtOnce"
        )
        environment = {
            "STAGE": stage,
            "TABLE_NAME": table.table_name,
            "PEPPER_SECRET_ARN": pepper.secret_arn,
            "POWERTOOLS_SERVICE_NAME": "staysharp",
            "POWERTOOLS_METRICS_NAMESPACE": "StaySharp",
            "POWERTOOLS_LOGGER_LOG_EVENT": "false",
        }
        if drill:
            environment["STAYSHARP_DRILL"] = drill
        if launch_date:
            environment["LAUNCH_DATE"] = launch_date
        else:
            Annotations.of(self).add_warning_v2(
                "staysharp:launch-date",
                f"No launch date for {stage}: GET /today fails until cdk.json sets launchDate.",
            )

        log_group = logs.LogGroup(
            self,
            "ApiLogs",
            log_group_name=f"/aws/lambda/staysharp-{stage}-api",
            retention=LOG_RETENTION,
        )
        self.function = lambda_.Function(
            self,
            "Api",
            function_name=f"staysharp-{stage}-api",
            runtime=lambda_.Runtime.PYTHON_3_13,
            architecture=lambda_.Architecture.ARM_64,
            handler=API_HANDLER if prod else DEV_HANDLER,
            code=api_code(stage),
            memory_size=512,
            timeout=Duration.seconds(10),
            # A flood gives 5xx to players instead of a bill: a deliberate trade-off (R9).
            reserved_concurrent_executions=RESERVED_CONCURRENCY,
            environment=environment,
            log_group=log_group,
            logging_format=lambda_.LoggingFormat.JSON,
        )
        table.grant_read_write_data(self.function)
        pepper.grant_read(self.function)
        if not prod:
            self.function.add_to_role_policy(
                iam.PolicyStatement(
                    actions=["ssm:GetParameter"],
                    resources=[
                        self.format_arn(
                            service="ssm",
                            resource="parameter",
                            resource_name=f"staysharp/{stage}/fault-injection",
                        )
                    ],
                )
            )

        self.version = self.function.current_version
        self.alias = lambda_.Alias(self, "Live", alias_name="live", version=self.version)

        access_logs = logs.LogGroup(
            self,
            "AccessLogs",
            log_group_name=f"/staysharp/{stage}/api-access",
            retention=LOG_RETENTION,
        )
        self.http_api = apigw.HttpApi(
            self,
            "HttpApi",
            api_name=f"staysharp-{stage}-api",
            default_integration=integrations.HttpLambdaIntegration("Live", self.alias),
            create_default_stage=False,
        )
        self.stage = apigw.HttpStage(
            self,
            "DefaultStage",
            http_api=self.http_api,
            stage_name="$default",
            auto_deploy=True,
            throttle=apigw.ThrottleSettings(burst_limit=THROTTLE_BURST, rate_limit=THROTTLE_RATE),
            access_log_settings=AccessLogs(access_logs),
        )

        self._delivery(stage, topic, config_name)

    def _delivery(self, stage: str, topic: sns.ITopic, config_name: str) -> None:
        name = self.function.function_name
        minute = Duration.minutes(1)
        rollback = [
            make_alarm(
                self,
                "CanaryErrors",
                topic=topic,
                metric=cloudwatch.Metric(
                    namespace="AWS/Lambda",
                    metric_name="Errors",
                    dimensions_map={
                        "FunctionName": name,
                        "Resource": f"{name}:live",
                        "ExecutedVersion": self.version.version,
                    },
                    statistic="Sum",
                    period=minute,
                ),
                threshold=1,
                treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
                description="Rollback: the new version raised errors through the live alias.",
            ),
            make_alarm(
                self,
                "CanaryScoringFailures",
                topic=topic,
                metric=cloudwatch.Metric(
                    namespace="StaySharp",
                    metric_name="ScoringFailures",
                    dimensions_map={"Stage": stage, "FunctionVersion": self.version.version},
                    statistic="Sum",
                    period=minute,
                ),
                threshold=1,
                treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
                description="Rollback: the new version failed to store an answer.",
            ),
            make_alarm(
                self,
                "Api5xx",
                topic=topic,
                metric=cloudwatch.Metric(
                    namespace="AWS/ApiGateway",
                    metric_name="5xx",
                    dimensions_map={"ApiId": self.http_api.api_id, "Stage": "$default"},
                    statistic="Sum",
                    period=minute,
                ),
                threshold=1,
                treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
                description="Rollback and health: the API answered 5xx.",
            ),
        ]

        hook_logs = logs.LogGroup(
            self,
            "PreTrafficLogs",
            log_group_name=f"/aws/lambda/staysharp-{stage}-pre-traffic",
            retention=LOG_RETENTION,
        )
        hook = lambda_.Function(
            self,
            "PreTraffic",
            function_name=f"staysharp-{stage}-pre-traffic",
            runtime=lambda_.Runtime.PYTHON_3_13,
            architecture=lambda_.Architecture.ARM_64,
            handler="staysharp.handlers.pre_traffic_check.handler",
            code=api_code(stage),
            memory_size=256,
            timeout=Duration.seconds(60),
            environment={
                "TARGET_FUNCTION_ARN": self.version.function_arn,
                "STAGE": stage,
                "POWERTOOLS_SERVICE_NAME": "staysharp-pre-traffic",
            },
            log_group=hook_logs,
            logging_format=lambda_.LoggingFormat.JSON,
            retry_attempts=0,
            on_failure=destinations.SnsDestination(topic),
        )
        # The new version's ARN and nothing else (R10, V11).
        hook.add_to_role_policy(
            iam.PolicyStatement(
                actions=["lambda:InvokeFunction"], resources=[self.version.function_arn]
            )
        )
        make_alarm(
            self,
            "PreTrafficErrors",
            topic=topic,
            metric=hook.metric_errors(period=Duration.minutes(5), statistic="Sum"),
            threshold=1,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
            description="The pre-traffic check failed or could not report to CodeDeploy.",
        )

        group = codedeploy.LambdaDeploymentGroup(
            self,
            "Deployment",
            application=codedeploy.LambdaApplication(
                self, "Application", application_name=f"staysharp-{stage}-api"
            ),
            deployment_group_name=f"staysharp-{stage}-api",
            alias=self.alias,
            deployment_config=DEPLOYMENT_CONFIGS[config_name],
            alarms=rollback,
            pre_hook=hook,
            auto_rollback=codedeploy.AutoRollbackConfig(
                failed_deployment=True, stopped_deployment=True, deployment_in_alarm=True
            ),
        )
        topic.grant_publish(group.role)
        cfn_group = group.node.default_child
        if not isinstance(cfn_group, codedeploy.CfnDeploymentGroup):
            raise TypeError("expected the CloudFormation deployment group")
        cfn_group.trigger_configurations = [
            codedeploy.CfnDeploymentGroup.TriggerConfigProperty(
                trigger_name="maintainer",
                trigger_target_arn=topic.topic_arn,
                trigger_events=["DeploymentFailure", "DeploymentRollback"],
            )
        ]
        self.deployment_group = group
        self.rollback_alarms = rollback

    @property
    def api_domain(self) -> str:
        return f"{self.http_api.api_id}.execute-api.{self.region}.{self.url_suffix}"
