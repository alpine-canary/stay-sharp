# Stay Sharp

A daily 5-minute game for developers who work with coding agents. Agents write more of the code;
Stay Sharp keeps the skills that are left to you in use: spot the bug, improve working code,
reason about failures, know the words and follow this week's AI news.

Five questions a day, the same for everyone, with an explanation after each answer. Three
levels: Starter (from 12 years old, its own five decks), Junior and Senior (the same decks, Junior
with easier questions). No account: progress stays in your browser.

## What you can do

- **Play today's set**: five questions, graded and explained one by one, with an optional speed
  bonus. Relaxed mode turns the timer and the bonus off, before or during a play.
- **Keep a streak**, with one freeze a week earned by finishing five dailies, and see which decks
  need work.
- **Share your result** without spoilers, or **challenge a colleague** with a link: they play the
  same set, then you both see both results.
- **Practise** past questions by deck; the ones you miss come back sooner.

## Run it locally

You need Python 3.13 with `uv`, Node.js 22 with `pnpm`, and Java 17 or later for DynamoDB Local.

```sh
uv sync --directory api && pnpm --dir front install && uv sync --directory infra
make ddb-start                                                    # DynamoDB Local on :8000
uv run --directory api python -m staysharp.tools.seed --fixtures --create-table
uv run --directory api python -m staysharp.local                  # API on :3001
pnpm --dir front dev                                              # site on :5173
```

Checks: `make lint typecheck test`, `make test-integration` (DynamoDB Local) and
`pnpm --dir front test:e2e`. The local seed holds sample and test questions only: questions for
today or a later day never enter this repository.

## How it is built

- **Front end**: React, Vite and Tailwind, a static site on S3 behind CloudFront. Streak, freeze,
  skill view and practice boxes are computed in the browser from local storage.
- **API**: one Python Lambda (AWS Lambda Powertools) behind an HTTP API, in `eu-central-2`
  (Zurich). Questions leave the server without their answer; an answer is graded once, in one
  DynamoDB transaction, however many times it is sent.
- **Data**: one DynamoDB table, with point-in-time recovery. Anonymous plays expire after about 90
  days.
- **Delivery**: AWS CDK in Python. Every change goes through CI; the API goes live through a canary
  that rolls back by itself on errors. WAF limits the API per IP.
- **Content**: questions are written and approved by a person in a private repository and
  published through its own CI. A leak guard checks that no future question reaches this public
  repository or its history.

Details: `specs/001-m1-web-app/` (spec, plan, research, contracts, tasks) and `docs/runbooks/`.

## Rules for contributors and agents

`AGENTS.md` and `.specify/memory/constitution.md`.

## Numbers

Players, cost and incidents will be published here once measured, with the date of measurement.
Not measured yet.
