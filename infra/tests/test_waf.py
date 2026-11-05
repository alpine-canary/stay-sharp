"""WAF on CloudFront (task T116, research R9, W12).

One web ACL in us-east-1 (CloudFront scope), shared by the dev and prod distributions: a rate
rule of 1,000 requests per 5 minutes per IP on ``/api/*`` answering the JSON 429 body of R9, a
rule refusing ``/api/*`` bodies over 2 KB, and the AWS managed common rule set. No logging and
no sampled requests, since both would keep IP addresses.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from tests.conftest import TemplateOf, resources

RATE_BODY = {"code": "rate_limited", "message": "Too many requests. Try again in a few minutes."}


def web_acl(template: TemplateOf) -> dict[str, Any]:
    (acl,) = resources(template("staysharp-edge"), "AWS::WAFv2::WebACL").values()
    properties: dict[str, Any] = acl["Properties"]
    return properties


def rule(acl: dict[str, Any], name: str) -> dict[str, Any]:
    (found,) = [r for r in acl["Rules"] if r["Name"] == name]
    result: dict[str, Any] = found
    return result


def starts_with_api(statement: dict[str, Any]) -> bool:
    match = statement.get("ByteMatchStatement", {})
    return (
        match.get("SearchString") == "/api/"
        and match.get("PositionalConstraint") == "STARTS_WITH"
        and "UriPath" in match.get("FieldToMatch", {})
    )


def test_one_cloudfront_acl_without_logs_or_samples(template: TemplateOf) -> None:
    acl = web_acl(template)
    assert acl["Scope"] == "CLOUDFRONT"
    assert acl["DefaultAction"] == {"Allow": {}}
    for item in [acl, *acl["Rules"]]:
        assert item["VisibilityConfig"]["SampledRequestsEnabled"] is False
    assert not resources(template("staysharp-edge"), "AWS::WAFv2::LoggingConfiguration")


def test_rate_rule_on_api_with_the_json_429(template: TemplateOf) -> None:
    acl = web_acl(template)
    rate = rule(acl, "ApiRatePerIp")
    statement = rate["Statement"]["RateBasedStatement"]
    assert statement["Limit"] == 1000
    assert statement["EvaluationWindowSec"] == 300
    assert statement["AggregateKeyType"] == "IP"
    assert starts_with_api(statement["ScopeDownStatement"])
    response = rate["Action"]["Block"]["CustomResponse"]
    assert response["ResponseCode"] == 429
    body = acl["CustomResponseBodies"][response["CustomResponseBodyKey"]]
    assert body["ContentType"] == "APPLICATION_JSON"
    assert json.loads(body["Content"]) == RATE_BODY


def test_api_bodies_over_2_kb_are_refused(template: TemplateOf) -> None:
    acl = web_acl(template)
    size = rule(acl, "ApiBodyOver2KB")
    parts = size["Statement"]["AndStatement"]["Statements"]
    assert any(starts_with_api(p) for p in parts)
    (constraint,) = [p["SizeConstraintStatement"] for p in parts if "SizeConstraintStatement" in p]
    assert constraint["ComparisonOperator"] == "GT"
    assert constraint["Size"] == 2048
    assert constraint["FieldToMatch"]["Body"]["OversizeHandling"] == "MATCH"
    assert size["Action"]["Block"]["CustomResponse"]["ResponseCode"] == 413


def test_managed_common_rule_set(template: TemplateOf) -> None:
    common = rule(web_acl(template), "AwsCommonRuleSet")
    managed = common["Statement"]["ManagedRuleGroupStatement"]
    assert (managed["VendorName"], managed["Name"]) == ("AWS", "AWSManagedRulesCommonRuleSet")
    assert common["OverrideAction"] == {"None": {}}


@pytest.mark.parametrize("stage", ["dev", "prod"])
def test_both_distributions_use_the_acl(template: TemplateOf, stage: str) -> None:
    (dist,) = resources(
        template(f"staysharp-{stage}-web"), "AWS::CloudFront::Distribution"
    ).values()
    assert dist["Properties"]["DistributionConfig"].get("WebACLId")
