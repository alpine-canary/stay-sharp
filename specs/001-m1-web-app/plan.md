# Implementation Plan: M1 - public daily game without accounts

**Branch**: `001-m1-web-app` | **Date**: 2026-11-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-m1-web-app/spec.md`

## Summary

A public web game with two levels (Senior, Starter 12+), five questions a day, graded on the
server. The browser gets one question at a time, without its answer; the server records when it
sent the question, grades the answer once (conditional write in a DynamoDB transaction), adds a
speed bonus, and only then returns the answer and explanation. Streak, freeze, skill view and
practice boxes live in the browser in M1. Challenge links store anonymous result snapshots.
Questions live in a private content repository and are loaded by a validated, all-or-nothing
publish step. One API Lambda behind API Gateway and CloudFront, deployed with a CodeDeploy canary
whose pre-traffic check exercises grading on a hidden self-test set, and which rolls back on
error or scoring-failure alarms. Everything in CDK (Python), gated by GitHub Actions.

## Technical Context

**Language/Version**: Python 3.13 (API, tools, CDK); TypeScript 5 strict (front end)

**Primary Dependencies**: AWS Lambda Powertools for Python (event handler, logger, metrics,
parser), Pydantic v2, boto3; React 19, Vite, Tailwind CSS v4; AWS CDK v2

**Storage**: DynamoDB, one table, on-demand, PITR, TTL; S3 for static files; browser
`localStorage` for local progress

**Testing**: pytest (+ moto for units, DynamoDB Local for integration), CDK assertions; Vitest,
Testing Library; Playwright with axe-core; Lighthouse CI; schemathesis or a schema check against
`contracts/openapi.yaml`

**Target Platform**: AWS Lambda arm64 in `eu-central-2`; CloudFront; evergreen browsers, 390 px
and up

**Project Type**: web application (static front end + serverless API + infrastructure)

**Performance Goals**: first question usable within 2 s on a mid-range phone on 4G (SC-007);
answer round trip p95 under 500 ms warm; Lighthouse 100 x4

**Constraints**: no answer in the browser before submit; no personal data stored or logged; data
in Switzerland or EU; USD 20 a month budget; WCAG 2.2 AA; no hard time limit

**Scale/Scope**: hundreds to low thousands of players a day; 2 levels x 5 questions a day; 140
questions at launch; about 8 screens

## Constitution Check

*Initial gate: pass. Re-checked after Phase 1 design: pass.*

| Principle | How this plan complies | Status |
|---|---|---|
| I. Honesty | README "Numbers" stays "Not measured yet"; cost in research R15 is labelled an estimate; questions are written by a person with dated sources; prototype anecdote already removed. | Pass |
| II. Deterministic, server-side grading | Grading is a pure Python function of (question version, choice, line, elapsed, relaxed); one question sent at a time with a strict response schema; choice ids random and order shuffled at publish; no content in the static bundle; private content repo + leak guard (R1, R4); contract test, Playwright leak scan, SC-002 scan before each release. | Pass |
| III. Model proposes, person decides | No model in M1. All questions human-written and approved in the content repo; no Bedrock permission exists in any M1 role. | Pass (N/A in practice) |
| IV. Reliability first | Conditional writes in a transaction for every grade (R2); timeouts and limited retries on every AWS client (R8); every DynamoDB response checked (cancellation reasons inspected, not assumed); errors logged with ids and turned into 5xx plus a `ScoringFailures` metric. **No queues in M1**, so DLQ, maxReceiveCount, redrive and partial batch failures have nothing to apply to; they become mandatory in M3. The two async invocations (EventBridge to `stock_check`, CodeDeploy to `pre_traffic_check`) get an on-failure destination and an alarm. | Pass |
| V. Everything as code, gated delivery | CDK Python for all resources; CI gates lint, types, tests, CDK assertions, synth and diff; prod through CodeDeploy canary with alarms and a pre-traffic check; dev and prod accounts in an Organization (R10, R13). | Pass |
| VI. Security and privacy | One IAM role per function, scoped to the table and needed actions (publish role limited by `LeadingKeys` to `Q#`, `DAILY#`, `POOL#`, `STOCK#`); no secrets needed in M1 (the challenge pepper is a generated SSM SecureString, never in code); no IP or player id in logs (player id hashed); region `eu-central-2`, edge-only resources in `us-east-1` hold no game data; fonts self-hosted; input validated by Pydantic with size limit; WAF and throttling (R9). Delete-my-account: not applicable without accounts; data expires after 90 days. | Pass |
| VII. Accessibility and performance | Keyboard play, relaxed mode, text labels for squares, reduced motion; Lighthouse CI asserting 1.0 x4 on mobile and desktop; axe in Playwright (R12). | Pass |
| VIII. Cost ceiling | Budget USD 20 with actual and forecast alerts created in the first infra deploy; on-demand everything; reserved concurrency caps a flood; WAF cost decided before first deploy (R9). | Pass |
| Writing rules | English only, straight hyphens; Starter content rules in FR-024a. | Pass |
| Review checklist | Each pull request uses the constitution checklist; `AGENTS.md` added in this feature. | Pass |

