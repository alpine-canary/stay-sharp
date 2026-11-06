"""Per-stage data: the game table and the pepper secret (task T032, research R16, R17)."""

from __future__ import annotations

from typing import Any

from aws_cdk import RemovalPolicy, Stack
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct


class DataStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, *, stage: str, **kwargs: Any) -> None:
        super().__init__(scope, construct_id, **kwargs)
        prod = stage == "prod"

        self.table = dynamodb.TableV2(
            self,
            "Table",
            table_name=f"staysharp-{stage}",
            partition_key=dynamodb.Attribute(name="PK", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="SK", type=dynamodb.AttributeType.STRING),
            billing=dynamodb.Billing.on_demand(),
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True
            ),
            deletion_protection=prod,
            time_to_live_attribute="expiresAt",
            # Sparse: only account items carry lastActiveMonth (M2, inactive accounts, A8).
            global_secondary_indexes=[
                dynamodb.GlobalSecondaryIndexPropsV2(
                    index_name="GSI_INACTIVE",
                    partition_key=dynamodb.Attribute(
                        name="lastActiveMonth", type=dynamodb.AttributeType.STRING
                    ),
                    projection_type=dynamodb.ProjectionType.KEYS_ONLY,
                )
            ],
            removal_policy=RemovalPolicy.RETAIN if prod else RemovalPolicy.DESTROY,
        )

        # Rotating it breaks live challenges (owner and colleague hashes stop matching), so it is
        # retained and rotated only after a 30-day notice (R16).
        self.pepper = secretsmanager.Secret(
            self,
            "Pepper",
            secret_name=f"staysharp/{stage}/pepper",
            description="HMAC pepper for player hashes in logs and challenges",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                password_length=64, exclude_punctuation=True
            ),
            removal_policy=RemovalPolicy.RETAIN,
        )
