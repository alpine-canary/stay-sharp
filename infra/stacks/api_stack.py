"""Per-stage API: one Lambda behind an HTTP API (task T043, research R8, R9).

First version: function, alias ``live``, HTTP API with throttling and access logs. The CodeDeploy
group, the pre-traffic check and the rollback alarms come with Story 6 (tasks T075 to T079).
"""

from __future__ import annotations

from typing import Any

import jsii
from aws_cdk import Annotations, Duration, Stack
from aws_cdk import aws_apigateway as apigw_v1
from aws_cdk import aws_apigatewayv2 as apigw
from aws_cdk import aws_apigatewayv2_integrations as integrations
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

from stacks.bundling import api_code

LOG_RETENTION = logs.RetentionDays.ONE_MONTH
RESERVED_CONCURRENCY = 20
THROTTLE_BURST = 50
THROTTLE_RATE = 20

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
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        environment = {
            "STAGE": stage,
            "TABLE_NAME": table.table_name,
            "PEPPER_SECRET_ARN": pepper.secret_arn,
            "POWERTOOLS_SERVICE_NAME": "staysharp",
            "POWERTOOLS_METRICS_NAMESPACE": "StaySharp",
            "POWERTOOLS_LOGGER_LOG_EVENT": "false",
        }
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
            handler="staysharp.handlers.api.handler",
            code=api_code(),
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

        self.alias = lambda_.Alias(
            self, "Live", alias_name="live", version=self.function.current_version
        )

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

    @property
    def api_domain(self) -> str:
        return f"{self.http_api.api_id}.execute-api.{self.region}.{self.url_suffix}"
