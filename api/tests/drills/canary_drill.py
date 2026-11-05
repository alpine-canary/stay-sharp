"""Canary drill (task T082, V9, SC-005): a bad version never stays live in dev.

    make canary-drill STAGE=dev CANARY=LambdaCanary10Percent5Minutes

(a) Deploys a version whose self-check fails: the pre-traffic hook stops it before any traffic.
(b) Deploys a version that fails every request: during the canary the version-scoped alarms go
    off and CodeDeploy rolls back by itself.

Both are deployed with ``cdk deploy`` and the dev-only ``drill`` context. After each, ``live``
must point at the version it had before, within 15 minutes, with no human action. The failure
and rollback e-mails are checked by the maintainer.
"""

from __future__ import annotations

import argparse
import subprocess  # noqa: S404 - runs the pinned CDK CLI of this repository
import threading
import time
from pathlib import Path

import boto3

from tests.drills.common import REGION, call, refuse_prod, site_domain, wait_for

INFRA = Path(__file__).resolve().parents[3] / "infra"
CDK = ["npx", "--yes", "aws-cdk@2.1147.0"]
LIMIT_S = 15 * 60


def live_version(stage: str) -> str:
    client = boto3.client("lambda", region_name=REGION)
    return str(
        client.get_alias(FunctionName=f"staysharp-{stage}-api", Name="live")["FunctionVersion"]
    )


def last_deployment(stage: str) -> dict[str, object]:
    """The bad deployment: if the newest one is CloudFormation's rollback, the one it undid."""
    client = boto3.client("codedeploy", region_name=REGION)
    ids = client.list_deployments(
        applicationName=f"staysharp-{stage}-api", deploymentGroupName=f"staysharp-{stage}-api"
    )["deployments"]
    if not ids:
        raise SystemExit("FAILED: no CodeDeploy deployment found")
    info = client.get_deployment(deploymentId=ids[0])["deploymentInfo"]
    triggered_by = (info.get("rollbackInfo") or {}).get("rollbackTriggeringDeploymentId")
    if triggered_by:
        info = client.get_deployment(deploymentId=triggered_by)["deploymentInfo"]
    return {
        "id": info["deploymentId"],
        "status": info["status"],
        "error": (info.get("errorInformation") or {}).get("code"),
        "rolled_back": bool(triggered_by),
    }


def deploy(stage: str, canary: str, drill: str | None) -> int:
    command = [
        *CDK,
        "deploy",
        f"staysharp-{stage}-api",
        "--exclusively",
        "--require-approval",
        "never",
        "-c",
        f"devDeploymentConfig={canary}",
    ]
    if drill:
        command += ["-c", f"drill={drill}"]
    print(f"  cdk deploy ({drill or 'normal'}, {canary})")
    result = subprocess.run(command, cwd=INFRA, check=False, capture_output=True, text=True)  # noqa: S603
    return result.returncode


def traffic(domain: str, stop: threading.Event) -> None:
    while not stop.is_set():
        call(domain, "GET", "/health", None)
        time.sleep(0.5)


def rollback_alarms_quiet(stage: str) -> bool:
    """A case only proves something if no rollback alarm is already firing."""
    cloudwatch = boto3.client("cloudwatch", region_name=REGION)
    alarms = cloudwatch.describe_alarms(AlarmNamePrefix=f"staysharp-{stage}-api-")["MetricAlarms"]
    return all(a["StateValue"] != "ALARM" for a in alarms)


def run_case(stage: str, canary: str, drill: str, domain: str, expected_error: str) -> None:
    wait_for(
        "rollback alarms quiet",
        lambda: True if rollback_alarms_quiet(stage) else None,
        timeout_s=900,
        every_s=30,
    )
    before = live_version(stage)
    print(f"case {drill}: live is version {before}")
    started = time.monotonic()
    stop = threading.Event()
    sender = threading.Thread(target=traffic, args=(domain, stop), daemon=True)
    sender.start()
    try:
        code = deploy(stage, canary, drill)
    finally:
        stop.set()
        sender.join(timeout=5)
    took = time.monotonic() - started
    after = live_version(stage)
    deployment = last_deployment(stage)
    print(f"  deploy exit {code} after {took:.0f} s; deployment {deployment}")
    if code == 0:
        raise SystemExit("FAILED: the bad version deployed successfully")
    if after != before:
        raise SystemExit(f"FAILED: live moved from {before} to {after}")
    if deployment["status"] not in ("Failed", "Stopped"):
        raise SystemExit(f"FAILED: the deployment ended {deployment['status']}")
    if deployment["error"] != expected_error:
        raise SystemExit(f"FAILED: stopped by {deployment['error']}, expected {expected_error}")
    if took > LIMIT_S:
        raise SystemExit(f"FAILED: took {took:.0f} s, more than {LIMIT_S} s")
    print(f"  ok: live stayed on {before}, stopped in {took:.0f} s with no human action")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--stage", default="dev")
    parser.add_argument("--canary", default="LambdaCanary10Percent5Minutes")
    parser.add_argument("--only", choices=["selfcheck-fail", "fail-traffic"])
    args = parser.parse_args()
    refuse_prod(args.stage)

    domain = site_domain(args.stage)
    # What should stop each bad version: the pre-traffic hook, then the version-scoped alarms.
    expected = {"selfcheck-fail": "HOOK_EXECUTION_FAILURE", "fail-traffic": "ALARM_ACTIVE"}
    cases = [args.only] if args.only else list(expected)
    for drill in cases:
        run_case(args.stage, args.canary, drill, domain, expected[drill])
    print(
        "PASSED. Check the failure and rollback e-mails in the inbox of /staysharp/dev/alarm-email."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
