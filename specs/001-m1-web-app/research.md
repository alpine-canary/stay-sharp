# Research: M1 - public daily game without accounts

**Date**: 2026-11-03 | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Each entry: Decision, Rationale, Alternatives considered. Items marked **Verify before first
deploy** are facts I could not confirm from an AWS primary source on 2026-11-03.

## R1. How answers stay out of the browser

- **Decision**: Questions are sent one at a time through `POST .../questions/{n}/open`. The
  response schema is strict (`additionalProperties: false`) and has no answer, explanation or
  source fields. Choice ids are random tokens and the choice order is shuffled once at publish
  time, so neither the id nor the position says which choice is right. The static site contains
  no question content. Source maps are not uploaded. API responses carry `Cache-Control: no-store`.
- **Rationale**: Principle II and FR-003. Sending one question at a time also gives the server a
  real "first sent" time for the speed bonus (FR-005a) and stops a player from reading question 5
  while the clock runs on question 1.
- **Alternatives considered**: send the whole set at once (breaks per-question timing); encrypt
  answers in the browser (the key would also be in the browser); shuffle at request time with a
  hash of the question id, as in the prototype (the algorithm is public, so the order can be
  recomputed).

## R2. "Same answer twice counts once"

- **Decision**: One DynamoDB item per (player, play, question), created by `open` with
  `servedAt` (`if_not_exists`). `answer` runs a single `TransactWriteItems`:
  1. update the answer item with the grade, condition `attribute_not_exists(grade)`;
  2. update the play item (add grade and bonus, set the answered bit), condition that the bit is
     not set yet.
  If the transaction is cancelled because the grade already exists, the handler reads the stored
  item: the same choice and line returns the stored grade with `200`; a different answer returns
  `409`. Practice uses a server-issued `attemptId` as the key.
- **Rationale**: Principle IV and FR-006. The business key itself is the idempotency key, so
  double clicks, client retries, Lambda retries and two tabs all end in one stored grade.
  The transaction keeps the score and the answers consistent.
- **Alternatives considered**: Powertools idempotency utility alone (it caches responses for a
  time window, but the business rule "once forever" needs the conditional write anyway; Powertools
  stays available for M3 queue consumers, where it fits better); read-then-write (race between two
  tabs).

## R3. Anonymous player id

- **Decision**: The browser creates a UUIDv4 on first visit, keeps it in `localStorage`, and sends
  it in the `X-Player-Id` header. The server checks the format only. All player items expire
  after 90 days (DynamoDB TTL).
- **Rationale**: FR-011. There is no leaderboard in M1, so a forged id only fools the forger. A
  server-signed id would need a secret to manage, for no gain in M1. M2 accounts adopt the id.
- **Alternatives considered**: signed server-issued id (more moving parts, revisit in M2 when the
  leaderboard makes cheating matter); cookie (needs a consent analysis, not needed).

## R4. Where content lives and how it is published

- **Decision**: A private repository `stay-sharp-content` holds questions as YAML, one file per
  question, validated against the JSON Schema in this repository
  (`contracts/question.schema.json`). Its CI runs `publish validate` on every push and
  `publish apply --env dev|prod` on `main`, using a GitHub OIDC role allowed only to write
  `Q#` and `DAILY#` items (IAM condition `dynamodb:LeadingKeys`). Publishing is all-or-nothing per
  batch: validate everything, then write in transactions of at most 100 items; any failure stops
  before writing. Published questions are immutable per version: an edit writes version n+1 and a
  change log entry; grades already given are not touched (FR-027).
- **Leak guard (FR-024b)**: the private repository's CI checks out the public repository with
  full history and fails if any prompt, code block or explanation of a question scheduled for
  today or later appears in it (normalised text fingerprints). It runs on every push to either
  repository (a scheduled job covers pushes to the public one, daily). The public repository's
  own CI only allows question files under `content/samples/`, each marked `sample: true`.
- **Rationale**: clarification of 2026-11-03 and Principle II.
- **Alternatives considered**: encrypted files in the public repo (key management, and one
  mistake publishes everything); an admin screen (out of M1).

## R5. Speed bonus and time

- **Decision**: `elapsedMs = answerReceivedAt - servedAt`, both from the Lambda clock. Bonus 0.2 if
  grade is 1, the play is not relaxed and `elapsedMs <= target`. Targets are copied into the daily
  set item at publish, so a later change never alters a past day. "Suspiciously fast" is an
  aggregate metric per deck, no player id.
