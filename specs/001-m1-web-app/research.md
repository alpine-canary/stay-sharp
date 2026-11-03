# Research: M1 - public daily game without accounts

**Date**: 2026-11-03 (revised after the plan audit, same day) | **Spec**: [spec.md](./spec.md) |
**Plan**: [plan.md](./plan.md)

Each entry: Decision, Rationale, Alternatives considered. Items marked **Verify before first
deploy** are facts not confirmed from an AWS primary source on 2026-11-03. Audit finding ids
(C1-C7, W1-W18, S1-S11) show where a decision changed after the audit.

## R1. How answers stay out of the browser

- **Decision**: Questions are sent one at a time (`POST /plays` returns question 0, then
  `POST .../questions/{n}/open`). The view is built by one function from an explicit field
  allowlist (`index, deck, prompt, code, language, choices, targetSeconds, servedAt`, as in the contract `QuestionView`); a unit test
  passes a full question item, answer fields included, and asserts they cannot appear (S2). The
  response schema is also strict (`additionalProperties: false`). Choice ids are random tokens and
  the choice order is shuffled once at publish; publish checks that the correct position is
  roughly uniform across a batch (S7). The static site contains no question content; source maps
  are not uploaded; API responses carry `Cache-Control: no-store` and CloudFront never caches
  `/api/*` (R8, C2).
- **Replay is not an answer key (C3)**: `POST /plays` refuses `mode=replay` for today unless the
  player's daily play for that date and level is finished (`409`).
- **Practice cannot reach future questions (C4)**: `practice/next` reads the pool
  `POOL#<level>#<deck>` for `date < today` and resolves `prefer` ids only by membership in that
  result, never as a direct `Q#` key. Question ids carry no date or schedule information; publish
  refuses ids that contain a date-like pattern.
- **Accepted residual (S1)**: the set and its choice ids are the same for everyone, so a finished
  player can share the right ids. No leaderboard in M1, so only the cheater gains; per-player ids
  are an M2 item.
- **Alternatives considered**: whole set at once (breaks per-question timing); encrypting answers
  in the browser (key would be in the browser); shuffle at request time with a public hash, as in
  the prototype (order can be recomputed).

## R2. "Same answer twice counts once"

- **Decision**: One answer item per (player, play, question), created by `open` with `servedAt`
  (`if_not_exists`). `answer` runs one `TransactWriteItems`:
  1. update the answer item: set choice, line, grade, bonus, `answeredAt`; condition
     `attribute_exists(servedAt) AND attribute_not_exists(grade)`;
     `ReturnValuesOnConditionCheckFailure=ALL_OLD`;
  2. update the play item, purely additive, no condition (C1): `ADD score :g, bonus :b,
     elapsedMs :e, answered :idxSet` (a string set) and `SET grades.#i = :g`;
  3. on the fifth answer only (known from the play read at the start of the request): put the
     challenge result item `R#<playerHash>` with `attribute_not_exists`, and update the challenge
     `META` counter with condition `results < 50` (W4).
  `finished` is derived as `size(answered) = 5` at read time; no `finishedAt` condition.
  Item 1 alone makes the transaction once-only.
- **Cancellation handling (W1)**:

  | Cancellation reasons | Meaning | Response |
  |---|---|---|
  | item 1 `ConditionalCheckFailed`, old item has `grade`, same choice and line | duplicate | `200`, stored result, `duplicate: true`; `DuplicateAnswers` +1 |
  | item 1 `ConditionalCheckFailed`, old item has `grade`, different answer | conflict | `409` with the stored result in the body (W18) |
  | item 1 `ConditionalCheckFailed`, old item missing or no `servedAt` | not opened (or expired) | `400 invalid_request` |
  | item 3 `ConditionalCheckFailed` only (cap of 50 reached) | challenge full | retry the transaction without item 3; result still graded |
  | `TransactionConflict`, throttling, any other reason | temporary or unknown | retry up to 3 times with backoff and jitter; then `503`, `ScoringFailures` +1; never classified as a duplicate |

  Practice uses the same pattern on `PRA#<attemptId>` items, without a play.
