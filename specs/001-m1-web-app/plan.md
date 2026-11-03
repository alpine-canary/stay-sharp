# Implementation Plan: M1 - public daily game without accounts

**Branch**: `001-m1-web-app` | **Date**: 2026-11-03 (revised after the plan audit) |
**Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-m1-web-app/spec.md`

## Summary

A public web game with two levels (Senior, Starter 12+), five questions a day, graded on the
server. The browser gets one question at a time, built from a field allowlist, without its answer;
the server records when it sent the question, grades the answer once (conditional write in a
DynamoDB transaction, old item returned on cancellation), adds a speed bonus, and only then
returns the answer and explanation. Streak, freeze, skill view and practice boxes live in the
browser in M1. Challenge links store anonymous result snapshots written in the same transaction
as the last answer. Questions live in a private content repository; only fixtures reach dev, and a
two-layer leak guard gates every prod release. One API Lambda behind API Gateway and CloudFront
(`/api/*` never cached), deployed with a CodeDeploy canary whose pre-traffic step runs a data-free
self-check on the new version, and which rolls back on version-scoped alarms. Everything in CDK
(Python) in one dedicated AWS account, gated by GitHub Actions with no AWS credentials on pull
requests.

## Technical Context

**Language/Version**: Python 3.13 (API, tools, CDK); TypeScript 5 strict (front end)

**Primary Dependencies**: AWS Lambda Powertools for Python (event handler, logger, metrics,
parser), Pydantic v2, boto3; React 19, Vite, Tailwind CSS v4; AWS CDK v2

**Storage**: DynamoDB (one table per stage, on-demand, PITR, TTL); S3 (versioned site prefixes);
Secrets Manager (one pepper per stage); browser `localStorage` for local progress

**Testing**: pytest (DynamoDB Local for anything transactional, moto only for simple units), CDK
assertions; Vitest, Testing Library; Playwright with axe-core; Lighthouse CI; contract tests
against `contracts/openapi.yaml`

**Target Platform**: AWS Lambda arm64 in `eu-central-2`; CloudFront; evergreen browsers from 390 px

**Project Type**: web application (static front end + serverless API + infrastructure)

**Performance Goals**: first question usable within 2 s on a mid-range phone on 4G (two round
trips at most); answer round trip p95 under 500 ms warm; Lighthouse 100 x4

**Constraints**: no answer in the browser before submit; no personal data stored or logged; data
in Switzerland or EU; USD 20 a month budget; WCAG 2.2 AA; no hard time limit

**Scale/Scope**: hundreds to low thousands of players a day; 2 levels x 5 questions a day; 140
questions at launch; about 8 screens

## Constitution Check

*Initial gate: pass. Re-checked after the audit revision: pass.*

| Principle | How this plan complies | Status |
|---|---|---|
| I. Honesty | README "Numbers" stays "Not measured yet"; costs in R15 labelled estimates, with the worst case close to the limit stated; retention written as "about"; the shared-answer residual is written down (R1, spec Assumptions); reserved concurrency recorded as an availability trade-off. | Pass |
| II. Deterministic, server-side grading | Pure grading function; allowlist view builder with a test that feeds it a full item; one question at a time; random choice ids and publish-time shuffle with a uniformity check; replay of today refused until the daily is finished; practice limited to the past pool; `/api/*` never cached; content only in the private repo, fixtures only in dev; leak guard in both repos and a release gate (R1, R4, R8). | Pass |
| III. Model proposes, person decides | No model in M1; questions human-written, approved, Starter with a second reader; no Bedrock permission in any role. | Pass |
| IV. Reliability first | Transaction with a cancellation-reason table, retries only for temporary errors, `503` plus `ScoringFailures` otherwise (R2); timeouts and limited retries on every client; every response checked; async functions with on-failure destinations; missing stock metric treated as breaching. No queues in M1, so DLQ, `maxReceiveCount`, redrive and partial batch failures apply from M3. | Pass |
| V. Everything as code, gated delivery | CDK for all resources; PR gates without credentials; diff and deploy after merge; canary with data-free pre-traffic self-check and version-scoped rollback alarms; front end uploaded after the canary, revertible by origin path; one dedicated account, dev and prod stacks (constitution 1.0.1). | Pass |
| VI. Security and privacy | One IAM role per function; OIDC trust pinned by `sub` per role; narrowed CDK bootstrap policy; actions pinned to SHAs; one secret (pepper) in Secrets Manager, retained; player id only as HMAC in logs and challenges; no event or input logging; no IP stored; edge size limit and rate limit with a JSON 429; `eu-central-2`, edge-only resources in `us-east-1`. | Pass |
| VII. Accessibility and performance | Keyboard play, relaxed switchable mid-play, text labels for squares, reduced motion; Lighthouse CI 1.0 x4; axe; first question in two round trips. | Pass |
| VIII. Cost ceiling | One USD 20 budget for the account with actual and forecast alerts, in the first deploy; metric dimensions capped and counted; WAF price verified in step 1. | Pass |
| Writing rules | English, straight hyphens; Starter rules FR-024a. | Pass |
| Review checklist | Constitution checklist on every PR; `AGENTS.md` in this feature. | Pass |

## Project Structure

### Documentation (this feature)

```text
specs/001-m1-web-app/
├── plan.md              # This file
├── research.md          # Phase 0: decisions R1-R17
├── data-model.md        # Phase 1: table design, entities, states
├── quickstart.md        # Phase 1: validation scenarios V1-V18
├── contracts/
│   ├── openapi.yaml           # public API
│   ├── question.schema.json   # authoring format (content repository)
│   └── schedule.schema.json   # daily schedule format (content repository)
├── checklists/requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks, not created here)
```

### Source Code (repository root)

```text
api/                               # Python 3.13, uv
├── src/staysharp/
│   ├── handlers/
│   │   ├── api.py                 # Powertools APIGatewayHttpResolver; also routes the selfcheck event
│   │   ├── pre_traffic_check.py   # invokes the new version's selfcheck, reports to CodeDeploy
│   │   └── stock_check.py         # daily, StockDaysAhead per level
│   ├── domain/                    # pure, no AWS imports
│   │   ├── grading.py             # grade + bonus
│   │   ├── views.py               # allowlist view builder (the only way a question leaves)
│   │   ├── calendar.py            # Zurich today, allowed dates, game number, ISO week
│   │   ├── cancellation.py        # R2 reason table -> outcome
│   │   └── models.py              # strict Pydantic models
│   ├── selfcheck/                 # bundled fixtures + checks, no table access
│   ├── store/                     # DynamoDB access, transactions, conditional writes
│   ├── publish/                   # validate + apply + fingerprints (used by the content repo)
│   ├── tools/                     # seed fixtures, leak scan, return-rate report
│   └── aws.py                     # clients with timeouts and retry config
├── testing/                       # fault-injection handler, packaged for dev only
└── tests/ { unit/, integration/, contract/ }

front/                             # React 19 + Vite + Tailwind v4, pnpm
├── src/
│   ├── api/                       # typed client generated from contracts/openapi.yaml
│   ├── progress/                  # streak, freeze, skill view, Leitner boxes (pure)
│   ├── views/                     # Home, Play, Result, Practice, Challenge, Privacy
│   ├── components/                # CodeBlock (line picker), Choices, Timer, ShareCard, Squares
│   └── storage.ts                 # versioned localStorage with safe fallback
├── public/fonts/                  # self-hosted subsets
└── tests/ { unit/, e2e/ }         # Vitest; Playwright + axe; lighthouserc.json

infra/                             # AWS CDK v2, Python
├── app.py                         # stages dev and prod in one account; cross_region_references
├── stacks/
│   ├── edge_stack.py              # us-east-1: ACM certificate, WAF (rate rule with JSON 429, size rule)
│   ├── data_stack.py              # DynamoDB table, pepper secret
│   ├── api_stack.py               # Lambdas, alias, CodeDeploy group, HTTP API, rollback alarms
│   ├── web_stack.py               # S3 (OAC, versioned prefixes), CloudFront (/api/* no cache, CF function), headers
│   ├── ops_stack.py               # SNS, paging alarms, stock schedule (per stage)
│   └── account_stack.py           # budget, OIDC provider and roles (once per account)
└── tests/                         # CDK assertion tests

content/samples/                   # sample + prototype questions (sample: true, daily_eligible: false)
docs/runbooks/                     # rollback, restore, fault drill, publish, pepper rotation
.github/workflows/                 # ci.yml (PR, no AWS), deploy.yml (main -> dev -> approval -> gate -> prod)
AGENTS.md
prototype/                         # M0, unchanged
```

**Structure Decision**: `api/`, `front/` and `infra/` at the root, each with its own toolchain and
tests; one shared contract in `specs/001-m1-web-app/contracts/`, copied by codegen into `api/`
and `front/`. Content and its publish CI live in the private `stay-sharp-content` repository,
which installs `api/` as a package to reuse `publish/` and `domain/views.py`.

## Delivery order (input for /speckit-tasks)

0. **Gate before anything is public or in prod** (W17): clean the history of the public
   repository, then make it public. Done 2026-11-03: see `docs/decisions/0001-public-history.md`.
1. **Account and edge prerequisites**: `stay-sharp` account in the Organization (done by the
   maintainer), region and WAF pricing checks (R9, R14), ACM certificate request and Infomaniak
   DNS records, CDK bootstrap with narrowed policies, OIDC roles, budget, SNS topic.
2. **Domain**: grading, views allowlist, calendar, cancellation table, models; unit tests,
   including the allowlist test and the R2 table.
3. **Data, API and a thin edge**: table, store, routes, contract and integration tests on
   DynamoDB Local (V3, V4, V13, V14, V15), plus a minimal CloudFront with the `/api/*` behaviour
   in dev so caching, headers and CSP are tested early (W16).
4. **Content**: schemas, publish validate/apply with all R4 checks, private repository and its CI,
   fingerprints, both leak-guard layers, fixtures for dev (V7, V2).
5. **Front end**: Play and Result (Story 1), relaxed, streak and share, challenge, practice,
   privacy page.
6. **Delivery**: WAF, deploy workflow, canary with pre-traffic self-check, front-end upload after
   canary, drills V8 and V9, runbooks.
7. **Quality gates and docs**: Lighthouse CI, axe, return-rate report, `AGENTS.md`, README.
8. **Content stock**: 140 questions (70 Senior, 70 Starter) written and reviewed, starting in
   parallel with step 2.

## Risks and open items

- **Region and pricing facts** (R9, R14): checked in step 1.
- **Cost margin** (R15): worst-case estimate is close to USD 20; first measured month decides
  whether dev metrics are cut.
- **Content volume**: 140 new questions is the longest task and is not code.
- **Starter audience**: second reader required by the schema; no personal data, so no consent
  flow in M1.
- **Public history**: step 0 gates it.

## Complexity Tracking

| Item | Why | Simpler alternative rejected because |
|---|---|---|
| Private content repository + fingerprint scan in the public repo | Principle II: answers must not be readable on GitHub, and FR-024b needs a check in the public CI | Encrypted files in the public repo: key handling, one mistake leaks everything |
| Pre-traffic self-check | A canary with almost no traffic proves nothing (R10) | Canary alarms alone; or a self-test set in prod data, which pollutes metrics and needs content every day |
| Size limit enforced in WAF and the Lambda, not in API Gateway | HTTP API has no request validation | REST API: higher cost for one feature |