- **Rationale**: FR-005a to FR-005d. Server time cannot be faked from the browser.
- **Alternatives considered**: client timer (fakeable); hard limit (rejected in clarification,
  WCAG 2.2.1).

## R6. Day boundary and dates

- **Decision**: The server computes "today" in `Europe/Zurich` (`zoneinfo`) and returns it from
  `GET /today`; the browser never uses its own date for game logic. A daily play started on day D
  can still be answered on D+1 (until 23:59:59 D+1) so a set started before midnight can be
  finished.
- **Rationale**: spec edge cases (device clock, midnight).

## R7. Streak, freeze, skill view, practice boxes

- **Decision**: Computed in the browser in one pure TypeScript module (`front/src/progress/`),
  from a local log of finished days (dates from the server) and local answer counts. Exhaustively
  unit-tested with a table of day sequences, including freeze earning (5 finished dailies in one
  ISO week), freeze use (one missed day), two missed days, week boundaries and Zurich DST changes.
  Practice "weak spots": five Leitner boxes per question id in the browser; the browser sends up
  to 5 preferred question ids to `POST /practice/next`, and the server returns the first one that
  belongs to a past published day, else a random past question of the chosen deck.
- **Rationale**: FR-012 to FR-016, FR-022: progress is local in M1. Keeping it in one pure module
  makes the M2 move to the server a port, not a rewrite.

## R8. API shape and Lambda layout

- **Decision**: One API Lambda (Python 3.13, arm64, 512 MB) with Powertools `APIGatewayHttpResolver`
  and Pydantic v2 models, behind an API Gateway **HTTP API**, behind CloudFront on the same domain
  (`/api/*`), so there is no CORS and one place for security headers and WAF.
  Two more functions: `pre_traffic_check` (CodeDeploy hook, R10) and `stock_check` (daily
  EventBridge schedule, FR-026). Every boto3 client has explicit `connect_timeout=2`,
  `read_timeout=3`, standard retry mode with `max_attempts=3` (temporary errors only, with
  backoff and jitter from botocore). Function timeout 10 s.
- **Rationale**: one function means one canary and one alias to roll back; the routes share the
  same data access and grading code.
- **Alternatives considered**: one function per route (more aliases and deployment groups for no
  gain at this size); REST API (supports WAF directly but costs more; WAF sits on CloudFront
  instead).

## R9. Rate limiting and WAF

- **Decision**: AWS WAF web ACL on CloudFront (created in `us-east-1`), with a rate-based rule per
  IP on `/api/*` (initial value 300 requests per 5 minutes) and the AWS managed common rule set.
  API Gateway stage throttling as a second limit (burst 50, rate 20 per second). Lambda reserved
  concurrency 20 caps the cost of a flood. WAF logging off (it would store IP addresses).
- **Cost**: CloudFront flat-rate plans (Free plan: 1M requests and 100 GB per month, WAF
  included, no overage charges) would remove the WAF cost. **Verify before first deploy**: whether
  the Free plan includes WAF rate-based rules and is available to this account (sources disagree;
  AWS pricing page lists the allowance, third-party pages list "5 WAF rules"). Fallback: standard
  WAF pricing, estimated at about USD 7 a month (web ACL plus 2 rules), still under the USD 20
  budget. Estimate, not measured.
- **Sources**: <https://aws.amazon.com/cloudfront/pricing/>,
  <https://docs.aws.amazon.com/PricingPlanManager/latest/UserGuide/plans.html>

## R10. Canary and automatic rollback with low traffic

- **Decision**: The API function is deployed through a Lambda alias `live` and a CodeDeploy
  deployment group with `LambdaCanary10Percent5Minutes` in prod (`AllAtOnce` in dev). Rollback
  alarms on the alias: `Errors >= 1`, API `5xx >= 1` and `ScoringFailures >= 1`, each over 1
  minute. Because a quiet hour may send zero real requests to the 10 % canary, a
  **BeforeAllowTraffic hook** (`pre_traffic_check`) calls the new version directly: it opens and
  answers a hidden self-test daily set (level `selftest`, never listed), checks grades, the
  answer-hiding schema and the "same answer twice" rule, then reports success or failure to
  CodeDeploy. A failing hook stops the deployment before any player traffic.
  Fault injection for SC-005: a `FAULT_INJECTION=scoring` setting that makes grading raise; a CDK
  assertion test fails the build if it is set in the prod stage.