- **Rationale**: Principle IV, FR-006. The business key is the idempotency key, so double clicks,
  retries and two tabs all end in one stored grade, and the old item comes back inside the
  cancellation (no second read, no consistency question).
- **Spike result (T031, 2026-11-03)**: DynamoDB Local 3.3.2 returns the `ALL_OLD` item inside
  `CancellationReasons` (`ConditionalCheckFailed` with `Item`), and no `Item` when the answer item
  does not exist. Duplicate and conflict tests therefore run on DynamoDB Local; no dev-table
  exception is needed.
- **Tests (W15)**: run on DynamoDB Local, not moto (cancellation reasons). An early spike checks
  that DynamoDB Local returns `ALL_OLD` items in cancellation reasons; if not, that case is
  covered by an integration test against the dev table.
- **Alternatives considered**: Powertools idempotency utility (response cache for a time window;
  the rule "once forever" needs the conditional write anyway; kept for M3 queue consumers);
  read-then-write (race); bit mask with a condition (DynamoDB has no bitwise operators, C1).

## R3. Anonymous player id

- **Decision**: The browser creates a UUIDv4 on first visit, keeps it in `localStorage`, and sends
  it in `X-Player-Id`. The server checks the format only. In logs and in challenge items it only
  appears as `HMAC-SHA256(pepper, playerId)` (S4).
- **Rationale**: FR-011. No leaderboard, so a forged id only fools the forger. M2 accounts adopt
  the id.
- **Alternatives considered**: signed server-issued id (revisit in M2); cookie (not needed).

## R4. Content: private repository, publish, leak guard

- **Decision**: A private repository `stay-sharp-content` holds questions as YAML (one file per
  question) and schedules, validated against `contracts/question.schema.json` and
  `contracts/schedule.schema.json`. Its CI runs `publish validate` on every push and
  `publish apply --stage prod` on `main`. The dev stage only ever receives fixture content from
  this repository's `content/samples/` (C7): real future answers never touch dev, the public CI or
  its logs.
- **Publish checks in code (W14)**, all-or-nothing per batch: one question per deck in the FR-001
  order; question level matches schedule level; a qid is scheduled on one date only; no sample or
  `daily_eligible: false` qid in a schedule; `answer.lines` within the real line count of `code`;
  every deck has a target time; Starter questions have `second_reader`; a new version of an
  existing id has `change_reason`; no date-like pattern in ids; correct positions roughly uniform.
  Writes use transactions of at most 100 items; any failure stops before writing. Each edit writes
  version n+1 (`Q#<qid>/V#<n>`) and never changes stored grades (FR-027).
- **Leak guard, two layers (C6)**:
  1. Private CI, offline: runs the API's view builder (R1) over every question of today and the
     next 7 days and fails if any answer, explanation or source text appears in the output
     (SC-002). On success it writes `leak-guard/last-pass` (timestamp, commit) to SSM in the
     project account through its OIDC role.
  2. Public CI, every push and pull request from this repository: downloads a fingerprint file
     (`HMAC-SHA256(K, normalised 12-word shingle)` for prompts, code lines, correct choices and
     explanations of every question scheduled for today or later) from a private S3 object, and
     fails if any shingle of any tracked file or of the full git history matches. `K` is an
     Actions secret (not exposed to fork pull requests; those are checked again on merge). Only
     match counts and file paths are printed, never text.
  The prod deploy job refuses to run if `leak-guard/last-pass` is older than 24 hours or the
  public fingerprint scan of the release commit failed (SC-002a gate).
- **Alternatives considered**: encrypted files in the public repo (key handling, one mistake leaks
  everything); a daily cron only (up to 24 hours of exposure, no release gate).

## R5. Speed bonus and time

