# Stay Sharp - product and technical spec (v0.1, 23.10.2026)

> Working name. "Agents write the code. Don't lose your touch." A daily 5-minute game for developers: spot the bug, name the acronym, survive the outage, know this week's AI news.

## 1. Why

| Goal | How this project serves it |
|---|---|
| Keep developers sharp | Agents write more of the code; reading, reviewing and reasoning about failure are the skills that matter. Five minutes a day keeps them in use. |
| Show how it is built | A public repository: architecture, agent setup (roles, limits, how changes are reviewed), tests, a short walkthrough. |
| Practise reliability for real | SQS + DLQ + redrive, idempotent consumers (Powertools), Lambda partial batch failures, DynamoDB, CDK, canary deploys, alarms. The news pipeline is built around "what if it arrives twice / fails five times / the model invents something". |
| Practise review | Writing the code-review questions means applying the review checklist every week. |
| Reach | A daily game people share; "build in public" posts about how it was built. |
| Lumineth | Lives under the Lumineth tech section; shows the agency builds real software, not only sites. |

**Honesty rule**: the README and posts say what is true and measured - traffic, costs, incidents. No invented numbers.

## 2. The game

### 2.1 The daily
- **One daily set, the same for everyone at a level**, unlocked at 00:00 Europe/Zurich. 5 questions, about 5 minutes.
- One question per deck + one bonus (rotating):
  1. **Spot the bug** - a short snippet (Python, TypeScript, PHP, SQL, CDK). Tap the line with the worst defect, then pick what's wrong from 4 options.
  2. **Could do better** - code that works but has a weakness (no timeout, float for money, N+1, secret in logs). Pick the best improvement.
  3. **What if it fails?** - a small system diagram + a failure ("the e-mail arrives twice", "the supplier API hangs"). Pick what happens / what protects it.
  4. **Acronym or tool** - "HNSW is…", "What does a DLQ hold?", "CDK vs CloudFormation?".
  5. **AI this week** - one question on recent AI news, always with date and source link shown after answering.
- **Levels**: Junior, Mid, Senior, Lead. Same decks, different depth. Lead adds Run topics (incidents, post-mortems, SLAs, change freezes).
- **Scoring**: correct + time bonus (capped, so careful beats fast). **Explanation shown after every answer** - learning is the point.
- **Streak** like LinkedIn's games; a missed day breaks it (one "freeze" per week).
- **Share card** (no spoilers):
  ```
  Stay Sharp #42 · Senior
  🟩🟩🟥🟩🟩  4/5 · 3m12s · streak 9
  stay-sharp.lumineth.com
  ```

### 2.2 Practice mode (after the daily)
- Unlimited questions from the archive, by deck and level.
- **Weak spots**: missed questions come back sooner (Leitner boxes, 5 boxes).

### 2.3 Accounts
- **Play without an account** (progress in the browser).
*Accounts arrive in M2. M1 is played without an account (streak kept in the browser).*
- **Account optional**, to keep streaks across devices and appear on the leaderboard: username + password (Cognito), e-mail needed only for password reset. No other personal data.
- **Leaderboard** (later, not at launch: streaks come first): weekly, per level, by username. Opt-in.
- **Delete my account** button, with all data (nFADP / GDPR).

### 2.4 Not in v1
- Free-text answers graded by a model (cost, abuse, unpredictability). The game is **graded deterministically**; the model is used only *before* publication, to draft content a person approves.
- Mobile store app. v1 is a web app that installs on the home screen (PWA). Store app only if people use it.
- Paid features, ads.

## 3. Content

### 3.1 Question format (one JSON schema for all decks)
```json
{
  "id": "q_2026_10_23_spot_01",
  "deck": "spot_the_bug",
  "level": "senior",
  "language": "python",
  "prompt": "Which line is the worst defect?",
  "code": "for order in orders:\n    try:\n        requests.post(URL, json=order)\n ...",
  "answer": { "line": 3, "choice": "b" },
  "choices": ["...", "...", "...", "..."],
  "explanation": "requests doesn't raise on 4xx/5xx - a 500 counts as success...",
  "checklist_points": [3, 4],
  "sources": [],
  "status": "approved",
  "author": "human | model_draft_approved",
  "approved_by": "maintainer", "approved_at": "2026-10-23T08:10:00Z"
}
```

