# Agents working on Stay Sharp

This file tells coding agents (and people) how work is done in this repository. The rules come
from `.specify/memory/constitution.md`; when the two differ, the constitution wins.

## Roles

| Role | May do | May not do |
|---|---|---|
| Coding agent | Write code, tests and docs on a feature branch; run local checks; open a pull request when asked | Merge, push to `main`, deploy to prod, change AWS by hand |
| Reviewer agent | Read the diff and report findings against the checklist below | Change code |
| Maintainer (a person) | Review and merge, approve the prod deploy, write and approve questions | - |

## Hard limits

- **No real Bedrock call** (development, CI or evaluation) without the maintainer's approval
  first. No role in M1 has a Bedrock permission.
- **No future question in this repository.** Questions for today or a later day live only in the
  private content repository. Here: `content/samples/` and test fixtures only. A question may be
  copied here only after its day has passed.
- **No account ids, portal URLs, e-mail addresses or secrets** in committed files, logs or
  outputs. CDK reads the account from the SSO profile.
- **No personal data in logs**: never the raw player id, IP addresses, headers or input values.
  Log `request_id`, `question_id` and `player_hash`.
- **No manual change in the AWS console.** Everything is in CDK; an emergency change is written
  back into code the same day.
- **No push without the maintainer asking.** Work happens on branches with Conventional Commits.

## How a change is made

1. Read the task in `specs/001-m1-web-app/tasks.md` and the documents it points to.
2. Write the test first and see it fail; then the code.
3. Run `make lint typecheck test` (and `make test-integration` with
   `make ddb-start` when storage is touched; Java only, no Docker needed).
4. Tick the task in `tasks.md` and commit: one task, one commit.

## Review checklist (worst defect first)

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

## Writing rules

English everywhere. Plain words, short sentences, active voice. Straight hyphens only, never
long dashes. No client names and no internal details of any employer. Figures are measured,
sourced and dated, or written as "not measured yet".