- **Decision**: `elapsedMs = answerReceivedAt - servedAt`, both from the Lambda clock. Bonus 0.2 if
  grade is 1, the play is not relaxed at the time of the answer, and `elapsedMs <= target`.
  Targets are copied into the daily set at publish. Relaxed can be switched on mid-play through
  `POST /plays/{playId}/relaxed` (one-way, W3). `servedAt` is written before the response leaves,
  so a lost response uses part of the window; accepted (S6). `SuspiciouslyFast` is an aggregate
  metric with a `deck` dimension only.
- **Alternatives considered**: client timer (fakeable); hard limit (rejected, WCAG 2.2.1).

## R6. Day boundary and dates

- **Decision**: The server computes "today" in `Europe/Zurich` and returns it from `GET /today`.
  A play's own `date` is authoritative for streak, freeze week and share card (W2). A daily play
  for D can be answered until 23:59:59 on D+1; the D+1 set is a separate play available at
  00:00. Validation: `daily` plays accept `date = today` at start; `open` and `answer` accept the
  play's date or the day after. Future dates are always refused.

## R7. Streak, freeze, skill view, practice boxes

- **Decision**: Computed in the browser in one pure TypeScript module (`front/src/progress/`) from
  a local log of finished plays keyed by the play's date, and local answer counts. Rules: answers
  with `duplicate: true` are ignored for counts, boxes and the day log (W13). Table-driven unit
  tests cover freeze earning (5 finished dailies in one ISO week), freeze use (one missed day),
  two missed days, week boundaries, DST weeks and a play finished after midnight. Practice: five
  Leitner boxes per qid in the browser; up to 5 preferred qids sent to `practice/next` (R1).

## R8. API, edge and Lambda layout

- **Decision**: One API Lambda (Python 3.13, arm64, 512 MB, timeout 10 s) with Powertools
  `APIGatewayHttpResolver` and Pydantic v2, behind an API Gateway HTTP API, behind CloudFront on
  the same domain:
  - CloudFront behaviour `/api/*` (C2): `CachePolicy.CACHING_DISABLED`; origin request policy
    forwarding `X-Player-Id` and `Content-Type` only (no cookies, no query strings beyond the
    contract); all methods allowed. A CDK assertion test checks it (V11).
  - Default behaviour: S3 with OAC; static files under a versioned prefix `site/<commit>/`, the
    distribution's origin path points at the current one, so deploying the previous commit is an
    instant revert (W6). A CloudFront Function rewrites `/c/<id>` to `/c/index.html`; other
    unknown paths return a real 404 page (W18).
  - Every boto3 client: `connect_timeout=2`, `read_timeout=3`, standard retry mode, 3 calls in total
    (`total_max_attempts=3`). Every DynamoDB response checked; unexpected shapes raise and count as
    `ScoringFailures` on scoring paths.
  - `POWERTOOLS_LOGGER_LOG_EVENT=false`; validation errors are logged as field names and error
    types only, never input values or headers (S3).
  - Two more functions: `pre_traffic_check` (R10) and `stock_check` (R11). Both are invoked
    asynchronously; each has an on-failure destination (SNS) and an error alarm.
- **Alternatives considered**: one function per route (more aliases for no gain); REST API
  (request validation at the edge but more cost; edge validation done in WAF instead, R9).

## R9. Rate limiting and WAF

- **Decision**: WAF web ACL on CloudFront (in `us-east-1`): rate-based rule per IP on `/api/*` at
  1,000 requests per 5 minutes (a full daily uses about 15; the margin covers schools and offices
  behind one IP, W12) with a custom response: status 429, `Content-Type: application/json`, body
  `{"code":"rate_limited","message":"Too many requests. Try again in a few minutes."}`; a
  size-constraint rule refusing `/api/*` bodies over 2 KB (edge validation for Principle VI); AWS
  managed common rule set. API Gateway throttling: burst 50, rate 20 per second. Lambda reserved
  concurrency 20: a flood gives 5xx to real players instead of a bill; recorded as a deliberate
  availability trade-off. WAF logging off (it would store IPs).