## Project Structure

### Documentation (this feature)

```text
specs/001-m1-web-app/
├── plan.md              # This file
├── research.md          # Phase 0: decisions R1-R15
├── data-model.md        # Phase 1: table design, entities, states
├── quickstart.md        # Phase 1: validation scenarios V1-V12
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
│   ├── handlers/                  # thin Lambda entry points
│   │   ├── api.py                 # Powertools APIGatewayHttpResolver, routes from openapi.yaml
│   │   ├── pre_traffic_check.py   # CodeDeploy BeforeAllowTraffic hook
│   │   └── stock_check.py         # daily schedule, StockDaysAhead metric
│   ├── domain/                    # pure, no AWS imports
│   │   ├── grading.py             # grade + bonus, deterministic
│   │   ├── calendar.py            # Zurich today, allowed dates, game number, ISO week
│   │   └── models.py              # Pydantic request/response models (strict)
│   ├── store/                     # DynamoDB access, one module per entity, conditional writes
│   ├── publish/                   # validate + apply, used by the content repository CI
│   ├── tools/                     # seed (samples, selftest), leak_scan
│   └── aws.py                     # boto3 clients with timeouts and retry config
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
├── app.py                         # stages dev and prod, env from cdk.json context
├── stacks/
│   ├── edge_stack.py              # us-east-1: ACM certificate, WAF web ACL
│   ├── data_stack.py              # DynamoDB table
│   ├── api_stack.py               # Lambdas, alias, CodeDeploy group, HTTP API, alarms
│   ├── web_stack.py               # S3 (private, OAC), CloudFront, response headers (CSP)
│   └── ops_stack.py               # SNS topic, budget, stock_check schedule, dashboard
└── tests/                         # CDK assertion tests

content/samples/                   # sample questions only (sample: true) + prototype days
docs/                              # spec.md, runbooks/ (rollback, fault drill, publish)
.github/workflows/                 # ci.yml (PR), deploy.yml (main -> dev -> approval -> prod)
AGENTS.md                          # agent roles, limits, review rule
prototype/                         # M0, unchanged
```

**Structure Decision**: web application split into `api/`, `front/` and `infra/` at the
repository root, each with its own toolchain and tests; one shared contract in
`specs/001-m1-web-app/contracts/` (copied to `api/` and `front/` by a codegen step so both sides
build from the same file). Content and its publish CI live in the private `stay-sharp-content`
repository, which installs `api/` as a package to reuse `publish/`.

## Delivery order (input for /speckit-tasks)

1. Accounts, OIDC roles, budget and SNS topic (ops first, so cost and alarms exist before
   anything else) and the region check from research R14.
2. Domain: grading, calendar, models, with unit tests (no AWS).
3. Data and API: table, store with conditional writes, routes, contract and integration tests,
   idempotency and timing tests (V3, V4).
4. Content: schema, publish validate/apply, private repository, leak guard, selftest set (V7).
5. Front end: Play and Result first (Story 1), then streak and share, challenge, practice, privacy.
6. Delivery: CloudFront, WAF, CI, deploy workflow, canary with pre-traffic check, drills V8 and V9.
7. Quality gates: Lighthouse CI, axe, leak scan (V2, V10), runbooks, AGENTS.md, README.

## Risks and open items

- **Region and pricing facts not yet verified** (R9, R14): checked before the first deploy, not
  assumed.
- **Content volume**: 140 new questions before launch is the longest task, and it is not code. It
  runs in parallel from day one.
- **Children's audience (Starter)**: content review against FR-024a by a second reader before
  publish is recommended; no personal data means no consent flow in M1.
- **History of the public repository**: earlier commits on `main` hold private wording; the
  maintainer decides how to clean it before the repository is made public (outside this plan).

## Complexity Tracking

No violations. The one point worth recording:

| Item | Why | Simpler alternative rejected because |
|---|---|---|
| Private content repository next to the public one | Principle II: answers must not be readable on GitHub | Encrypted files in the public repo: key handling, and one mistake leaks all future answers |
| Pre-traffic check Lambda | A canary with no traffic proves nothing (R10) | Canary alarms alone: may pass with zero requests |