- **Rationale**: Principle V and FR-029. Without the hook, a canary with no traffic proves nothing.
- **Alternatives considered**: CloudWatch Synthetics canary every 5 minutes (costs more, and only
  sees the live version).

## R11. Alarms, metrics, logs

- **Decision**: Powertools Logger (JSON, `request_id`, `question_id`, `play_id` hash, never the
  player id in plain form, never IP), Powertools Metrics (EMF, namespace `StaySharp`):
  `ScoringFailures`, `AnswersGraded`, `DuplicateAnswers`, `SuspiciouslyFast` (by deck),
  `PlaysStarted`, `PlaysFinished`, `ChallengesCreated`, `ChallengesFinished`, `StockDaysAhead`.
  Alarms to an SNS topic with the maintainer's e-mail: scoring failures (>= 1 in 1 minute,
  meets the 5-minute target of SC-004), API 5xx, Lambda errors and throttles, `StockDaysAhead < 7`,
  AWS Budget at USD 20 (actual) and USD 16 (forecast). API Gateway access logs exclude
  `sourceIp`; CloudFront standard logs off. Log retention 30 days.
- **Rationale**: Principles IV, VI, VIII; FR-028, FR-031; SC-010 aggregate analytics without
  cookies.

## R12. Front end

- **Decision**: React 19, Vite, Tailwind CSS v4, TypeScript strict. No router library (four views:
  home, play, result, practice; plus `/c/{id}` and `/privacy` as prerendered entry points).
  Fonts self-hosted and subset (the prototype loads Google Fonts, which sends the visitor's IP to
  Google). Strict Content-Security-Policy from CloudFront response headers. Tests: Vitest and
  Testing Library (units and components), Playwright with `@axe-core/playwright` (a full daily by
  keyboard, relaxed mode, challenge flow, leak scan), Lighthouse CI with all four categories
  asserted at 1.0 on mobile and desktop presets.
- **Rationale**: Principle VII, FR-033, FR-034, SC-006, SC-007.

## R13. CI/CD and accounts

- **Decision**: GitHub Actions. On pull request: ruff, mypy (strict), pytest with coverage,
  eslint, `tsc --noEmit`, vitest, `cdk synth`, CDK assertion tests, `cdk diff` against dev and prod
  with a read-only OIDC role (trust limited to this repository; pull requests from forks get no
  OIDC token). On merge to `main`: deploy dev, run API integration tests, Playwright, Lighthouse
  CI and the leak scan against dev, then wait for manual approval (GitHub environment
  `production`), then deploy prod (CodeDeploy canary). Accounts: `stay-sharp-dev` and
  `stay-sharp-prod` in an AWS Organization; deploy roles via GitHub OIDC, no long-lived keys.
  `cdk.context.json` committed; no account ids printed in public logs beyond what CDK requires.
- **Rationale**: Principle V, FR-030.

## R14. Region

- **Decision**: All stateful resources and Lambda in `eu-central-2` (Zurich). CloudFront, its ACM
  certificate and the WAF web ACL are global and must be created in `us-east-1`; they store no
  game data. DNS for `stay-sharp.lumineth.com` stays at Infomaniak (CNAME to CloudFront, plus the
  ACM validation CNAME, added by hand by the maintainer).
- **Verify before first deploy**: that API Gateway HTTP API, Lambda `python3.13` on arm64,
  CodeDeploy and DynamoDB TTL are available in `eu-central-2`:
  `aws ssm get-parameters-by-path --path /aws/service/global-infrastructure/regions/eu-central-2/services`.
  Fallback: `eu-central-1` (Frankfurt), recorded as an exception under Principle VI.
- **Sources**: <https://aws.amazon.com/blogs/aws/a-new-aws-region-opens-in-switzerland/>,
  <https://aws.amazon.com/blogs/alps/3-year-anniversary-news-about-aws-europe-zurich-region>

## R15. Cost estimate (to replace with measured figures)

Estimate for low traffic (hundreds of players a day), not measured: Lambda, API Gateway HTTP API,
DynamoDB on-demand, S3 and CloudFront within or near free tiers (under USD 2); about 10 CloudWatch
alarms (about USD 1); WAF USD 0 on the CloudFront Free plan or about USD 7 on standard pricing.
Total estimate: USD 3 to 10 a month. The README will show the measured figure after one full month
(Principle I).
