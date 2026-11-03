# Stay Sharp Constitution

Stay Sharp is a daily 5-minute game for developers who work with coding agents. This document
sets the rules every spec, plan, task and change in this repository must follow.

## Core Principles

### I. Honesty

- Every figure published in the README, on the site or in posts (players, retention, cost,
  incidents, approval rates) MUST be measured, MUST name its source and MUST carry the date of
  measurement.
- Estimates MUST be labelled as estimates. A figure that has not been measured is written as
  "not measured yet", never guessed.
- Question content MUST be checkable: one clearly right answer, facts from a named and dated
  source, no opinion presented as a fact, no anecdote that cannot be verified.

Rationale: the project is public and is used as evidence of how it was built. One invented
number discredits all the others.

### II. Deterministic, server-side grading (NON-NEGOTIABLE)

- Grading MUST be deterministic: the same submission for the same question always gets the same
  result. No model takes part in grading.
- Grading MUST happen on the server. Correct answers and explanations MUST NOT reach the browser
  (API responses, bundled JavaScript, source maps, static files, caches) before the player has
  submitted an answer to that question.
- Every scoring write MUST be idempotent: the same answer sent twice counts once.

Rationale: a game whose answers can be read in dev tools, or whose score changes on retry, is
not a game.

### III. The model proposes, code checks, a person decides

- Nothing a language model writes reaches players without explicit approval by a person, with an
  audit trail (who approved, when, which version).
- Model output MUST be validated in code (schema, grounding checks) before a person sees it.
  Text fetched from the internet is untrusted input (prompt injection) and is handled as data,
  never as instructions.
- Every real Bedrock call (development, CI, evaluation or production) MUST be approved by the
  maintainer beforehand, because it costs money and sends data to AWS. CI runs model
  evaluations offline against recorded fixtures only.
- Every model call MUST set `max_tokens` and log its cost.

Rationale: models are useful for drafting and unreliable as authorities.

### IV. Reliability first (NON-NEGOTIABLE)

- Every queue is treated as at-least-once. Every consumer MUST be idempotent: an idempotency key
  plus a DynamoDB conditional write, using AWS Lambda Powertools idempotency where it fits.
- Every queue MUST have a dead-letter queue with an explicit `maxReceiveCount`, an alarm on DLQ
  depth, and a written, tested redrive procedure in the repository.
- Batch consumers MUST report partial batch failures, so that only failed records are retried.
- Every external call (HTTP, AWS SDK, model) MUST have an explicit timeout.
- Retries MUST use exponential backoff with jitter and a maximum number of attempts, and only for
  temporary errors (timeouts, throttling, 5xx). Permanent errors (4xx, validation) fail at once
  and are recorded.
- Every downstream response MUST be checked (status code and body); a call is not a success
  until the response says so.
- No error is swallowed: every failure is logged with its business id and either fails the
  invocation or is reported as a batch item failure.

Rationale: the parts that fail quietly (duplicates, hangs, silent 500s) are the ones this
project exists to get right.

### V. Everything as code, gated delivery

- All infrastructure MUST be defined in AWS CDK (Python). No manual changes in the console; any
  emergency change is written back into code the same day.
- CI MUST pass before merge: lint, type checks, unit and integration tests, CDK assertion tests,
  `cdk synth` and `cdk diff` against the target environment.
- Production deploys of API functions MUST use Lambda aliases with a canary (CodeDeploy) gated by
  error alarms and by a scoring-failure metric, with automatic rollback when an alarm fires.
- Two environments (dev and prod) as separate stacks, with separate names, roles and alarms, in
  one AWS account dedicated to the project, inside an AWS Organization. Nothing else runs in that
  account.

Rationale: a change that cannot be reviewed, repeated or rolled back is a risk, not a feature.

### VI. Security and privacy

- Least-privilege IAM: one role per function, scoped to the exact resources and actions it uses.
- No secrets in code, configuration files, CloudFormation outputs or logs. Secrets live in AWS
  Secrets Manager or SSM Parameter Store and are read at runtime.
