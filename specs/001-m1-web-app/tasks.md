---
description: "Task list for M1 - public daily game without accounts"
---

# Tasks: M1 - public daily game without accounts

**Input**: Design documents from `specs/001-m1-web-app/` (plan.md, spec.md, research.md,
data-model.md, contracts/, quickstart.md) and `.specify/memory/constitution.md` (v1.0.1).

**Tests**: Required. The spec's acceptance criteria are automated checks (SC-002 to SC-006) and
the constitution requires tests for the failure case (review checklist item 11). Within each
story, tests are written first and must fail before the code that makes them pass.

**Organization**: by user story, after the shared setup and foundation. Story labels match
spec.md: US1 daily (P1), US6 safe changes and alarms (P1), US7 publish (P2), US2 streak (P2),
US3 share (P2), US4 challenge (P3), US5 practice (P3).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: the user story the task belongs to (US1 to US7)
- Paths are from the repository root; "content repo" means the private `stay-sharp-content`
  repository (R4), which is never cloned into this one.

## Rules that apply to every task

- No question for today or a future day ever enters this repository (FR-024b). Fixtures and
  samples only: `content/samples/` and `api/src/staysharp/selfcheck/fixtures/`.
- No account id, portal URL or e-mail address in committed files; CDK reads the account from the
  SSO profile (R14).
- No real Bedrock call; no Bedrock permission in any role (Principle III).
- Every boto3 client comes from `api/src/staysharp/aws.py` (timeouts and retries, R8).
- Logs never contain the raw player id, IP, headers or input values (R3, R8, R11).
- English, straight hyphens only, in code, comments, UI text and docs.

---

## Phase 1: Setup (shared infrastructure)

**Purpose**: the three toolchains, local tooling and the pull-request CI, with no AWS access.

- [x] T001 Clean the public history before anything is public (plan step 0, W17): single clean root commit, old history kept only in a local bundle outside the repository; record the decision and method in `docs/decisions/0001-public-history.md`
- [x] T002 Create the source layout from plan.md (`api/`, `front/`, `infra/`, `content/samples/`, `docs/runbooks/`, `.github/workflows/`) with a `.gitignore` covering `node_modules/`, `.venv/`, `cdk.out/`, `dist/`, `*.bundle`, `.specify/feature.json`
- [x] T003 [P] Initialise the API package with uv in `api/pyproject.toml` (Python 3.13; deps `aws-lambda-powertools[parser]`, `pydantic>=2`, `boto3`; dev deps `pytest`, `pytest-cov`, `ruff`, `mypy`, `boto3-stubs[dynamodb,lambda,codedeploy,ssm,secretsmanager,cloudwatch]`, `openapi-core`), src layout `api/src/staysharp/__init__.py`
- [x] T004 [P] Initialise the front end with pnpm in `front/package.json`: React 19, Vite, Tailwind CSS v4 (`@tailwindcss/vite`), TypeScript 5 strict (`front/tsconfig.json` with `strict`, `noUncheckedIndexedAccess`), Vitest, Testing Library, Playwright, `@axe-core/playwright`, `@lhci/cli`, eslint with `jsx-a11y`
- [x] T005 [P] Initialise the CDK app with uv in `infra/pyproject.toml` (`aws-cdk-lib` v2, `constructs`, pytest) and `infra/cdk.json`; commit `infra/cdk.context.json` empty so `cdk synth --no-lookups` works without credentials
- [x] T006 [P] Configure ruff (rules E, F, I, B, UP, S, SIM) and mypy strict for `api/` and `infra/` in their `pyproject.toml` files
- [x] T007 [P] Add `docker-compose.yml` at the root with DynamoDB Local on port 8000 (`amazon/dynamodb-local`, `-inMemory -sharedDb`)
- [x] T008 [P] Add `Makefile` targets: `lint`, `test`, `test-integration`, `synth`, `fault-drill STAGE=dev`, `canary-drill STAGE=dev CANARY=...` (drill targets refuse `STAGE=prod`)
- [x] T009 [P] Add the contract codegen: `front/scripts/gen-api.mjs` builds `front/src/api/schema.ts` from `specs/001-m1-web-app/contracts/openapi.yaml` (openapi-typescript), and `api/scripts/gen_models.py` checks that Pydantic models in `api/src/staysharp/domain/models.py` match the contract (fails CI on drift)
- [x] T010 Write the pull-request workflow `.github/workflows/ci.yml`: no AWS credentials in any job except `cdk-diff`, `permissions: contents: read`, every action pinned to a commit SHA; jobs ruff, mypy, pytest (unit + integration with DynamoDB Local service), eslint, `tsc --noEmit`, vitest, CDK assertion tests, `cdk synth --no-lookups`; a `cdk-diff` job that runs only for pull requests from branches of this repository (never forks, which get no OIDC token), assumes the read-only diff role of T018, runs `cdk diff` against dev and prod, and posts no diff text to the pull request (constitution V); no artefact upload
- [x] T011 [P] Write `AGENTS.md` at the root: agent roles, what agents may not do (push, deploy prod, real Bedrock calls, touch the content repo), the 12-point review checklist from the constitution, and the content rules above

**Checkpoint**: `make lint test synth` passes locally on empty packages; CI is green on a pull request.

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: account prerequisites, the pure domain, storage, the API skeleton and a thin edge in
dev. No user story can start before this phase ends.