- **Cost (checked 2026-11-03, T015)**: the CloudFront flat-rate Free plan does not fit. Per the
  CloudFront developer guide ("Features by pricing plan tier"), the Free plan has no custom origin
  request policies (we forward only `X-Player-Id` and `Content-Type`), no custom response header
  policies (our strict CSP), and no custom WAF response (our JSON 429); those start at the
  Business plan (USD 200 a month). The Free plan also allows only 5 WAF rules and no rule groups.
  Decision: standard pay-as-you-go CloudFront and WAF, estimated at about USD 7 a month for the
  web ACL and 3 rules. Estimate, not measured.
- **Sources**: <https://aws.amazon.com/cloudfront/pricing/>,
  <https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/flat-rate-pricing-plan.html>,
  <https://docs.aws.amazon.com/PricingPlanManager/latest/UserGuide/plans.html>

## R10. Canary, pre-traffic self-check, rollback

- **Decision**:
  - Lambda alias `live`, CodeDeploy deployment group: `LambdaCanary10Percent5Minutes` in prod,
    `AllAtOnce` in dev.
  - **Self-check without data (C5)**: the API package contains a `selfcheck` entry point that
    grades fixtures bundled in the package (no table access, no metrics except its own
    `SelfCheckFailures`), checks the view builder against the allowlist, and checks the
    duplicate-classification table of R2 with a stubbed DynamoDB client. `pre_traffic_check`
    invokes the **new version** directly (its qualified ARN is passed as an environment
    variable from the same CDK construct; IAM allows `lambda:InvokeFunction` on that ARN only),
    with a synthetic event that routes to `selfcheck`, then reports to CodeDeploy
    (`PutLifecycleEventHookExecutionStatus`). The `selftest` level no longer exists anywhere.
  - **Rollback alarms (W5)**, all `treatMissingData=notBreaching`, period 60 s, 1 of 1 datapoint:

    | Alarm | Metric | Dimensions |
    |---|---|---|
    | Canary errors | `AWS/Lambda Errors` | `FunctionName`, `Resource=<fn>:live`, `ExecutedVersion=<new>` |
    | Canary scoring failures | `StaySharp ScoringFailures` | `Stage`, `FunctionVersion` (from `context.function_version`) |
    | API 5xx | `AWS/ApiGateway 5xx` | `ApiId`, `Stage` |

    The paging alarm for the maintainer (FR-028) is separate: `ScoringFailures` summed over
    versions, >= 1 in 5 minutes, SNS only, never wired to CodeDeploy. Once the alias is at 100 %,
    CodeDeploy no longer rolls back; `docs/runbooks/rollback.md` covers that case.
  - **Fault injection (W11)**: a separate test-only handler module, packaged only in the dev
    build (CDK asset excludes it for prod; a CDK assertion checks the prod asset has no such
    file); the code also refuses it at runtime when `STAGE=prod`. The drill (V8) restores dev in a
    `finally` step, and an alarm fires if a dev function runs with injection on for more than
    30 minutes.
  - **Front end after API (W6)**: the deploy job uploads the new site only after the canary has
    completed. API changes stay compatible with the previous front end for one release (`/api/v1`
    is additive only).
- **Rationale**: Principle V, FR-029; a canary with almost no traffic proves nothing without the
  self-check.

## R11. Alarms, metrics, logs

