# Implementation Plan: Optional accounts (M2)

**Branch**: `002-accounts` | **Date**: 2026-11-06 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/002-accounts/spec.md`

## Summary

An optional account that keeps a player's progress across devices, without a password. A Cognito
user pool in Zurich signs players in with a one-time e-mail code (sent through SES from
`lumineth.com`) or a passkey; the website calls the user pool API directly from a separate code
chunk, so the game's first screen does not grow. An account owns one primary player id: signing
in on another browser merges that browser's anonymous plays into it on the server (first
finished daily per date and level wins) and switches the browser to the primary id, so every M1
"once per player" rule holds per account unchanged. The browser's progress is stored per account
as one versioned copy with conditional writes; conflicts are merged in the browser by a pure,
tested function. "Delete my account" removes every item by key, anonymises challenge results,
deletes the Cognito user, and answers only when done; a daily job finishes stuck deletions and
deletes accounts inactive for 24 months after a warning. No account under 16: the age question
comes before the e-mail and stores nothing. Everything in CDK; dev first.

## Technical Context

**Language/Version**: Python 3.13 (API, tools, CDK); TypeScript 5 strict (front end), as M1

**Primary Dependencies**: M1's (Powertools, Pydantic v2, boto3, React 19, Vite, Tailwind v4,
CDK v2); new: Cognito user pool API (no SDK in the browser: `fetch` to the Cognito JSON API),
WebAuthn browser API, Amazon SES; `jsonschema` for the progress outline (already a tool
dependency)

**Storage**: the M1 DynamoDB table (new items: account, player link, progress copy, merge record;
one sparse index for inactive accounts); Cognito holds the e-mail and passkeys

**Testing**: pytest with DynamoDB Local (merge, progress versions, delete), a fake Cognito token
issuer for local and CI; CDK assertions (user pool settings, authorizer, least privilege);
Vitest (merge function, offer rules, token handling); Playwright with a virtual WebAuthn
authenticator and axe; Lighthouse CI on `/account`

**Target Platform**: AWS `eu-central-2`; evergreen browsers from 390 px; passkeys where the
device supports them, e-mail code everywhere

**Project Type**: web application (M1 structure)

**Performance Goals**: progress on a new device in under 3 s (SC-102); M1's 2 s first question
and Lighthouse 100 unchanged

**Constraints**: no e-mail or token in logs; account code never in the first-screen bundle;
progress copy at most 64 KB; delete finishes within 1 minute

**Scale/Scope**: 1,000 accounts at first (SC-107); 6 new API routes, 2 scheduled or async
functions, 4 new screens (age question, e-mail and code, account, delete confirmation)

## Constitution Check

| Principle | Check | Status |
|---|---|---|
| I. Honesty | Account count and cost reported only once measured; privacy page states what is stored | Pass |
| II. Server-side grading | Unchanged; the merge never re-grades, it moves graded records | Pass |
| III. Model proposes, person decides | No model involved | Pass (n/a) |
| IV. Reliability | Conditional writes for progress and account creation; idempotent merge and delete with retries; job and alarm for stuck deletions; failure tests (409, retry, injected failure) | Pass |
| V. Everything as code | User pool, SES identity, authorizer, jobs, alarms in CDK; DNS records for DKIM documented for the maintainer as in M1 | Pass |
| VI. Security and privacy | E-mail only in Cognito; no PII in logs (`account_hash`); data in Zurich; delete removes everything; under 16 stores nothing; least-privilege roles (delete function alone may call `AdminDeleteUser`) | Pass |
| VII. Accessibility and performance | Account chunk lazy-loaded; WCAG 2.2 accessible authentication (paste allowed, no puzzle); Lighthouse 100 on `/account` | Pass, measured in A13 |
| VIII. Cost ceiling | Free tiers, pay per use; budget alarm already in place | Pass |

No violation; no complexity to justify.

## Project Structure

### Documentation (this feature)

```text
specs/002-accounts/
├── spec.md
├── plan.md               # this file
├── research.md           # A1 to A11
├── data-model.md
├── quickstart.md         # validation scenarios A1 to A15
├── contracts/
│   ├── accounts.openapi.yaml
│   └── progress.schema.json
└── checklists/requirements.md
```

### Source Code (repository root)

```text
api/src/staysharp/
├── handlers/routes_me.py        # GET/PUT/DELETE /me, POST /me/adopt, GET/PUT /me/progress
├── handlers/account_jobs.py     # daily: finish stuck deletions, warn and delete inactive accounts
├── store/accounts.py            # account, player links, progress copy (conditional writes)
├── store/merge.py               # re-key an anonymous player's plays into the primary id
├── store/deletion.py            # delete by key, anonymise challenge results, Cognito user
└── domain/names.py              # display name rules
api/testing/fake_cognito.py      # signed test tokens for local runs and tests

front/src/account/               # lazy chunk: never imported by the first screen
├── cognito.ts                   # USER_AUTH flow over fetch (EMAIL_OTP, WEB_AUTHN), tokens
├── passkeys.ts                  # navigator.credentials create/get
├── session.ts                   # token storage, refresh, sign out
├── sync.ts                      # progress copy: send, 409, merge, retry
├── merge.ts                     # pure merge of two Progress values
└── views/                       # AgeQuestion, SignIn, Account, DeleteAccount
front/src/components/AccountOffer.tsx   # result-screen offer (small, no Cognito code)

infra/stacks/auth_stack.py       # user pool, app client, SES identity, WebAuthn RP id per stage
infra/stacks/api_stack.py        # + JWT authorizer, /me routes, account jobs, alarms
```

**Structure Decision**: same three-part structure as M1; account code isolated in its own
modules on both sides so M1 paths stay as they are.

## Phases

1. **Foundations**: auth stack (dev), fake token issuer, JWT authorizer, `account_hash` logging,
   progress schema; maintainer: SES domain records and sandbox exit.
2. **Story 2 (sign in) + Story 1 (create and adopt)**: Cognito flow in the browser, `POST
   /me/adopt`, progress copy with versions, merge in the browser and on the server.
3. **Story 3 (delete)**: delete route, job, alarm, privacy page.
4. **Story 4 (offer) and Story 5 (age question)**: offer rules, Account link, under-16 page.
5. **Story 6 (sign out)**, passkeys, inactive accounts.
6. **Polish**: accessibility, Lighthouse, logs check, runbook (delete on request, SES), dev
   validation A1 to A15; prod only with the maintainer's approval.

## Complexity Tracking

None.
