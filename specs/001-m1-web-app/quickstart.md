# Quickstart and validation guide: M1

**Date**: 2026-11-03 | **Plan**: [plan.md](./plan.md)

How to prove M1 works, end to end. Commands are the intended interface; they exist once the
tasks are implemented. Contracts: [contracts/openapi.yaml](./contracts/openapi.yaml). Data:
[data-model.md](./data-model.md).

## Prerequisites

- Python 3.13, `uv`; Node.js 22 LTS, `pnpm`; AWS CDK v2 CLI; Docker (DynamoDB Local).
- For cloud checks: access to the `stay-sharp-dev` account through SSO. No production access is
  needed for any check below except V9.
- No Bedrock access is needed or used in M1.

## Local setup

```sh
uv sync --directory api && pnpm --dir front install && uv sync --directory infra
docker compose up -d dynamodb            # DynamoDB Local on :8000
uv run --directory api python -m staysharp.tools.seed --samples   # sample + selftest questions only
uv run --directory api python -m staysharp.local                  # API on :3001
pnpm --dir front dev                                              # site on :5173, proxies /api
```

## Validation scenarios

| # | Proves | How | Expected |
|---|---|---|---|
| V1 | Story 1, FR-001 to FR-009 | `pnpm --dir front test:e2e --grep "daily"` (local) | A full daily is played by keyboard only; each answer shows grade, correct answer, explanation; resume after reload continues at the first unanswered question. |
| V2 | Answers invisible (FR-003, SC-002) | `pnpm --dir front test:e2e --grep "leak"` (local), then `make leak-scan ENV=dev DAYS=7` | The scan records every response, script and storage entry before each answer and finds no correct choice id marked, no explanation text, no source. Contract test rejects any extra field. Exit code 0. |
| V3 | Same answer twice counts once (FR-006, SC-003) | `uv run --directory api pytest tests/integration/test_idempotency.py` | Same answer sent 2, 10 and 50 times, sequential and concurrent (threads): one stored grade, score unchanged, `duplicate: true` after the first; a different answer gets `409`. |
| V4 | Speed bonus and relaxed (FR-005a to FR-005d) | `uv run --directory api pytest tests/unit/test_grading.py tests/integration/test_timing.py` | Bonus 0.2 only for grade 1 within target and not relaxed; reload does not reset `servedAt`; fast answers counted in `SuspiciouslyFast`. |
| V5 | Streak and freeze (FR-012 to FR-014) | `pnpm --dir front test -- progress` | The table of day sequences (freeze earned on the 5th daily of a week, used on one missed day, two missed days reset, DST weeks) matches the expected streak and longest streak. |
| V6 | Challenge (Story 4) | `pnpm --dir front test:e2e --grep "challenge"` | Two browser contexts: owner creates a link; colleague sees only the score, plays, then both see both snapshots; expired or malformed id shows the plain message. |
| V7 | Publish rules (Story 7, FR-024 to FR-027) | In the content repository: `uv run publish validate fixtures/invalid` then `uv run publish validate fixtures/valid` | Invalid batch refused with question id and reason, nothing written; valid batch passes; editing a past question creates version n+1 and does not change stored grades. |
| V8 | Scoring alarm (FR-028, SC-004) | `make fault-drill ENV=dev` (deploys dev with `FAULT_INJECTION=scoring`, sends one answer, waits) | `ScoringFailures` alarm goes to ALARM and the maintainer e-mail arrives within 5 minutes; logs carry `question_id` and `request_id`, no player id or IP. The drill then redeploys without the flag. |
| V9 | Canary rollback (FR-029, SC-005) | `make canary-drill ENV=dev CANARY=LambdaCanary10Percent5Minutes` | The pre-traffic check fails or the rollback alarms fire; CodeDeploy rolls back with no human action; `live` alias points at the previous version within 15 minutes; e-mail received. Run before the first prod release and after any change to the deploy setup. |
| V10 | Accessibility and Lighthouse (FR-033, FR-034, SC-006) | `pnpm --dir front lhci` and `pnpm --dir front test:e2e --grep "a11y"` | 100 in all four categories, mobile and desktop, on home, play, result, practice, challenge and privacy pages; axe finds no WCAG 2.2 AA violation. |
| V11 | Infra rules | `uv run --directory infra pytest` | Assertions pass: no public bucket, TLS only, PITR on, TTL on, alarms exist, no `FAULT_INJECTION` in prod, one IAM role per function with no `*` actions on data, log retention set, access logs without `sourceIp`. |
| V12 | Budget (FR-031) | `uv run --directory infra pytest -k budget` and check the AWS Budgets console once after deploy | Budget of USD 20 with actual and forecast notifications to the maintainer e-mail. |

## Done means

All of V1 to V12 pass, CI is green on `main`, the prod deploy went through the canary, and the
README "Numbers" section still says "Not measured yet" until one full month of data exists.
