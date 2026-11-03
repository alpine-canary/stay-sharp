# Quickstart and validation guide: M1

**Date**: 2026-11-03 (revised after the plan audit) | **Plan**: [plan.md](./plan.md)

How to prove M1 works, end to end. Commands are the intended interface; they exist once the
tasks are implemented. Contracts: [contracts/openapi.yaml](./contracts/openapi.yaml). Data:
[data-model.md](./data-model.md). Decisions: [research.md](./research.md).

## Prerequisites

- Python 3.13, `uv`; Node.js 22 LTS, `pnpm`; AWS CDK v2 CLI; Docker (DynamoDB Local).
- For cloud checks: SSO access to the `stay-sharp` account. No Bedrock is used in M1.

## Local setup

```sh
uv sync --directory api && pnpm --dir front install && uv sync --directory infra
docker compose up -d dynamodb                                     # DynamoDB Local on :8000
uv run --directory api python -m staysharp.tools.seed --fixtures  # samples + test fixtures only
uv run --directory api python -m staysharp.local                  # API on :3001
pnpm --dir front dev                                              # site on :5173, proxies /api
```

## Validation scenarios

| # | Proves | How | Expected |
|---|---|---|---|
| V1 | Story 1, FR-001 to FR-009 | `pnpm --dir front test:e2e --grep "daily"` | Full daily by keyboard only; grade, answer, explanation after each; resume after reload continues at the first unanswered question. |
| V2 | Answers invisible (FR-003, SC-002) | `uv run --directory api pytest tests/unit/test_views.py`; `pnpm --dir front test:e2e --grep "leak"`; in the content repo `uv run publish leak-check --days 7` | Allowlist test: a full item cannot produce answer fields. E2E: nothing before an answer contains the correct id marked, explanation or source. Content check over today + 7 days: zero matches, prints counts only. |
| V3 | Same answer twice (FR-006, SC-003) | `uv run --directory api pytest tests/integration/test_idempotency.py` (DynamoDB Local) | 2, 10, 50 identical submissions, sequential and concurrent: one grade, score unchanged, `duplicate: true` after the first; a different answer gets `409` with the stored result. |
| V4 | Speed bonus and relaxed (FR-005a to FR-005d) | `uv run --directory api pytest tests/unit/test_grading.py tests/integration/test_timing.py` | Bonus only for grade 1 within target and not relaxed; relaxed mid-play stops bonuses from that question; reload does not reset `servedAt`. |
| V5 | Streak, freeze, duplicates in the browser | `pnpm --dir front test -- progress` | Day-sequence table (freeze earned on the 5th daily of a week, used on one missed day, two missed days reset, DST weeks, play finished after midnight counts for its own date); `duplicate: true` changes no count or box. |
| V6 | Challenge (Story 4) | `pnpm --dir front test:e2e --grep "challenge"` | Owner creates a link; colleague sees only the score, plays, then both see both; a colleague who already finished sees both at once; expired, malformed and over-cap links behave as specified. |
| V7 | Publish rules (Story 7) | Content repo: `uv run publish validate fixtures/invalid` then `fixtures/valid` | Each invalid case (wrong deck order, wrong level, qid on two dates, sample in a schedule, line outside code, missing target, Starter without second reader, edit without reason, date in id) refused with id and reason; nothing written. |
| V8 | Scoring alarm (FR-028, SC-004) | `make fault-drill STAGE=dev` | Paging alarm and e-mail within 5 minutes; logs carry `question_id`, `request_id`, `player_hash`, no IP or raw id; dev restored in a `finally` step. |
| V9 | Canary rollback (FR-029, SC-005) | `make canary-drill STAGE=dev CANARY=LambdaCanary10Percent5Minutes` | (a) a version whose self-check fails is stopped before traffic; (b) a version that fails under traffic trips the version-scoped alarms; both roll back with no human action, `live` on the previous version within 15 minutes, e-mail received. |
| V10 | Accessibility and Lighthouse | `pnpm --dir front lhci`; `pnpm --dir front test:e2e --grep "a11y"` | 100 x4 mobile and desktop on every page; axe finds no WCAG 2.2 AA violation; relaxed reachable before and during a play. |
| V11 | Infra rules | `uv run --directory infra pytest` | `/api/*` behaviour uses caching disabled and forwards only `X-Player-Id` and `Content-Type`; no public bucket; PITR and TTL on; alarms with the R10 dimensions and `notBreaching`; stock alarm `breaching`; no fault-injection file in the prod asset; one role per function; OIDC `sub` conditions exact; pepper secret retained; `POWERTOOLS_LOGGER_LOG_EVENT=false`; log retention 30 days; access logs without `sourceIp`. |
| V12 | Budget | `uv run --directory infra pytest -k budget` | One USD 20 budget for the account with actual and forecast notifications. |
| V13 | Replay is not an answer key (C3) | `uv run --directory api pytest tests/integration/test_replay.py` | `mode=replay` for today before the daily is finished: `409`; after: allowed, unscored. |
| V14 | Practice cannot reach future content (C4) | `uv run --directory api pytest tests/integration/test_practice.py` | `prefer` with a future qid, an unknown qid or another level's qid returns a normal past pool question; never the requested one. |
| V15 | Storage failure paths (W15) | `uv run --directory api pytest tests/integration/test_failures.py` | Throttled or timed-out transaction: retried, then `503`, one `ScoringFailures`, no partial write, never `duplicate`. |
| V16 | Midnight (W2) | `pnpm --dir front test:e2e --grep "midnight"` with a mocked server clock | Play started 23:58 finishes 00:03: counts for its start date; the new day's set is a separate play. |
| V17 | First question speed (SC-007) | `pnpm --dir front test:e2e --grep "perf"` (Moto G Power profile, Slow 4G) | First question interactive under 2 s, cold Lambda included, on dev. |
| V18 | Public leak guard (FR-024b) | Push a branch with a fixture that copies a future prompt (content repo test key) | Public CI fails, prints file path and match count, no text. |

## Done means

V1 to V18 pass, CI is green on `main`, step 0 (public history) is done, the prod deploy went
through the canary, and the README "Numbers" section still says "Not measured yet" until one full
month of data exists.
