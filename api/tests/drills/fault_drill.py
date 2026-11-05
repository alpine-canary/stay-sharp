"""Fault drill (task T081, V8, SC-004): a scoring failure in dev pages the maintainer.

    make fault-drill STAGE=dev        (AWS_PROFILE with access to the project account)

1. Turns fault injection on for 15 minutes (SSM ``/staysharp/dev/fault-injection``).
2. Plays one answer through the public dev site and expects 503.
3. Waits until the paging alarm is in ALARM (within 5 minutes).
4. Checks the failure log line: ``question_id``, ``request_id``, ``player_hash``; no raw player
   id and no IP address.
5. Always turns injection off again (``finally``). The alarm e-mail is checked by the maintainer.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import time

import boto3

from tests.drills.common import (
    REGION,
    alarm_state,
    call,
    new_player,
    refuse_prod,
    site_domain,
    wait_for,
)

IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
# Twelve digits standing alone (not inside a hash or another id).
ACCOUNT_ID = re.compile(r"(?<![0-9A-Za-z])\d{12}(?![0-9A-Za-z])")


def set_injection(stage: str, until: dt.datetime | None) -> None:
    ssm = boto3.client("ssm", region_name=REGION)
    ssm.put_parameter(
        Name=f"/staysharp/{stage}/fault-injection",
        Value=until.isoformat() if until else "off",
        Type="String",
        Overwrite=True,
    )


def answer_once(domain: str, player: str) -> tuple[int, str]:
    started = call(domain, "POST", "/plays", player, {"level": "senior", "mode": "daily"})
    if started.status not in (200, 201):
        raise SystemExit(f"FAILED: could not start a play ({started.status}: {started.body})")
    play = started.body
    question = play["question"]
    body: dict[str, object] = {"choiceId": question["choices"][0]["id"]}
    if question["deck"] == "spot":
        body["line"] = 1
    reply = call(
        domain,
        "POST",
        f"/plays/{play['playId']}/questions/{question['index']}/answer",
        player,
        body,
    )
    return reply.status, str(play["playId"])


def failure_log(stage: str, since_ms: int) -> dict[str, object] | None:
    logs = boto3.client("logs", region_name=REGION)
    events = logs.filter_log_events(
        logGroupName=f"/aws/lambda/staysharp-{stage}-api",
        startTime=since_ms,
        filterPattern='"scoring failure"',
    )["events"]
    for event in events:
        try:
            line: dict[str, object] = json.loads(event["message"])
        except ValueError:
            continue
        if line.get("message") == "scoring failure":
            line["_raw"] = event["message"]
            return line
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--stage", default="dev")
    args = parser.parse_args()
    refuse_prod(args.stage)

    domain = site_domain(args.stage)
    player = new_player()
    since_ms = int(time.time() * 1000) - 5_000
    print(f"fault drill on {args.stage} ({domain})")
    try:
        set_injection(args.stage, dt.datetime.now(dt.UTC) + dt.timedelta(minutes=15))
        print("  injection on; waiting 15 s for the function cache")
        time.sleep(15)
        started = time.monotonic()
        status, _play_id = answer_once(domain, player)
        if status != 503:
            raise SystemExit(f"FAILED: expected 503 from the answer, got {status}")
        print("  answer refused with 503, as injected")

        paging = f"staysharp-{args.stage}-ops-PagingScoringFailures"
        wait_for(
            "paging alarm in ALARM",
            lambda: True if alarm_state(paging) == "ALARM" else None,
            timeout_s=300 - (time.monotonic() - started),
        )
        line = wait_for(
            "the scoring failure log line",
            lambda: failure_log(args.stage, since_ms),
            timeout_s=120,
        )
        raw = str(line.pop("_raw"))
        missing = [k for k in ("question_id", "request_id", "player_hash") if not line.get(k)]
        if missing:
            raise SystemExit(f"FAILED: the log line lacks {missing}")
        if player in raw:
            raise SystemExit("FAILED: the raw player id is in the log")
        if IPV4.search(raw):
            raise SystemExit("FAILED: an IP address is in the log")
        if ACCOUNT_ID.search(raw):
            raise SystemExit("FAILED: an account id is in the log")
        print("  log line has question_id, request_id, player_hash; no raw id, no IP")
    finally:
        set_injection(args.stage, None)
        print("  injection off")

    print(
        "PASSED. Check the alarm e-mail in the inbox of /staysharp/dev/alarm-email; "
        "an OK e-mail follows within a few minutes."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
