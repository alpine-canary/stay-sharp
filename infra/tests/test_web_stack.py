"""CloudFront, S3 and the site router (task T046, scenario V11, research R8, R12)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from aws_cdk import assertions

from app import build_app
from tests.conftest import TemplateOf, cdk_context, resources

STAGES = ("dev", "prod")
CACHING_DISABLED = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad"
ROUTER = Path(__file__).resolve().parents[1] / "stacks" / "site_router.js"


def distribution(template: TemplateOf, stage: str) -> dict[str, Any]:
    (dist,) = resources(
        template(f"staysharp-{stage}-web"), "AWS::CloudFront::Distribution"
    ).values()
    config: dict[str, Any] = dist["Properties"]["DistributionConfig"]
    return config


@pytest.mark.parametrize("stage", STAGES)
def test_api_is_never_cached_and_forwards_two_headers(template: TemplateOf, stage: str) -> None:
    config = distribution(template, stage)
    (api,) = [b for b in config["CacheBehaviors"] if b["PathPattern"] == "/api/*"]
    assert api["CachePolicyId"] == CACHING_DISABLED
    assert api["ViewerProtocolPolicy"] == "https-only"
    assert "POST" in api["AllowedMethods"]
    (policy,) = resources(
        template(f"staysharp-{stage}-web"), "AWS::CloudFront::OriginRequestPolicy"
    ).values()
    settings = policy["Properties"]["OriginRequestPolicyConfig"]
    assert settings["HeadersConfig"] == {
        "HeaderBehavior": "whitelist",
        "Headers": ["X-Player-Id", "Content-Type"],
    }
    assert settings["QueryStringsConfig"] == {"QueryStringBehavior": "none"}
    assert settings["CookiesConfig"] == {"CookieBehavior": "none"}


@pytest.mark.parametrize("stage", STAGES)
def test_bucket_is_private_and_served_through_oac(template: TemplateOf, stage: str) -> None:
    t = template(f"staysharp-{stage}-web")
    (bucket,) = resources(t, "AWS::S3::Bucket").values()
    assert bucket["Properties"]["PublicAccessBlockConfiguration"] == {
        "BlockPublicAcls": True,
        "BlockPublicPolicy": True,
        "IgnorePublicAcls": True,
        "RestrictPublicBuckets": True,
    }
    assert len(resources(t, "AWS::CloudFront::OriginAccessControl")) == 1
    s3_origin = [o for o in distribution(template, stage)["Origins"] if "S3OriginConfig" in o]
    assert s3_origin[0]["OriginPath"] == "/site/initial"
    assert "Logging" not in distribution(template, stage)


@pytest.mark.parametrize("stage", STAGES)
def test_strict_security_headers(template: TemplateOf, stage: str) -> None:
    (policy,) = resources(
        template(f"staysharp-{stage}-web"), "AWS::CloudFront::ResponseHeadersPolicy"
    ).values()
    security = policy["Properties"]["ResponseHeadersPolicyConfig"]["SecurityHeadersConfig"]
    csp = security["ContentSecurityPolicy"]["ContentSecurityPolicy"]
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "unsafe-inline" not in csp
    assert "unsafe-eval" not in csp
    assert security["StrictTransportSecurity"]["AccessControlMaxAgeSec"] >= 31_536_000
    assert security["FrameOptions"]["FrameOption"] == "DENY"
    behaviors = [
        distribution(template, stage)["DefaultCacheBehavior"],
        *distribution(template, stage)["CacheBehaviors"],
    ]
    assert all("ResponseHeadersPolicyId" in b for b in behaviors)


def test_only_prod_uses_the_public_name(template: TemplateOf) -> None:
    assert distribution(template, "prod")["Aliases"] == ["stay-sharp.lumineth.com"]
    assert "Aliases" not in distribution(template, "dev")


@pytest.mark.parametrize("stage", STAGES)
def test_no_custom_error_responses(template: TemplateOf, stage: str) -> None:
    # They would also rewrite API errors into HTML (W18): the router answers 404 instead.
    assert "CustomErrorResponses" not in distribution(template, stage)


@pytest.mark.parametrize("stage", STAGES)
def test_router_is_attached_to_the_site_only(template: TemplateOf, stage: str) -> None:
    config = distribution(template, stage)
    assert len(config["DefaultCacheBehavior"]["FunctionAssociations"]) == 1
    (api,) = config["CacheBehaviors"]
    assert "FunctionAssociations" not in api


ROUTER_CASES = [
    ("/", "/index.html", None),
    ("/play", "/index.html", None),
    ("/practice/", "/index.html", None),
    ("/privacy", "/index.html", None),
    ("/c/ABCDEFGHJKLM", "/index.html", None),
    ("/assets/index-abc123.js", "/assets/index-abc123.js", None),
    ("/fonts/inter.woff2", "/fonts/inter.woff2", None),
    ("/c/short", None, 404),
    ("/wp-admin", None, 404),
    ("/play/extra", None, 404),
]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
@pytest.mark.parametrize(("uri", "rewritten", "status"), ROUTER_CASES)
def test_router_function(uri: str, rewritten: str | None, status: int | None) -> None:
    script = (
        ROUTER.read_text()
        + f"\nprocess.stdout.write(JSON.stringify(handler({{request:{{uri:{json.dumps(uri)}}}}})));"
    )
    out = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)  # noqa: S603, S607
    result = json.loads(out.stdout)
    if status is None:
        assert result["uri"] == rewritten
    else:
        assert result["statusCode"] == status
        assert "Page not found" in result["body"]["data"]


def test_site_upload_splits_assets_and_pages_and_comes_before_the_switch(tmp_path: Path) -> None:
    """The deploy workflow passes siteDist: files first, then the origin path (W6)."""
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html>")
    (dist / "assets" / "index-abc.js").write_text("x")
    context = {**cdk_context(), "siteCommit": "abc123", "siteDist": str(dist)}
    assembly = build_app(context).synth()
    artifact = assembly.get_stack_by_name("staysharp-dev-web")
    t = assertions.Template.from_json(artifact.template)
    uploads = {
        k: v["Properties"] for k, v in t.find_resources("Custom::CDKBucketDeployment").items()
    }
    assert len(uploads) == 2
    prefixes = sorted(p["DestinationBucketKeyPrefix"] for p in uploads.values())
    assert prefixes == ["site/abc123/", "site/abc123/assets/"]
    assert all(p["Prune"] is False for p in uploads.values())
    controls = sorted(json.dumps(p.get("SystemMetadata", {})) for p in uploads.values())
    assert any("immutable" in c for c in controls)
    assert any("must-revalidate" in c for c in controls)
    (dist_key,) = t.find_resources("AWS::CloudFront::Distribution")
    depends = set(t.to_json()["Resources"][dist_key].get("DependsOn", []))
    assert any(k.startswith("SitePages") for k in depends)

    contents = {}
    for asset in Path(assembly.directory).glob("asset.*"):
        if asset.is_dir():
            contents[asset.name] = sorted(
                str(p.relative_to(asset)) for p in asset.rglob("*") if p.is_file()
            )
    site_sets = [files for files in contents.values() if any("index" in f for f in files)]
    assert ["index-abc.js"] in contents.values()
    assert ["index.html"] in site_sets


def test_no_upload_without_site_dist(template: TemplateOf) -> None:
    assert not template("staysharp-dev-web").find_resources("Custom::CDKBucketDeployment")