### Account and edge prerequisites (plan step 1; maintainer actions marked "maintainer")

- [x] T012 Create the `stay-sharp` member account in the Organization, Identity Center access with a 4-hour admin set, MFA on, local SSO profile `stay-sharp` (maintainer, done 2026-11-03)
- [x] T013 Enable the opt-in region `eu-central-2` in the account (done 2026-11-03, R14)
- [x] T014 Write `docs/runbooks/account-setup.md`: enable `eu-central-2` first, SSO profile, CDK bootstrap with narrowed execution policies, DNS records at Infomaniak, root user without daily use; no ids or URLs in the file
- [ ] T015 Verify in the account and record in `specs/001-m1-web-app/research.md` R9 and R14: `python3.13` arm64 runtime and HTTP API available in `eu-central-2`; whether the CloudFront flat-rate Free plan covers the WAF rules of R9, else standard WAF cost
- [ ] T016 Bootstrap CDK in `eu-central-2` and `us-east-1` with `--cloudformation-execution-policies` limited to the services in plan.md (no `AdministratorAccess`); commit the policy document as `infra/bootstrap/execution-policy.json` (maintainer runs the command)
- [ ] T017 Request the ACM certificate for `stay-sharp.lumineth.com` in `us-east-1` from `infra/stacks/edge_stack.py` (DNS validation) and give the maintainer the validation CNAME to add at Infomaniak (maintainer action, W16)
- [ ] T018 [P] Implement `infra/stacks/account_stack.py` (deployed once per account): AWS Budget USD 20 actual and USD 16 forecast to the SNS topic (FR-031, R11), GitHub OIDC provider, four roles with exact `sub` conditions (read-only diff on `repo:<owner>/stay-sharp:pull_request`, limited to `cloudformation:Describe*`, `cloudformation:GetTemplate*` and assuming the CDK lookup role, no write action; dev deploy on `refs/heads/main`, prod deploy on `environment:production`, content publish on `stay-sharp-content` `refs/heads/main` limited to `Q#`, `DAILY#`, `POOL#`, `STOCK#` keys, the `leak-guard/last-pass` SSM parameter and the fingerprint object) (R13)
- [ ] T019 [P] Implement `infra/stacks/ops_stack.py` per stage: SNS topic with the maintainer e-mail read from an SSM parameter (not committed), one helper to create alarms with explicit `treatMissingData`
- [ ] T020 [P] CDK assertion tests in `infra/tests/test_account_stack.py`: one budget with actual and forecast notifications (V12), OIDC `sub` conditions exact, no Bedrock action in any policy, the diff role has no write action

### Domain (pure Python, no AWS imports) - tests first