- **Decision**: Powertools Logger (JSON; `request_id`, `question_id`, `player_hash`; never IP,
  never raw player id). Powertools Metrics (EMF, namespace `StaySharp`, dimension `Stage` on
  everything), one dimension set per metric (W9):

  | Metric | Extra dimension | Use |
  |---|---|---|
  | `ScoringFailures` | `FunctionVersion` | paging + rollback |
  | `AnswersGraded`, `DuplicateAnswers` | - | health |
  | `SuspiciouslyFast` | `Deck` (10 values) | review |
  | `PlaysStarted`, `PlaysFinished`, `PlayDurationMs` | - | SC-001 (p50 of `PlayDurationMs`), SC-010 support |
  | `ChallengesCreated`, `ChallengesOpened`, `ChallengesFinished` | - | SC-010 |
  | `StockDaysAhead` | `Level` | FR-026 |
  | `SelfCheckFailures` | - | R10 |

  About 25 metric series per stage; custom metrics are billed per metric-hour, so short-lived
  `FunctionVersion` series cost little. Estimate in R15. A CDK test and the review checklist flag
  any new dimension.
- **Alarms** to one SNS topic with the maintainer's e-mail: paging `ScoringFailures`; API 5xx;
  Lambda errors and throttles; CloudFront 5xx rate (W6); `StockDaysAhead < 7` with
  `treatMissingData=breaching`, `stock_check` errors, and `stock_check` `Invocations < 1` per day
  (W8); `SelfCheckFailures`; dev fault-injection left on. Rollback alarms also notify the topic,
  and CodeDeploy sends `DeploymentFailure` and `DeploymentRollback` events to it. Stock counts days strictly after today.
- **Budget**: one AWS Budget for the project account, USD 20 actual and USD 16 forecast, in the
  `us-east-1` edge stack (deployed once, not per stage; W9). `AWS::Budgets::Budget` is not
  available in `eu-central-2` (CloudFormation validation, 2026-11-03).
- **Logs**: API Gateway access logs without `sourceIp`; CloudFront standard logs off; retention
  30 days.

## R12. Front end

- **Decision**: React 19, Vite, Tailwind CSS v4, TypeScript strict. No router library. Fonts
  self-hosted and subset. Strict CSP from CloudFront response headers. `POST /plays` returns the
  first question, and `/today` is prefetched from the HTML, so the first question needs two
  round trips at most (SC-007, W7). Tests: Vitest + Testing Library, Playwright + axe-core,
  Lighthouse CI asserting 1.0 x4 on mobile and desktop presets.

## R13. CI/CD and the AWS account

- **Decision**:
  - One AWS account `stay-sharp` in an AWS Organization (constitution 1.0.1), stages `dev` and
    `prod` as separate stacks with stage-prefixed names (`staysharp-dev-*`, `staysharp-prod-*`).
  - **Pull requests** (C7): no AWS credentials, except one read-only job (below). ruff, mypy strict, pytest, eslint,
    `tsc --noEmit`, vitest, CDK assertion tests, `cdk synth --no-lookups` with the committed
    `cdk.context.json`, the public leak-guard scan (R4, secret not available to forks).
    `cdk diff` against dev and prod (constitution V) runs in a separate job, only for pull
    requests from branches of this repository (fork pull requests get no OIDC token), with a
    read-only role; the diff is printed in the job log only, never posted to the pull request.
  - **Push to `main`**: `cdk diff` and deploy dev, then API integration tests, Playwright,
    Lighthouse CI and the end-to-end leak scan against dev (fixture content only), then manual
    approval (GitHub environment `production`), then the SC-002a gate (R4), `cdk diff` and
    deploy prod with the canary, then the front-end upload.
  - **OIDC roles**, one per purpose, trust pinned by `sub`:
    `repo:<owner>/stay-sharp:pull_request` (read-only diff: CloudFormation describe and get
    template, CDK lookup role; no write action),
    `repo:<owner>/stay-sharp:ref:refs/heads/main` (dev deploy),
    `repo:<owner>/stay-sharp:environment:production` (prod deploy),
    `repo:<owner>/stay-sharp-content:ref:refs/heads/main` (publish prod, write `Q#`, `DAILY#`,
    `POOL#`, `STOCK#` keys only, write the leak-guard SSM parameter and fingerprint object).
    CDK bootstrap with narrowed `--cloudformation-execution-policies` (the default makes the deploy
    role an account admin).
  - Every third-party action pinned to a commit SHA; default `GITHUB_TOKEN` permissions read-only;
    no artifacts or traces uploaded from jobs that can touch real content; diffs are printed only
    in post-merge jobs.
