"""Per-stage site: private S3 behind CloudFront, ``/api/*`` to the HTTP API (task T044).

- Static files live under ``site/<commit>/``; the origin path points at the current one, so
  redeploying the previous commit is an instant revert (W6).
- ``/api/*`` is never cached and forwards only ``X-Player-Id`` and ``Content-Type`` (C2), plus
  ``Authorization`` for the account routes (M2). CloudFront passes ``Authorization`` on GET only
  through a cache policy, so ``/api/*`` has its own: at most 1 second, and the API answers
  ``Cache-Control: no-store``, so nothing is ever stored.
- A strict CSP and security headers on every response (R12).
- A CloudFront Function maps app paths to their HTML entry and answers a real 404 for anything
  else, without custom error responses (those would also rewrite API errors, W18).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aws_cdk import Duration, RemovalPolicy, Stack
from aws_cdk import aws_certificatemanager as acm
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as s3deploy
from constructs import Construct

ROUTER_JS = Path(__file__).with_name("site_router.js")

CSP = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self' data:",
        "font-src 'self'",
        # The account pages talk to the Cognito user pool API in Zurich (M2, research A1).
        "connect-src 'self' https://cognito-idp.eu-central-2.amazonaws.com",
        "manifest-src 'self'",
        "object-src 'none'",
        "base-uri 'none'",
        "form-action 'none'",
        "frame-ancestors 'none'",
        "upgrade-insecure-requests",
    ]
)
API_HEADERS = ("X-Player-Id", "Content-Type")


class WebStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        stage: str,
        api_domain: str,
        site_commit: str,
        site_dist: str | None = None,
        domain_name: str | None = None,
        certificate: acm.ICertificate | None = None,
        web_acl_arn: str | None = None,
        auth_config: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        prod = stage == "prod"

        self.bucket = s3.Bucket(
            self,
            "Site",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            object_ownership=s3.ObjectOwnership.BUCKET_OWNER_ENFORCED,
            removal_policy=RemovalPolicy.RETAIN if prod else RemovalPolicy.DESTROY,
            auto_delete_objects=not prod,
        )

        headers = cloudfront.ResponseHeadersPolicy(
            self,
            "SecurityHeaders",
            response_headers_policy_name=f"staysharp-{stage}-security-headers",
            security_headers_behavior=cloudfront.ResponseSecurityHeadersBehavior(
                content_security_policy=cloudfront.ResponseHeadersContentSecurityPolicy(
                    content_security_policy=CSP, override=True
                ),
                strict_transport_security=cloudfront.ResponseHeadersStrictTransportSecurity(
                    access_control_max_age=Duration.days(730),
                    include_subdomains=False,
                    preload=False,
                    override=True,
                ),
                content_type_options=cloudfront.ResponseHeadersContentTypeOptions(override=True),
                frame_options=cloudfront.ResponseHeadersFrameOptions(
                    frame_option=cloudfront.HeadersFrameOption.DENY, override=True
                ),
                referrer_policy=cloudfront.ResponseHeadersReferrerPolicy(
                    referrer_policy=cloudfront.HeadersReferrerPolicy.STRICT_ORIGIN_WHEN_CROSS_ORIGIN,
                    override=True,
                ),
            ),
            custom_headers_behavior=cloudfront.ResponseCustomHeadersBehavior(
                custom_headers=[
                    cloudfront.ResponseCustomHeader(
                        header="Permissions-Policy",
                        value="camera=(), microphone=(), geolocation=(), interest-cohort=()",
                        override=True,
                    )
                ]
            ),
        )

        router = cloudfront.Function(
            self,
            "Router",
            function_name=f"staysharp-{stage}-router",
            code=cloudfront.FunctionCode.from_file(file_path=str(ROUTER_JS)),
            runtime=cloudfront.FunctionRuntime.JS_2_0,
            comment="App paths to their HTML entry; real 404 otherwise",
        )

        api_requests = cloudfront.OriginRequestPolicy(
            self,
            "ApiRequests",
            origin_request_policy_name=f"staysharp-{stage}-api-requests",
            header_behavior=cloudfront.OriginRequestHeaderBehavior.allow_list(*API_HEADERS),
            query_string_behavior=cloudfront.OriginRequestQueryStringBehavior.none(),
            cookie_behavior=cloudfront.OriginRequestCookieBehavior.none(),
        )

        api_cache = cloudfront.CachePolicy(
            self,
            "ApiNoStore",
            cache_policy_name=f"staysharp-{stage}-api-no-store",
            comment="Never cached (no-store from the API); forwards Authorization",
            default_ttl=Duration.seconds(0),
            min_ttl=Duration.seconds(0),
            max_ttl=Duration.seconds(1),
            header_behavior=cloudfront.CacheHeaderBehavior.allow_list("Authorization"),
            query_string_behavior=cloudfront.CacheQueryStringBehavior.none(),
            cookie_behavior=cloudfront.CacheCookieBehavior.none(),
            enable_accept_encoding_gzip=False,
            enable_accept_encoding_brotli=False,
        )

        self.distribution = cloudfront.Distribution(
            self,
            "Distribution",
            comment=f"staysharp-{stage}",
            default_root_object="index.html",
            domain_names=[domain_name] if domain_name else None,
            certificate=certificate,
            minimum_protocol_version=(
                cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021 if certificate else None
            ),
            http_version=cloudfront.HttpVersion.HTTP2_AND_3,
            web_acl_id=web_acl_arn,
            price_class=cloudfront.PriceClass.PRICE_CLASS_100,
            enable_logging=False,
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(
                    self.bucket, origin_path=f"/site/{site_commit}"
                ),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                response_headers_policy=headers,
                compress=True,
                function_associations=[
                    cloudfront.FunctionAssociation(
                        function=router, event_type=cloudfront.FunctionEventType.VIEWER_REQUEST
                    )
                ],
            ),
            additional_behaviors={
                "/api/*": cloudfront.BehaviorOptions(
                    origin=origins.HttpOrigin(
                        api_domain, protocol_policy=cloudfront.OriginProtocolPolicy.HTTPS_ONLY
                    ),
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.HTTPS_ONLY,
                    allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                    cache_policy=api_cache,
                    origin_request_policy=api_requests,
                    response_headers_policy=headers,
                    compress=True,
                )
            },
        )
        if site_dist:
            self._upload_site(site_dist, site_commit, auth_config)

    def _upload_site(
        self, site_dist: str, site_commit: str, auth_config: dict[str, str] | None
    ) -> None:
        """Upload the built site under ``site/<commit>/`` before the origin path points there.

        Hashed files under ``assets/`` never change: cached for a year. Everything else (the
        HTML) is revalidated on each request, so a new release is seen at once. Older commits
        stay in the bucket, so pointing back at one is an instant revert (W6).

        ``auth.json`` (M2) tells the account pages where to sign in: the user pool API endpoint
        and the website client id, both public. Written with the pages, so it follows reverts.
        """
        prefix = f"site/{site_commit}/"
        common: dict[str, Any] = {
            "destination_bucket": self.bucket,
            "prune": False,
            "memory_limit": 256,
        }
        assets = s3deploy.BucketDeployment(
            self,
            "SiteAssets",
            sources=[s3deploy.Source.asset(str(Path(site_dist) / "assets"))],
            destination_key_prefix=f"{prefix}assets/",
            cache_control=[
                s3deploy.CacheControl.from_string("public, max-age=31536000, immutable")
            ],
            **common,
        )
        page_sources = [s3deploy.Source.asset(site_dist, exclude=["assets", "assets/**"])]
        if auth_config:
            page_sources.append(s3deploy.Source.json_data("auth.json", auth_config))
        pages = s3deploy.BucketDeployment(
            self,
            "SitePages",
            sources=page_sources,
            destination_key_prefix=prefix,
            cache_control=[s3deploy.CacheControl.from_string("public, max-age=0, must-revalidate")],
            **common,
        )
        pages.node.add_dependency(assets)
        self.distribution.node.add_dependency(pages)