- No personal data in logs: log opaque ids (player id, request id, question id), never e-mails,
  usernames, IP addresses or free text.
- Data stays in Switzerland or the EU: region `eu-central-2` (Zurich) by default, an EU region
  only where a service is not available there, Bedrock only through an EU inference profile.
- Collect only the data the game needs. Once accounts exist, "delete my account" MUST remove all
  of a player's data.
- Input from the browser is validated against a schema at the edge; size limits apply.

Rationale: a public game for strangers must be safe to play and safe to stop playing.

### VII. Accessibility and performance

- Every page MUST meet WCAG 2.2 AA: full keyboard play, visible focus, sufficient contrast, text
  alternatives, labelled controls, no information carried by colour alone (including the share
  card squares).
- Every page MUST score 100 in all four Lighthouse categories (Performance, Accessibility, Best
  Practices, SEO) on both mobile and desktop. A score below 100 blocks release unless the
  exception is written down with its reason.
- Motion respects `prefers-reduced-motion`.

Rationale: a daily habit has to work for everyone, on a phone, in five minutes.

### VIII. Cost ceiling

- An AWS budget with an alarm at USD 20 per month MUST exist before the first production deploy.
- Prefer on-demand and pay-per-use services; any always-on resource needs a written reason.
- Real monthly cost is reported in the README under Principle I.

Rationale: a side project that can surprise its owner with a bill will be switched off.

## Content and Writing Rules

- Everything in the repository and in the game is in English.
- Plain English: short sentences, common words, active voice.
- Use the straight hyphen "-" only. Long dashes (en dash, em dash) are not used anywhere.
- No client names, no client data and no internal details of any past or present employer in
  questions, docs, commit messages or posts. Questions are generic and written from first
  principles.
- AI news questions show the date and a link to the source after the answer.
- Do not call the game a "LinkedIn game"; say "a daily game, like Wordle".

## Development Workflow and Review

- Work happens on branches; commits follow Conventional Commits; merges to `main` go through a
  pull request with green CI.
- Every change is reviewed against this checklist before merge, worst defect first:
  1. Business result correct, including edge cases (empty, zero, time zones, day boundaries).
  2. Idempotency: what happens if it runs twice or is retried after a crash?
  3. Error handling: no swallowed exceptions, no success reported after a failure.
  4. Response checks: every downstream response is checked.
  5. Timeouts, retries with backoff and jitter, limited attempts, temporary errors only.
  6. Dead-letter queue and redrive for anything that can fail repeatedly.
  7. Secrets: none in code, config, outputs or logs.
  8. Input validation at the edge; model output validated; a person approves irreversible steps.
  9. Concurrency: conditional writes instead of read-then-write.
  10. Logs and observability: structured logs with ids, no personal data, a metric and an alarm
      for what matters.
  11. Tests cover the failure case (duplicate, 5xx, timeout), not only the happy path.
  12. Accessibility and the Lighthouse budget for front-end changes.
- Every plan produced with Spec Kit includes a Constitution Check against Principles I to VIII;
  any deviation is listed with its justification in the plan's complexity tracking table.
- Agents may write code; a person reviews and merges. The agent setup (roles, limits, review) is
  documented in `AGENTS.md`.

## Governance

- This constitution overrides other practices in the repository. When a document conflicts with
  it, the constitution wins until it is amended.
- Amendments are made by pull request that states the change, the reason and the version bump,
  and updates any dependent template or doc in the same pull request.
- Versioning follows semantic versioning: MAJOR for removing or redefining a principle, MINOR for
  adding a principle or materially expanding one, PATCH for wording.
- Compliance is checked at three points: the plan's Constitution Check, the pull request review
  against the checklist above, and CI gates.

**Version**: 1.0.1 | **Ratified**: 2026-11-03 | **Last Amended**: 2026-11-03