### 3.2 Where questions come from
| Deck | v1 source | Later |
|---|---|---|
| Spot the bug / Could do better | Hand-written from the review checklist (see the constitution) | Model drafts variations, a person approves |
| What if it fails? | Hand-written generic system scenarios (no client names, no real incidents that cannot be checked) | Same |
| Acronyms and tools | A hand-written glossary of common engineering and AI terms | Same |
| AI this week | **News pipeline (section 4)** | Same |

**Launch stock**: 60 days of dailies prepared before going public (≈ 300 questions across levels), so a missed week of writing doesn't break the game.

### 3.3 Rules for every question
- One clearly right answer; distractors plausible but wrong.
- No client data, no client names, no employer secrets.
- AI news: a fact from the source, dated, linked. Never an opinion presented as a fact.

## 4. News pipeline (Bedrock) - the reliability showcase

```
EventBridge (daily 05:00) ─► Lambda "fetch" ─► reads an allowlist of RSS feeds (vendor blogs, AWS, major outlets)
                                │  one message per article, key = hash(canonical URL)
                                ▼
                               SQS "articles" ── maxReceiveCount 3 ──► DLQ ─► alarm, redrive
                                │
                                ▼
                     Lambda "draft" (batch 5, ReportBatchItemFailures, Powertools idempotency on URL hash)
                                │  1. fetch article text (timeout 10 s, size cap)
                                │  2. Bedrock (Claude, EU inference profile, max_tokens set):
                                │     "Extract 1-2 checkable facts and draft one question. Use ONLY the text below.
                                │      Return JSON matching the schema. Quote the sentence that proves the answer."
                                │  3. Guardrails in code:
                                │     - JSON schema valid
                                │     - quoted sentence really appears in the article text (string match)
                                │     - published date within 14 days
                                │     - no answer leaked in the prompt; 4 distinct choices
                                ▼
                     DynamoDB "drafts" (status = pending) ─► admin page: a person approves / edits / rejects
                                                                │
                                                                ▼
                                                       scheduled into a future daily
```
- **The model proposes, code checks, a person decides.** Nothing a model writes reaches players without approval.
- **Article text is untrusted input** (prompt injection): it goes in a delimited block; instructions inside it are ignored; output is schema-validated anyway.
- **Twice?** Same article from two feeds → same URL hash → the second is skipped (conditional write).
- **Fails five times?** After 3 receives → DLQ, alarm by e-mail, redrive after a fix.
- **Model invents?** The quote check rejects it; rejection reason stored and counted.
- **Cost control**: max articles per day (e.g. 30), max_tokens per call, cost logged per run, budget alarm.
- **Evaluation**: a golden set of ~30 real articles with expected facts; run offline in CI; run against the real model only on demand (approve each run - cost, data sent to AWS).
- **Measured in the README**: drafts per week, approval rate, rejection reasons, cost per approved question.

## 5. Architecture

```
Browser (React 19 + Vite + Tailwind, PWA)
   │  static files: S3 + CloudFront (stay-sharp.lumineth.com, CNAME at Infomaniak DNS)
   ▼
API Gateway (HTTP API) ── Cognito authorizer (optional login)
   │
   ▼
Lambda (Python 3.13, AWS Lambda Powertools) ─► DynamoDB (single table)
   - GET  /daily?level=          today's questions WITHOUT answers
   - POST /daily/answer          server-side scoring; idempotent per (player, date, question)
   - GET  /practice                  (M1)
   - GET  /me, /leaderboard          (M2, with accounts; leaderboard after streaks)
   - DELETE /me                  account + data
News pipeline (section 4) ─► same table, "drafts" items
Admin (same app, admin group in Cognito) ─► approve / edit / schedule questions
Everything in AWS CDK (Python), 2 environments (dev, prod), each in its own AWS account inside an AWS Organization, region eu-central-2 (Zurich) where available, Bedrock via EU inference profile.
```
- **Answers never sent to the browser before submitting** (no cheating via dev tools).
- **Anonymous players**: random device id; answers scored server-side the same way; can be attached to an account later.
- **Single DynamoDB table**, access patterns:
  | Pattern | Key |
  |---|---|
  | Daily set for a date + level | `PK=DAILY#2026-10-23#senior` |
  | A question | `PK=Q#<id>` |
  | A player's answers for a day | `PK=PLAYER#<id>`, `SK=ANS#2026-10-23#<qid>` |
  | Streak / stats | `PK=PLAYER#<id>`, `SK=STATS` |
  | Weekly leaderboard (later) | GSI `LB#2026-W43#senior`, sort by score |
  | Drafts to review | GSI `STATUS#pending` |
