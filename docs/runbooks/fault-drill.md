# Runbook: fault and canary drills (dev only)

The drills prove that a scoring failure pages the maintainer (V8, SC-004) and that a bad version
never stays live (V9, SC-005). Both refuse to run against anything but dev. Run them after any
change to alarms, metrics, logging or the deployment setup, and at least once a quarter.

Before you start: `aws sso login --profile stay-sharp`, and confirm you can read the inbox of the
address stored in `/staysharp/dev/alarm-email`.

## Fault drill (about 3 minutes)

```sh
AWS_PROFILE=stay-sharp AWS_REGION=eu-central-2 make fault-drill STAGE=dev
```

What it does: turns fault injection on for 15 minutes (SSM `/staysharp/dev/fault-injection`),
plays one answer through the dev site and expects 503, waits for the paging alarm (within 5
minutes), checks the failure log line (ids only: no raw player id, IP or account id), and always
turns injection off at the end.

Then check your inbox: an ALARM e-mail, and an OK e-mail a few minutes later.

If it fails:
- No alarm: check the metric reaches CloudWatch with exactly the dimensions the alarm watches
  (`aws cloudwatch list-metrics --namespace StaySharp`). An extra dimension (for example
  `service`) means the alarm can never match.
- Injection left on: it switches itself off 30 minutes after it was set, and the
  `FaultInjectionLeftOn` alarm fires if it keeps injecting. To stop it at once:
  `aws ssm put-parameter --name /staysharp/dev/fault-injection --value off --type String --overwrite`.

## Canary drill (about 25 minutes)

Wait until the fault drill's alarms are back to OK (the drill also waits for that).

```sh
AWS_PROFILE=stay-sharp AWS_REGION=eu-central-2 \
  make canary-drill STAGE=dev CANARY=LambdaCanary10Percent5Minutes
```

What it does, with the dev-only `drill` context:

1. Deploys a version whose self-check fails. Expected: CodeDeploy stops it with
   `HOOK_EXECUTION_FAILURE`, before any traffic; `live` stays on the previous version.
2. Deploys a version that fails every request, with the canary, while sending traffic. Expected:
   the version-scoped alarms fire and CodeDeploy rolls back with `ALARM_ACTIVE`; `live` stays on
   the previous version.

Each case must end within 15 minutes with no human action. CloudFormation rolls the stack back
afterwards, so dev ends on its normal template. Check the inbox for the failure and rollback
e-mails.

A drill never runs against prod: the scripts, the CDK app (prod refuses the `drill` context) and
the fault-injection code (absent from the prod package, refused when `STAGE=prod`) each check it.