- **Rationale**: Principle V and VI for a public repository.

## R14. Region and DNS

- **Decision**: Stateful resources and Lambdas in `eu-central-2`. CloudFront, its ACM certificate
  and the WAF web ACL in `us-east-1` (no game data). `infra/app.py` uses
  `cross_region_references=True` for the certificate and web ACL; the edge stack is deployed first
  and destroyed last. DNS stays at Infomaniak: the ACM validation CNAME and the site CNAME are
  added by the maintainer **in delivery step 1** (W16), so the wait is off the critical path.
- **Verified 2026-11-03** (SSM public parameters, queried from `us-east-1` because the catalogue
  is not served from `eu-central-2`): Lambda, API Gateway, CodeDeploy, DynamoDB, CloudFront, SNS,
  CloudWatch, EventBridge and SSM are available in `eu-central-2`. WAFv2 and Budgets are not
  listed there, as expected: the CloudFront web ACL lives in `us-east-1` (already planned) and
  Budgets is a global service. Checked in the account on 2026-11-03 (T015): the HTTP API
  endpoint (`apigatewayv2`) answers in `eu-central-2`; the Lambda concurrency quota is 400, so
  reserving 20 per stage leaves more than the 100 AWS keeps unreserved. The `python3.13` arm64
  runtime is confirmed by the first dev deploy (T050).
- **Opt-in region**: `eu-central-2` is disabled by default in a new account (calls fail with
  `InvalidClientTokenId`). It was enabled on 2026-11-03 with `aws account enable-region`; the
  account set-up runbook (delivery step 1) must list it first, before CDK bootstrap.
- **Account set-up done 2026-11-03**: `stay-sharp` member account in the existing Organization;
  access through the existing IAM Identity Center instance (`us-east-1`; it holds only the
  maintainers' sign-in identities, no game data) with a 4-hour admin permission set assigned to
  this account only. Account ids and portal URL are kept out of this public repository; CDK reads
  the account from the SSO profile at deploy time.
- **Sources**: <https://aws.amazon.com/blogs/aws/a-new-aws-region-opens-in-switzerland/>,
  <https://aws.amazon.com/blogs/alps/3-year-anniversary-news-about-aws-europe-zurich-region>

## R15. Cost estimate (to replace with measured figures)

Estimate for low traffic (hundreds of players a day), not measured: Lambda, API Gateway HTTP API,
DynamoDB on-demand, S3 and CloudFront near or within free tiers (under USD 2); about 12 alarms
(about USD 1.20); about 50 custom metric series across two stages, many idle in dev (USD 3 to 8
depending on how many are active; free tier covers 10); WAF USD 0 on the CloudFront Free plan or
about USD 7 on standard pricing; one Secrets Manager secret (USD 0.40). Total estimate: USD 5 to
19 a month, which leaves little margin under USD 20 in the worst case: if the first month's
measured cost is above USD 12, cut dev metrics first (dev emits only `ScoringFailures` and
`SelfCheckFailures`). The README shows the measured figure after one full month (Principle I).

## R16. Secrets

- **Decision (W10)**: one secret, the challenge/log pepper, in Secrets Manager with
  `generate_secret_string` and `RemovalPolicy.RETAIN`, per stage; read at cold start and cached.
  Rotating it invalidates live challenges (owner and colleague hashes stop matching), so rotation
  is announced 30 days ahead and done only after that. No other secret exists in M1.
- **Alternatives considered**: SSM SecureString (CloudFormation cannot create one); a pepper in an
  environment variable (visible in console and diffs).

## R17. Data recovery

- **Decision (S10)**: PITR on in prod. `docs/runbooks/restore.md`: restore to a new table, compare
  item counts, switch the table name parameter, redeploy. Tried once in dev before launch.