- **Lumineth site**: a page in the tech section of www.lumineth.com (Hub) presents the game and links to the subdomain. The Hub itself is not changed.

## 6. Quality, security, operations (practised, not just claimed)
- **Tests**: unit (scoring, streaks, idempotency), CDK assertions (DLQ, maxReceiveCount, alarms, no public buckets), API tests, a Playwright test of one full daily.
- **CI** (GitHub Actions): lint, tests, CDK synth + diff, golden set offline.
- **Deploy**: Lambda aliases with **CodeDeploy canary** (10% for 5 min) gated by errors **and** a custom metric (scoring failures), automatic rollback.
- **Alarms**: DLQ depth, API 5xx, Lambda errors, Bedrock cost per day, AWS budget.
- **Security**: WAF rate limit on the API, Cognito password policy, least-privilege IAM per Lambda, secrets in Secrets Manager (none in code), no personal data in logs (player id only).
- **Privacy page**: what is stored (username, e-mail, scores), where (Switzerland/EU), how to delete.
- **Accessibility and performance**: WCAG 2.2 AA, keyboard play, Lighthouse 100 x4 mobile and desktop.
- **Agent setup documented** in the repo (`AGENTS.md`): which agents write which parts, their limits, and that every change is reviewed with the checklist before merge.

## 7. Cost estimate (to verify after one month)
At low traffic (hundreds of players a day): CloudFront + S3 + Lambda + DynamoDB on-demand + Cognito free tier ≈ a few USD a month; Bedrock ≈ 30 articles a day with a small model ≈ a few USD a month. Budget alarm at USD 20/month. Real figures go in the README.

## 8. Milestones
| # | Deliverable | Shows |
|---|---|---|
| M0 | Clickable prototype (`prototype/stay-sharp.html`), 2 weeks of dailies, self-play | Game feel; question quality |
| M1 | Public web app, no accounts: daily + practice + share card; CDK, CI, canary | React, CDK, serverless API |
| M2 | Accounts, streaks across devices, delete-my-account; leaderboard once streaks are in use | Cognito, DynamoDB design, privacy |
| M3 | News pipeline with Bedrock + admin approval + golden set | SQS/DLQ/idempotency, LLM guardrails, evaluation |
| M4 | Public launch on LinkedIn + "how I built it" posts; 60 days of stock | Visibility |
| M5 | After 4 weeks: numbers in README (players, retention, cost, incidents + post-mortems) | Run, honesty |

## 9. Decisions (taken 23.10.2026)
- **Name and address**: Stay Sharp, at `stay-sharp.lumineth.com`, plus a page in the Lumineth tech section that links to it.
- **Repository**: public, on the maintainer's personal GitHub.
- **Language of the game**: English only.
- **Backend**: Python (Lambda + Powertools); front end React 19 + Vite + Tailwind; infrastructure in AWS CDK (Python).
- **Social features**: streaks at launch; leaderboard later.
- **AWS**: a separate AWS account for this project, inside an AWS Organization with consolidated billing.

## 10. Words to avoid in public
- Don't call it a "LinkedIn game" (trademark); say "a daily game, like Wordle".
- No client names, no internal details of any employer in questions or posts.
