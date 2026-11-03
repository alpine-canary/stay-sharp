"""Table and secret settings (task T033, scenario V11, research R16, R17)."""

from __future__ import annotations

import pytest

from tests.conftest import TemplateOf, resources


@pytest.mark.parametrize("stage", ["dev", "prod"])
def test_table_keys_billing_pitr_ttl(template: TemplateOf, stage: str) -> None:
    (table,) = resources(template(f"staysharp-{stage}-data"), "AWS::DynamoDB::GlobalTable").values()
    props = table["Properties"]
    assert props["TableName"] == f"staysharp-{stage}"
    assert props["KeySchema"] == [
        {"AttributeName": "PK", "KeyType": "HASH"},
        {"AttributeName": "SK", "KeyType": "RANGE"},
    ]
    assert props["BillingMode"] == "PAY_PER_REQUEST"
    assert props["TimeToLiveSpecification"] == {"AttributeName": "expiresAt", "Enabled": True}
    (replica,) = props["Replicas"]
    assert replica["PointInTimeRecoverySpecification"]["PointInTimeRecoveryEnabled"] is True


def test_deletion_protection_and_retention_in_prod_only(template: TemplateOf) -> None:
    (prod,) = resources(template("staysharp-prod-data"), "AWS::DynamoDB::GlobalTable").values()
    (dev,) = resources(template("staysharp-dev-data"), "AWS::DynamoDB::GlobalTable").values()
    assert prod["Properties"]["Replicas"][0]["DeletionProtectionEnabled"] is True
    assert prod["DeletionPolicy"] == "Retain"
    assert dev["Properties"]["Replicas"][0].get("DeletionProtectionEnabled") in (None, False)


@pytest.mark.parametrize("stage", ["dev", "prod"])
def test_pepper_is_generated_and_retained(template: TemplateOf, stage: str) -> None:
    (secret,) = resources(
        template(f"staysharp-{stage}-data"), "AWS::SecretsManager::Secret"
    ).values()
    assert secret["DeletionPolicy"] == "Retain"
    assert secret["UpdateReplacePolicy"] == "Retain"
    generate = secret["Properties"]["GenerateSecretString"]
    assert generate["PasswordLength"] >= 32
    assert "SecretString" not in secret["Properties"]