- [x] T021 [P] Unit tests for `calendar` in `api/tests/unit/test_calendar.py`: Zurich today across DST changes, game number from launch day, ISO week Monday to Sunday, allowed dates (`daily` start only today; `open` and `answer` accept the play's date or the day after; future always refused) (R6, W2)
- [x] T022 [P] Unit tests for `grading` in `api/tests/unit/test_grading.py`: grades 1, 0.5 (Spot the bug: line or problem right, not both), 0; bonus 0.2 only for grade 1, not relaxed, `elapsedMs <= target`; total at most 6.0; same input always same output (FR-004, FR-005, FR-005b, V4)
- [x] T023 [P] Unit tests for `views` in `api/tests/unit/test_views.py`: given a full question item with every answer and authoring field, the output has exactly `index, deck, prompt, code, language, choices, targetSeconds, servedAt` (contract `QuestionView`; the qid is only returned by practice, next to the view) and no `answerChoiceId`, `answerLines`, `explanation`, `sourceUrl`, `sourceDate`, `approvedBy`, `secondReader`, `changeReason` (R1, S2, V2)
- [x] T024 [P] Unit tests for `cancellation` in `api/tests/unit/test_cancellation.py`: every row of the R2 table (duplicate, conflict 409 with stored result, not opened 400, challenge full, temporary/unknown -> retry then 503) and that a temporary error is never classified as a duplicate
- [x] T025 [P] Implement strict Pydantic models in `api/src/staysharp/domain/models.py` (`extra="forbid"`): `Level` (`senior`, `starter`), `Deck` (senior `spot`, `better`, `fail`, `acronym`, `news`; starter `logic`, `readcode`, `whatif`, `words`, `aisense`), `Question` with `qid` matching `^[a-z0-9_]{3,64}$`, `version` int from 1, exactly 4 `choices` `{id, text}` with 8-character base32 ids, `DailySet` with `items[5]` `{index, deck, qid, version, targetSeconds}`, request bodies with `X-Player-Id` UUIDv4, and response models matching `contracts/openapi.yaml`
- [x] T026 [P] Implement `api/src/staysharp/domain/calendar.py` to pass T021
- [x] T027 [P] Implement `api/src/staysharp/domain/grading.py` to pass T022; `SuspiciouslyFast` threshold 3 s, 5 s for `spot` and `logic` (FR-005d), returned as a flag, not applied to the grade
- [x] T028 [P] Implement `api/src/staysharp/domain/views.py` (the only way a question leaves the server) to pass T023
- [x] T029 [P] Implement `api/src/staysharp/domain/cancellation.py` to pass T024

### Storage and AWS access

- [x] T030 Implement `api/src/staysharp/aws.py`: one factory for boto3 clients with `connect_timeout=2`, `read_timeout=3`, retry mode `standard`, `total_max_attempts=3` (3 calls in total; botocore reads `max_attempts=3` as 3 retries), endpoint override for DynamoDB Local in tests (R8)
- [x] T031 Spike in `api/tests/integration/test_dynamodb_local_cancellation.py`: check that DynamoDB Local returns the `ALL_OLD` item inside `CancellationReasons` for `TransactWriteItems`; if not, mark the affected tests to run against the dev table and note it in research.md R2 (W15)
- [ ] T032 Implement `infra/stacks/data_stack.py`: table `staysharp-<stage>` with string `PK`/`SK`, on-demand, PITR on, deletion protection on in prod, TTL attribute `expiresAt`; pepper secret with `generate_secret_string` and `RemovalPolicy.RETAIN` (R16)
- [ ] T033 [P] CDK assertion tests in `infra/tests/test_data_stack.py`: PITR and TTL on, deletion protection in prod, secret retained (V11)
- [x] T034 Implement the store base in `api/src/staysharp/store/table.py`: key builders for every access pattern A1 to A8 of data-model.md, response checks (unexpected shapes raise), `expiresAt` compared with now on every read that depends on expiry
- [x] T035 Implement `api/src/staysharp/store/questions.py`: read daily set (A1) and a question version (A2); a missing set returns a typed "not ready" result, never an exception to the client (Story 7, scenario 2)
- [x] T036 Implement `api/src/staysharp/tools/seed.py` (`python -m staysharp.tools.seed --fixtures`): load `content/samples/` and test fixtures into DynamoDB Local or the dev table only; refuse `STAGE=prod`
- [x] T037 [P] Add sample questions in `content/samples/` (one per deck for both levels, `sample: true`, `daily_eligible: false`, valid against `contracts/question.schema.json`) and the 14 prototype days converted to the same format with `daily_eligible: false` (FR-024c)

### API skeleton, observability and secrets

- [x] T038 Implement `api/src/staysharp/handlers/api.py`: Powertools `APIGatewayHttpResolver` under `/api/v1`, Logger with `POWERTOOLS_LOGGER_LOG_EVENT=false`, Metrics (namespace `StaySharp`, dimension `Stage`), `X-Player-Id` UUIDv4 check, body size refused over 2 KB, validation errors logged as field names and error types only, `Cache-Control: no-store` on every response, JSON error bodies `{code, message}`; route the synthetic `selfcheck` event to the self-check (R8, R10)
- [x] T039 Implement `api/src/staysharp/obs.py`: `player_hash = HMAC-SHA256(pepper, playerId)` with the pepper read once at cold start from Secrets Manager and cached; helpers that log with `request_id`, `question_id`, `player_hash` only (R3, R16)
- [x] T040 Implement `GET /health` and `GET /today` in `api/src/staysharp/handlers/routes_today.py` (server date in Europe/Zurich, game number, levels with a set) per `contracts/openapi.yaml`
- [x] T041 [P] Contract test harness in `api/tests/contract/conftest.py` and `api/tests/contract/test_today.py`: every response validated against `contracts/openapi.yaml`, unknown fields fail
- [x] T042 Implement `api/src/staysharp/local.py` (`python -m staysharp.local`): run the resolver on port 3001 against DynamoDB Local for front-end work

### Thin edge in dev (W16) and front-end shell

- [ ] T043 Implement `infra/stacks/api_stack.py` (first version): API Lambda Python 3.13 arm64, 512 MB, timeout 10 s, reserved concurrency 20, one role with least privilege on the stage table and secret; alias `live`; HTTP API with throttling burst 50, rate 20/s; access logs without `sourceIp`; log retention 30 days
- [ ] T044 Implement `infra/stacks/web_stack.py` (first version): S3 bucket private with OAC, site under `site/<commit>/` with the distribution origin path pointing to it; behaviour `/api/*` with `CachePolicy.CACHING_DISABLED` and an origin request policy forwarding only `X-Player-Id` and `Content-Type`; strict CSP and security headers response policy; CloudFront Function rewriting `/c/<id>` to `/c/index.html`, real 404 page otherwise (R8, R12, W18)
- [ ] T045 Implement `infra/app.py`: stages `dev` and `prod` in one account with `staysharp-<stage>-*` names, edge stack in `us-east-1` deployed first, `cross_region_references=True`
- [ ] T046 [P] CDK assertion tests in `infra/tests/test_web_stack.py` and `infra/tests/test_api_stack.py`: `/api/*` caching disabled and only the two headers forwarded, no public bucket, log retention 30 days, `POWERTOOLS_LOGGER_LOG_EVENT=false`, one role per function, no `sourceIp` in access logs (V11)
- [ ] T047 [P] Implement `front/src/storage.ts`: versioned `localStorage` key `staysharp.v1` with the shape of data-model.md "Local progress", safe fallback when storage is blocked, broken data reset with a visible message, never a crash; player id UUIDv4 created on first visit
- [ ] T048 [P] Implement `front/src/api/client.ts` on the generated schema: `X-Player-Id` on every call, timeout, one retry for network errors on idempotent calls, typed errors; a plain message with a retry button when the service is down (Edge Cases)
- [ ] T049 [P] Front-end shell in `front/src/main.tsx`, `front/src/App.tsx` and `front/index.html`: no router library, views switched by path, self-hosted subset fonts in `front/public/fonts/`, `/api/v1/today` prefetched from the HTML (SC-007, W7), level choice Senior or Starter (12+) remembered in storage (FR-010)
- [ ] T050 Deploy dev from a maintainer machine once (`cdk deploy` with the SSO profile) and check `/api/v1/health` through CloudFront returns `no-store` and is never cached

**Checkpoint**: domain tests pass, `/today` works locally and in dev behind CloudFront, the front-end shell loads.

---

## Phase 3: User Story 1 - Play today's daily set (P1) - MVP

**Goal**: a player picks a level and plays today's five questions, graded on the server, with the
answer and explanation after each, a speed bonus, relaxed mode, resume, and replay not scored.

**Independent test**: on a fresh browser, play the five questions of the day with fixture content
in dev; each answer is graded and explained, the result matches the answers, and nothing in the
browser before an answer contains the correct id, explanation or source (V1, V2, V3, V4, V13).

### Tests for User Story 1 (write first, must fail)

- [ ] T051 [P] [US1] Integration tests in `api/tests/integration/test_idempotency.py` on DynamoDB Local: 2, 10 and 50 identical submissions, sequential and concurrent, give one grade, unchanged score, `duplicate: true` after the first; a different answer gets `409` with the stored result (FR-006, SC-003, V3)
- [ ] T052 [P] [US1] Integration tests in `api/tests/integration/test_timing.py`: bonus only for grade 1 within target and not relaxed; relaxed switched on mid-play stops bonuses from that question on; re-opening a question does not reset `servedAt` (FR-005a to FR-005c, V4)
- [ ] T053 [P] [US1] Integration tests in `api/tests/integration/test_replay.py`: `mode=replay` for today returns `409` before the daily of that date and level is finished, and is allowed and unscored after (C3, V13)
- [ ] T054 [P] [US1] Integration tests in `api/tests/integration/test_failures.py`: throttled or timed-out transaction is retried up to 3 times with backoff and jitter, then `503`, `ScoringFailures` +1, no partial write, never `duplicate` (R2, V15)
- [ ] T055 [P] [US1] Integration tests in `api/tests/integration/test_validation.py`: answer for a question not in the set, a future date, an unopened question, an out-of-range choice, a line outside the served version's line count, a body over 2 KB, a malformed `X-Player-Id`: each rejected with a clear code and nothing stored (FR-032, Edge Cases)
- [ ] T056 [P] [US1] Contract tests in `api/tests/contract/test_plays.py` for `/plays`, `/plays/{playId}`, `/plays/{playId}/relaxed`, `.../open`, `.../answer` against `contracts/openapi.yaml`, including the `409` and `503` bodies
- [ ] T057 [P] [US1] Playwright tests in `front/tests/e2e/daily.spec.ts`: full daily by keyboard only; grade, correct answer and explanation after each; reload mid-play resumes at the first unanswered question; finished daily shows the recorded result (V1)
- [ ] T058 [P] [US1] Playwright test in `front/tests/e2e/leak.spec.ts`: before each answer, page source, scripts, network responses, storage and Cache Storage contain no correct choice id marked, explanation or source text (FR-003, SC-002, V2)
- [ ] T059 [P] [US1] Playwright test in `front/tests/e2e/midnight.spec.ts` with a mocked server clock: a play started 23:58 and finished 00:03 counts for its start date; the new day's set is a separate play (W2, V16)

### Implementation for User Story 1

- [ ] T060 [US1] Implement `api/src/staysharp/store/plays.py`: start or resume a play (`playId = <date>.<level>.<mode>`, `expiresAt` = start + 90 days, idempotent for the same player, date, level and mode); refuse `replay` for today until the daily is finished (C3); relaxed one-way (`relaxed` false -> true, `relaxedFrom` = index of the first relaxed question)
- [ ] T061 [US1] Implement `api/src/staysharp/store/answers.py`: `open` writes the answer item with `servedAt` via `if_not_exists` and copies `qid`, `version` from the daily set; `answer` runs the R2 `TransactWriteItems` (item 1 condition `attribute_exists(servedAt) AND attribute_not_exists(grade)` with `ReturnValuesOnConditionCheckFailure=ALL_OLD`; item 2 purely additive `ADD score, bonus, elapsedMs, answered` and `SET grades.#i`; item 3 only on the fifth answer, added in US4; the answer item's `expiresAt` = the play's `expiresAt`, same base time, W1) and maps cancellations through `domain/cancellation.py`
- [ ] T062 [US1] Implement the play routes in `api/src/staysharp/handlers/routes_plays.py`: `POST /plays` returns the first question (two round trips at most, SC-007), `GET /plays/{playId}`, `POST /plays/{playId}/relaxed`, `POST .../questions/{index}/open`, `POST .../questions/{index}/answer` returning grade, bonus, correct answer, explanation and for `news` the source date and link (FR-007); date rules from `domain/calendar.py`; "Today's set is not ready yet" as a typed response
- [ ] T063 [US1] Emit metrics in the play routes: `PlaysStarted`, `PlaysFinished`, `PlayDurationMs`, `AnswersGraded`, `DuplicateAnswers`, `SuspiciouslyFast` (dimension `Deck` only), `ScoringFailures` (dimension `FunctionVersion` from `context.function_version`), all through one helper in `api/src/staysharp/metrics.py` that only accepts the metric and dimension pairs of R11 (unit test `api/tests/unit/test_metrics.py` fails on any other pair), with every scoring failure logged with `question_id` and `request_id` (FR-028, R11)
- [ ] T064 [P] [US1] Implement `front/src/components/CodeBlock.tsx`: code with line numbers, line picker by keyboard (arrow keys, Enter), scrolls inside its box at 390 px, page never scrolls sideways
- [ ] T065 [P] [US1] Implement `front/src/components/Choices.tsx`: four choices as a radio group, visible focus, submit by keyboard, disabled while submitting so a double click sends one request
- [ ] T066 [P] [US1] Implement `front/src/components/Timer.tsx`: shows time used against the target from the server's `servedAt`, hidden in relaxed mode, no motion when `prefers-reduced-motion`, not announced every second to screen readers
- [ ] T067 [P] [US1] Implement `front/src/components/Squares.tsx`: one square per question with a distinct symbol and a text label per question (no information by colour alone, FR-033)
- [ ] T068 [US1] Implement `front/src/views/Play.tsx`: open, answer, feedback (right, half right, wrong; correct answer; explanation; source date and link for `news`), next; relaxed switch reachable before and during a play with a one-way confirmation; resume at the first unanswered question; retry on network failure without double counting
- [ ] T069 [US1] Implement `front/src/views/Result.tsx`: squares, score out of 5, speed bonus or "relaxed", time taken; replay entry marked "not scored"
- [ ] T070 [US1] Implement `front/src/views/Home.tsx`: level choice, today's game number from `/today`, play or see today's result, "Today's set is not ready yet" state, service-down state with retry
- [ ] T071 [US1] Wire play routes into `infra/stacks/api_stack.py` and check in dev with fixtures: `uv run --directory api pytest tests/integration` and `pnpm --dir front test:e2e --grep "daily|leak|midnight"` against dev

**Checkpoint**: US1 works end to end in dev with fixture content; V1, V2 (API and E2E parts), V3, V4, V13, V15 and V16 pass.

---

## Phase 4: User Story 6 - Safe changes and alarms for the maintainer (P1)

**Goal**: scoring failures page the maintainer within 5 minutes; a bad version is stopped before
traffic or rolled back by itself; nothing reaches prod without the gates.

**Independent test**: in dev, inject a scoring failure and check the alert (V8); deploy a version
that fails its self-check and one that fails under traffic, and check both roll back with no
human action (V9).

### Tests for User Story 6 (write first, must fail)

- [ ] T072 [P] [US6] Unit tests in `api/tests/unit/test_selfcheck.py`: the self-check grades the bundled fixtures, checks the view allowlist and the R2 classification table with a stubbed DynamoDB client, touches no table, and returns failure when any check fails
- [ ] T073 [P] [US6] Unit tests in `api/tests/unit/test_pre_traffic_check.py`: invokes only the qualified ARN from its environment, reports `Succeeded` or `Failed` to CodeDeploy, reports `Failed` on timeout or an unreadable response, never swallows an error
- [ ] T074 [P] [US6] CDK assertion tests in `infra/tests/test_delivery.py`: deployment config `LambdaCanary10Percent5Minutes` in prod and `AllAtOnce` in dev; rollback alarms with the R10 dimensions (`Resource=<fn>:live`, `ExecutedVersion`, `FunctionVersion`), period 60 s, 1 of 1, `notBreaching`; paging alarm not attached to CodeDeploy; prod asset contains no fault-injection file; pre-traffic role can invoke only the new version (V11)

### Implementation for User Story 6

- [ ] T075 [P] [US6] Implement `api/src/staysharp/selfcheck/__init__.py` and fixtures in `api/src/staysharp/selfcheck/fixtures/` (fixture questions only, no content from the content repo), emitting only `SelfCheckFailures` (C5)
- [ ] T076 [P] [US6] Implement `api/src/staysharp/handlers/pre_traffic_check.py` to pass T073 (R10)
- [ ] T077 [P] [US6] Implement the fault-injection handler in `api/testing/fault_injection.py`, packaged only in the dev build and refused at runtime when `STAGE=prod` (W11)
- [ ] T078 [US6] Extend `infra/stacks/api_stack.py`: version and alias `live`, CodeDeploy deployment group with the stage config, pre-traffic hook function with the new version's qualified ARN, the three rollback alarms of R10 (each also with an SNS alarm action), a CodeDeploy trigger on `DeploymentFailure` and `DeploymentRollback` to the SNS topic (Story 6 scenario 2), async invoke with on-failure destination to SNS and an error alarm for `pre_traffic_check`
- [ ] T079 [US6] Extend `infra/stacks/ops_stack.py` with the paging and health alarms of R11: paging `ScoringFailures` >= 1 in 5 minutes summed over versions; API 5xx; Lambda errors and throttles; CloudFront 5xx rate; `SelfCheckFailures`; dev fault injection left on more than 30 minutes
- [ ] T080 [US6] Write the deploy workflow `.github/workflows/deploy.yml`: on push to `main`, OIDC dev role, `cdk diff` and deploy dev, integration tests, Playwright, Lighthouse CI and the end-to-end leak scan against dev; manual approval through the GitHub environment `production`; the SC-002a gate (refuse when SSM `leak-guard/last-pass` is older than 24 hours or the public fingerprint scan of the release commit failed); `cdk diff` and prod deploy with the canary; front-end upload to `site/<commit>/` and origin path switch only after the canary completed (W6); actions pinned to SHAs, read-only default token
- [ ] T081 [US6] Implement the fault drill `api/tests/drills/fault_drill.py` behind `make fault-drill STAGE=dev`: turn on injection, send one answer, wait for the alarm state and the SNS e-mail within 5 minutes, check the log line has `question_id`, `request_id`, `player_hash` and no IP or raw id, restore dev in a `finally` step (V8, SC-004)
- [ ] T082 [US6] Implement the canary drill `api/tests/drills/canary_drill.py` behind `make canary-drill STAGE=dev CANARY=LambdaCanary10Percent5Minutes`: (a) deploy a version whose self-check fails and check it is stopped before traffic; (b) deploy a version that fails under traffic and check the version-scoped alarms roll it back; both with `live` on the previous version within 15 minutes and the e-mail received (V9, SC-005)
- [ ] T083 [P] [US6] Write `docs/runbooks/rollback.md` (including the case after 100 % when CodeDeploy no longer rolls back, and the front-end revert by origin path) and `docs/runbooks/fault-drill.md`
- [ ] T084 [US6] Protect `main` on GitHub: required checks from `ci.yml`, pull request required, no force push (maintainer action, FR-030)

**Checkpoint**: V8 and V9 pass in dev; the deploy workflow reaches the approval step.

---

## Phase 5: User Story 7 - Publish questions (P2)

**Goal**: the maintainer publishes approved questions and schedules from the private content
repository; invalid batches are refused whole; future answers never reach the public repository.

**Independent test**: run `publish validate` on fixtures with one invalid entry of each kind and
check each is refused with its id and reason and nothing is written (V7); run both leak-guard
layers (V2 content part, V18).

### Tests for User Story 7 (write first, must fail)

- [ ] T085 [P] [US7] Unit tests in `api/tests/unit/test_publish_validate.py` with fixtures in `api/tests/fixtures/publish/invalid/` and `.../valid/`: wrong deck order, wrong level, qid on two dates, sample or `daily_eligible: false` qid in a schedule, line outside code, missing target, Starter without `second_reader`, new version without `change_reason`, question with `status: draft` (FR-025), date-like pattern in an id, missing answer, duplicate id, wrong number of choices; each refused with id and reason (V7, FR-024)
- [ ] T086 [P] [US7] Integration tests in `api/tests/integration/test_publish_apply.py`: all-or-nothing batches in transactions of at most 100 items; edits write `V#<n+1>` and never change stored grades (FR-027); refusal to change today or a past day; choice ids assigned at first publish and kept; correct positions roughly uniform across a batch (S7)
- [ ] T087 [P] [US7] Unit tests in `api/tests/unit/test_fingerprints.py`: normalised 12-word shingles, HMAC with a test key, a file copying a future prompt is matched, a harmless file is not, output shows only paths and counts

### Implementation for User Story 7

- [ ] T088 [US7] Implement `api/src/staysharp/publish/validate.py` against `contracts/question.schema.json` and `contracts/schedule.schema.json` plus every R4 check
- [ ] T089 [US7] Implement `api/src/staysharp/publish/apply.py`: writes `Q#`, `DAILY#`, `POOL#` and `STOCK#` items, target times copied into each daily set, version history, all-or-nothing
- [ ] T090 [US7] Implement `api/src/staysharp/publish/fingerprints.py` and the CLI `api/src/staysharp/tools/leak_scan.py` (scan tracked files and full git history, print paths and match counts only)
- [ ] T091 [US7] Add the public leak-guard job to `.github/workflows/ci.yml`: download the fingerprint object, run `leak_scan` with the Actions secret key; skipped on fork pull requests and run again on merge (R4 layer 2, V18)
- [ ] T092 [US7] Implement `api/src/staysharp/handlers/stock_check.py` (daily schedule): `StockDaysAhead` per level counting days strictly after today; in `infra/stacks/ops_stack.py` its own role (read `STOCK#` keys only), an on-failure destination to SNS (R8), the schedule, the alarm `StockDaysAhead < 7` with `treatMissingData=breaching`, an error alarm and an `Invocations < 1` per day alarm (FR-026, W8)
- [ ] T093 [US7] Create the private `stay-sharp-content` repository (maintainer action) with: `pyproject.toml` installing `api/` as a package, the question and schedule folders, a `fixtures/` folder, and its CI running `publish validate` on every push, the offline leak check over today + 7 days (writes `leak-guard/last-pass` on success, prints counts only) and `publish apply --stage prod` on `main`, through the content OIDC role (R4 layer 1, SC-002)
- [ ] T094 [P] [US7] Write `docs/runbooks/publish.md`: write, approve (second reader for Starter), schedule, publish; when a question may be copied to the public repository (after its day); the stock warning

**Checkpoint**: V7 passes, V18 fails a branch that copies a future prompt, the content repo publishes fixtures to dev.

---

## Phase 6: User Story 2 - Streak, freeze and skill view (P2)

**Goal**: streak, longest streak, freeze and per-deck skill view on the home screen, computed in
the browser from the local log, per level.

**Independent test**: run the day-sequence table and check every figure (V5).

- [ ] T095 [P] [US2] Table-driven tests in `front/src/progress/progress.test.ts`: freeze earned on the 5th finished daily of an ISO week (at most one held), used for one missed day (shown "frozen"), two missed days reset to 1, longest kept, DST weeks, a play finished after midnight counts for its own date, `duplicate: true` changes no count or box, per-level separation (FR-012 to FR-015, R7, W13, V5)
- [ ] T096 [US2] Implement `front/src/progress/streak.ts` and `front/src/progress/skills.ts` (pure functions) to pass T095; skill view counts half-right as half, daily and practice combined, weakest deck first
- [ ] T097 [US2] Record finished plays and answers in `front/src/storage.ts` from the play flow (ignore answers marked `duplicate`), keyed by the play's server date
- [ ] T098 [US2] Show current streak, longest, freeze and the skill view in `front/src/views/Home.tsx`, with the plain note that progress is kept on this browser (FR-016)

**Checkpoint**: V5 passes; the home screen shows the figures after a played daily.

---

## Phase 7: User Story 3 - Share the result without spoilers (P2)

**Goal**: copy a share card with no question content.

**Independent test**: finish a daily, copy the card, check it against the format and that it has
no question text, answer or deck hint.

- [ ] T099 [P] [US3] Unit tests in `front/src/components/ShareCard.test.tsx`: exact format `Stay Sharp #<n> · <Level>` / `<5 squares>  <score>/5 · speed +<bonus> · <m>m<ss>s · streak <k>` / `<site address>`; `relaxed` instead of the bonus; distinct symbols readable as text; no question content
- [ ] T100 [US3] Implement `front/src/components/ShareCard.tsx` and the "Copy result" action in `front/src/views/Result.tsx`; when the clipboard is not available, select the text and say so (Story 3, scenario 3)

**Checkpoint**: Story 3 scenarios pass in Vitest and in one Playwright step of `daily.spec.ts`.

---

## Phase 8: User Story 4 - Challenge a colleague (P3)

**Goal**: an anonymous challenge link; the colleague plays the same set; both results side by
side.

**Independent test**: finish on browser A, create a link, play it on browser B, and check both
see both results (V6).

- [ ] T101 [P] [US4] Integration tests in `api/tests/integration/test_challenges.py`: creating twice returns the same id; colleague sees only "A colleague scored <score>/5" before finishing; result item written in the same transaction as the fifth answer with `attribute_not_exists`; cap of 50 results (transaction retried without item 3, answer still graded); a colleague who already finished gets their snapshot from the existing play at first view; past-date link plays as a past set; expired (compare `expiresAt` with now), unknown and malformed ids; challenger opening their own link
- [ ] T102 [P] [US4] Contract tests in `api/tests/contract/test_challenges.py` for `/challenges` and `/challenges/{challengeId}`
- [ ] T103 [P] [US4] Playwright test in `front/tests/e2e/challenge.spec.ts` with two browser contexts (V6)
- [ ] T104 [US4] Implement `api/src/staysharp/store/challenges.py`: `CH#<challengeId>` `META` with `ownerHash`, owner snapshot `{grades[5], score, bonus, elapsedMs, relaxed}`, `results` count, `expiresAt` = 30 days; `challengeId` = 12 random base32 characters stored on the owner's play; `R#<playerHash>` items
- [ ] T105 [US4] Add item 3 (challenge result and `META.results < 50` condition) to the answer transaction in `api/src/staysharp/store/answers.py` for plays started from a challenge
- [ ] T106 [US4] Implement `POST /challenges` and `GET /challenges/{challengeId}` in `api/src/staysharp/handlers/routes_challenges.py`; emit `ChallengesCreated`, `ChallengesOpened` and `ChallengesFinished`
- [ ] T107 [US4] Implement `front/src/views/Challenge.tsx` (served at `/c/<id>`): invitation, play through the same Play view, side-by-side squares, score and time; plain message and "Play today's daily" for bad links

**Checkpoint**: V6 passes in dev.

---

## Phase 9: User Story 5 - Practice mode with weak spots (P3)

**Goal**: practise past questions by deck; missed ones come back sooner; nothing changes the
streak or the daily.

**Independent test**: miss one practice question, answer others right, and check the missed one
returns within the next 5 (V14 for the server side).

- [ ] T108 [P] [US5] Integration tests in `api/tests/integration/test_practice.py`: questions only from `POOL#<level>#<deck>` with `SK < today`; `prefer` with a future qid, an unknown qid or another level's qid returns a normal past question, never the requested one; at most 200 attempts per player per day (`PRACOUNT#<date>` conditional `ADD`); attempts expire after 14 days; same answer twice on one attempt counted once (C4, V14, FR-006)
- [ ] T109 [P] [US5] Unit tests in `front/src/progress/boxes.test.ts`: a miss goes to box 1 and returns within 5 questions; each right answer moves up one box; box 5 no longer preferred; at most 5 preferred qids sent (FR-022)
- [ ] T110 [US5] Implement `api/src/staysharp/store/practice.py` and `POST /practice/next`, `POST /practice/{attemptId}/answer` in `api/src/staysharp/handlers/routes_practice.py`, reusing `domain/views.py`, `domain/grading.py` and the R2 transaction on `PRA#<attemptId>`
- [ ] T111 [US5] Implement `front/src/progress/boxes.ts` to pass T109
- [ ] T112 [US5] Implement `front/src/views/Practice.tsx`: deck filter or "all decks", same feedback as the daily, never touches streak, freeze or the daily result (FR-023)

**Checkpoint**: V14 passes; practice works in dev with the prototype questions.

---

## Phase 10: Polish and cross-cutting concerns

- [ ] T113 [P] Implement `front/src/views/Privacy.tsx`: what is stored, where (Switzerland or EU), that clearing the browser removes local progress, in words a 12-year-old can follow (FR-035, FR-036)
- [ ] T114 [P] Lighthouse CI config `front/lighthouserc.json` asserting 1.0 in all four categories on mobile and desktop presets for every page, and `front/tests/e2e/a11y.spec.ts` with axe (WCAG 2.2 AA, no violations) on every view, including relaxed reachable before and during a play (FR-033, FR-034, SC-006, V10)
- [ ] T115 [P] Playwright performance test `front/tests/e2e/perf.spec.ts` (Moto G Power profile, Slow 4G, cold Lambda included): first question interactive under 2 s on dev (SC-007, V17)
- [ ] T116 [P] Add WAF to `infra/stacks/edge_stack.py`: rate rule 1,000 requests per 5 minutes per IP on `/api/*` with the JSON 429 body of R9, body size rule over 2 KB, AWS managed common rule set, logging off; on the plan chosen in T015
- [ ] T117 [P] Implement `api/src/staysharp/tools/return_rate.py`: monthly read-only count of players with finished plays on two or more dates, and challenge links that led to a finished game; prints aggregate numbers only (SC-010)
- [ ] T118 [P] Write `docs/runbooks/restore.md` and try the PITR restore once in dev (R17); write `docs/runbooks/pepper-rotation.md` (30-day notice, R16)
- [ ] T119 [P] Manual check with a keyboard-only tester and a screen reader on a full relaxed daily; record the date and result in `docs/accessibility-check.md` (SC-007a)
- [ ] T120 Update `README.md`: what the game is, how to run it locally (from quickstart.md), architecture in a few lines, and a "Numbers" section that says "Not measured yet" (Principle I)
- [ ] T121 Run every scenario V1 to V18 of `specs/001-m1-web-app/quickstart.md` and record the result and date of each in `specs/001-m1-web-app/checklists/release.md`

---

## Phase 11: Content stock (plan step 8, runs in parallel from Phase 2)

Not code, and done in the private content repository only. Listed here so the launch gate is
visible; the questions themselves never appear in this repository.

- [ ] T122 Write and approve 70 Senior questions (14 days x 5 decks) in the content repo, none previously public (SC-008)
- [ ] T123 Write and approve 70 Starter questions with a second reader, following FR-024a, in the content repo (SC-008)
- [ ] T124 Schedule 14 days per level from the launch date, publish to prod through the content CI, and check `StockDaysAhead >= 14` per level (SC-008)

---

## Dependencies and execution order

### Phase dependencies

- Phase 1 (Setup): no dependency. T001 is done.
- Phase 2 (Foundational): after Phase 1. Blocks every story. T012 and T013 are done; T015 to
  T017 need the maintainer.
- US1 (Phase 3): after Phase 2. MVP.
- US6 (Phase 4): after Phase 2; the drills (T081, T082) need the US1 answer route deployed; the prod gate in T080 needs the fingerprint scan of T090 and T091 (US7), so the prod part of T080 is finished after them.
- US7 (Phase 5): after Phase 2; can run in parallel with US1. Needed before prod launch, not for
  dev play (dev uses fixtures).
- US2 and US3 (Phases 6, 7): after US1 (they read finished plays).
- US4 (Phase 8): after US1 (it extends the answer transaction).
- US5 (Phase 9): after US1 (reuses views, grading and the R2 transaction) and after US7 for the
  pool items (`POOL#` is written by publish; fixtures can stand in on dev).
- Polish (Phase 10): after the stories it checks.
- Content (Phase 11): in parallel from Phase 2; T124 needs US7 and the prod deploy from US6.

### Within each story

Tests first and failing; then store, then routes, then front end; then the dev check.

### Parallel opportunities

- Phase 1: T003 to T009 and T011 in parallel.
- Phase 2: the four domain test files (T021 to T024) in parallel, then the four domain modules
  (T026 to T029) in parallel; T018 to T020 in parallel with the domain work; T047 to T049 in
  parallel with the API skeleton.
- US1: T051 to T059 in parallel; T064 to T067 in parallel.
- US6 and US7 can run in parallel with US1 once Phase 2 is done.
- US2 and US3 in parallel with each other.

## Parallel example: User Story 1

```text
Tests together:
  T051 test_idempotency.py   T052 test_timing.py   T053 test_replay.py
  T054 test_failures.py      T055 test_validation.py   T056 contract/test_plays.py
  T057 daily.spec.ts         T058 leak.spec.ts      T059 midnight.spec.ts
Components together:
  T064 CodeBlock.tsx   T065 Choices.tsx   T066 Timer.tsx   T067 Squares.tsx
```

## Implementation strategy

### MVP first

1. Phases 1 and 2.
2. Phase 3 (US1): the daily works in dev with fixtures. Stop and check V1 to V4, V13, V15, V16.
3. Phase 4 (US6): nothing goes to prod before the canary, the alarms and the drills pass.

### Before the first prod deploy

US7 (publish and both leak-guard layers), Phase 10 items T114 to T116, and enough approved
content for at least 14 days per level (Phase 11). The prod gate of T080 refuses to run
otherwise.

### Then

US2 and US3, then US4 and US5, each checked in dev on its own before the next.

## Notes

- 124 tasks; T001, T012 and T013 already done on 2026-11-03.
- Maintainer actions: T012, T015 to T017, T084, T093, T122 to T124.
- Each task is one commit (Conventional Commits) on a feature branch; a person reviews and merges.
