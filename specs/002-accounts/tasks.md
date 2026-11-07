# Tasks: Optional accounts (M2)

**Input**: `specs/002-accounts/` (spec.md, plan.md, research.md, data-model.md, contracts/,
quickstart.md)

**Tests**: required (constitution, AGENTS.md "write the test first"). Each story's tests come
before its code and must fail first.

**Ids**: T201 onwards, so they never clash with M1's T001 to T126.

**Format**: `- [ ] T### [P?] [Story?] Description with file path`. [P] = different files, no
dependency on an unfinished task. Stories: US1 keep my streak on another device, US2 sign in
without a password, US3 delete my account, US4 offer at the right moment, US5 under 16, US6 sign
out.

## Phase 1: Setup

- [X] T201 Add the accounts contract to the API contract tests and the front type generator: `specs/002-accounts/contracts/accounts.openapi.yaml` read by `api/tests/contract/conftest.py` and `front/scripts/gen-api.mjs` (writes `front/src/api/accounts-schema.ts`)
- [X] T202 [P] Copy `specs/002-accounts/contracts/progress.schema.json` into `api/src/staysharp/publish/schemas/progress.schema.json` with a test that the two stay identical in `api/tests/unit/test_schemas.py`
- [X] T203 [P] Fake Cognito token issuer for local runs and tests (HMAC-signed test tokens checked by the local server the way the JWT authorizer checks real ones, plus the user pool API calls the website makes, at `POST /cognito`): `api/testing/fake_cognito.py`, used by `api/src/staysharp/local.py` when `FAKE_COGNITO=1`

## Phase 2: Foundations (blocks every story)

- [X] T204 Test first: auth stack assertions (Essentials plan, `USER_AUTH` with `EMAIL_OTP` and `WEB_AUTHN` only, no password factor, MFA off, self sign-up on, e-mail as username, case-insensitive, RP id per stage, SES sender, deletion protection on prod, no output with an account id) in `infra/tests/test_auth_stack.py`
- [X] T205 Auth stack: user pool, public app client (no secret, `ALLOW_USER_AUTH` and refresh), SES domain identity `lumineth.com` with DKIM, WebAuthn RP id from the stage's host: `infra/stacks/auth_stack.py`, wired in `infra/app.py`
- [X] T206 Test first: JWT authorizer on `/api/v1/me*` only, M1 routes stay public, the API role cannot call Cognito admin actions, the delete function alone can call `AdminDeleteUser` on this pool: `infra/tests/test_api_stack.py`
- [X] T207 API stack: JWT authorizer, `/me` routes on the API function, `DELETE /me` on its own function (the jobs function comes with T233), sparse index `GSI_INACTIVE` on `lastActiveMonth`: `infra/stacks/api_stack.py`, `infra/stacks/data_stack.py`
- [X] T208 [P] `account_hash` (HMAC of `sub` with the stage pepper) and a log check that no e-mail, token or code pattern is ever logged: `api/src/staysharp/obs.py`, `api/tests/unit/test_obs.py`
- [X] T209 [P] Claims reader for requests that passed the authorizer (`sub`, token use = access): `api/src/staysharp/handlers/http.py` with tests in `api/tests/unit/test_http.py`
- [ ] T210 [maintainer] Add the SES DKIM and the mail-from records to the `lumineth.com` zone, verify the sender address for dev, and request SES production access before prod; steps in `docs/runbooks/account-setup.md` section 7
- [X] T211 Verify the service facts research.md relies on, on the dev pool (Cognito in eu-central-2 with `EMAIL_OTP` and `WEB_AUTHN`, SES region, passwordless self sign-up), and record the result in `specs/002-accounts/research.md`

## Phase 3: US2 - Sign in without a password (P1)

**Goal**: an e-mail code or a passkey signs a player in; no password anywhere.
**Independent test**: create, sign out, sign in with a code; add a passkey and sign in with it.

- [X] T212 [P] [US2] Test first: the USER_AUTH flow over fetch (start with e-mail, answer `EMAIL_OTP`, choose `WEB_AUTHN`, refresh, errors mapped to plain messages that never say whether the e-mail exists) against a mocked Cognito: `front/src/account/cognito.test.ts`
- [X] T213 [US2] Cognito client: `front/src/account/cognito.ts` (sign up without password, start sign-in, answer code, refresh, sign out globally)
- [X] T214 [P] [US2] Test first: session storage (memory and sessionStorage; refresh token in localStorage only with "keep me signed in"; cleared on sign out): `front/src/account/session.test.ts`
- [X] T215 [US2] Session: `front/src/account/session.ts`
- [X] T216 [US2] Sign-in screen: e-mail, code field (one-time-code autocomplete, paste allowed, no time pressure beyond the 10-minute expiry, resend), errors in plain words, keyboard and screen reader friendly: `front/src/account/views/SignIn.tsx` with `SignIn.test.tsx`
- [X] T217 [US2] Test first, then passkeys: add, list, remove, sign in (`navigator.credentials`), Playwright virtual authenticator: `front/src/account/passkeys.ts`, `front/tests/e2e/passkey.spec.ts`
- [X] T218 [US2] Lazy account chunk and `/account` route: router entry, prerendered first screen, site router path to `account.html`: `front/src/router.ts`, `front/src/prerender.tsx`, `infra/stacks/site_router.js`

## Phase 4: US1 - Keep my streak on another device (P1)

**Goal**: an account adopts this browser's history; another browser merges into it; progress
follows the player.
**Independent test**: quickstart A4 to A7.

- [X] T219 [P] [US1] Test first (DynamoDB Local): create account on first adopt (one transaction, `attribute_not_exists`), second adopt returns the same result, a `deleting` account refuses: `api/tests/integration/test_accounts.py`
- [X] T220 [P] [US1] Test first (DynamoDB Local): merge an anonymous id with overlapping days into the primary id: the first finished daily per date and level wins, the other becomes a replay record, challenge results follow, a repeated merge changes nothing, a crash half-way then a retry gives the same end state: `api/tests/integration/test_merge.py`
- [X] T221 [P] [US1] Test first (DynamoDB Local): progress copy with versions (200, 409 with the stored copy, 413 over 64 KB, outline validated against the schema): `api/tests/integration/test_progress_copy.py`
- [X] T222 [P] [US1] Contract tests for `/me`, `/me/adopt`, `/me/progress` (no e-mail in any response, additionalProperties false): `api/tests/contract/test_me.py`
- [X] T223 [US1] Store: `api/src/staysharp/store/accounts.py` (account, player links, progress copy)
- [X] T224 [US1] Store: `api/src/staysharp/store/merge.py` (re-key plays and answers per play in one transaction, merge record written last)
- [X] T225 [US1] Routes: `api/src/staysharp/handlers/routes_me.py` (`GET /me`, `POST /me/adopt`, `GET` and `PUT /me/progress`), registered in `api/src/staysharp/handlers/api.py`
- [X] T226 [P] [US1] Test first: pure merge of two `Progress` values per level (days union with the first result kept, longest = max of recomputed and stored, freeze weeks combined, skill counts and practice boxes combined, never more than one result per date): `front/src/account/merge.test.ts`
- [X] T227 [US1] Merge: `front/src/account/merge.ts`
- [X] T228 [US1] Test first, then sync: send after each change with the last version, on 409 merge and retry (at most 3 times, backoff), offline queue, pull on open and on focus: `front/src/account/sync.ts`, `sync.test.ts`
- [X] T229 [US1] After sign-in: call adopt, switch this browser to the primary player id, pull and merge progress, tell the player when two histories were combined: `front/src/account/views/Account.tsx`, `front/src/storage.ts`
- [X] T230 [US1] e2e: create on browser A with 3 days, sign in on browser B with its own day, both show the merged streak; play on B, reopen A, today shows as played: `front/tests/e2e/accounts.spec.ts`

## Phase 5: US3 - Delete my account (P1)

**Goal**: every item and the Cognito user removed; 204 only when done.
**Independent test**: quickstart A10.

- [X] T231 [P] [US3] Test first (DynamoDB Local and a stubbed Cognito): delete removes account, player links, plays, answers, practice records, progress copy, merge records; challenge results become "deleted player"; Cognito user deleted; an injected failure gives 503 and a retry finishes; repeated delete is 204: `api/tests/integration/test_deletion.py`
- [X] T232 [US3] Deletion: `api/src/staysharp/store/deletion.py` and `DELETE /me` in `routes_me.py` (only role allowed `AdminDeleteUser`)
- [X] T233 [US3] Job: finish deletions stuck in `deleting` for more than 10 minutes; metric and alarm when one stays more than 1 hour: `api/src/staysharp/handlers/account_jobs.py`, `infra/stacks/api_stack.py`
- [X] T234 [US3] Delete screen: one confirmation, plain consequences, result only after 204, then a new anonymous player: `front/src/account/views/DeleteAccount.tsx` with tests
- [X] T235 [US3] Privacy page: what an account stores, where, how long (24 months inactive, backups 35 days), how to delete: `front/src/views/Privacy.tsx`

## Phase 6: US4 - Asked at the right moment (P2)

- [X] T236 [P] [US4] Test first: offer rules (never before the first finished daily; streak 3 or more in this level; hidden 7 days after dismiss; never when signed in): `front/src/components/AccountOffer.test.tsx`
- [X] T237 [US4] Offer on the result screen and an "Account" link in the header (no Cognito code in the main bundle; the link loads the chunk): `front/src/components/AccountOffer.tsx`, `front/src/App.tsx`, `front/src/views/Result.tsx`
- [X] T238 [US4] e2e: a fresh browser sees no prompt through home, play, result (SC-105): `front/tests/e2e/accounts.spec.ts`

## Phase 7: US5 - Under 16 (P2)

- [X] T239 [P] [US5] Test first: "No" stores nothing and sends no request; "Yes" leads to the e-mail step; the answer is sent as `adult: true` only: `front/src/account/views/AgeQuestion.test.tsx`
- [X] T240 [US5] Age question and friendly under-16 page: `front/src/account/views/AgeQuestion.tsx`

## Phase 8: US6 - Sign out (P3)

- [X] T241 [US6] Test first, then sign out: global sign-out, clear tokens and local progress, new anonymous player id; signing in again brings the progress back: `front/src/account/session.ts`, `front/tests/e2e/accounts.spec.ts`

## Phase 9: Inactive accounts (FR-120)

- [X] T242 [P] Test first (mocked clock): warning e-mail once at 23 months of inactivity, deletion at 24 months with the US3 steps, `lastActiveMonth` updated at most once a month per account: `api/tests/integration/test_inactive.py`
- [X] T243 Inactive accounts in the daily job and the warning e-mail through SES (plain text, no tracking): `api/src/staysharp/handlers/account_jobs.py`

## Phase 10: Polish

- [X] T244 [P] Display name: rules and blocked words, `PUT /me`: `api/src/staysharp/domain/names.py`, tests in `api/tests/unit/test_names.py`
- [X] T245 [P] axe on every account screen in light and dark, and accessible authentication checks (paste in the code field, no CAPTCHA): `front/tests/e2e/a11y.spec.ts`
- [X] T246 [P] Lighthouse 100 on `/account` mobile and desktop; first-screen bundle size unchanged (a test fails if the main chunk grows by more than 1 KB): `front/lighthouserc.json`, `front/tests/bundle.test.ts`
- [X] T247 [P] Log check during the account e2e run: no e-mail, name, code, token or IP in captured logs (FR-117): `api/tests/integration/test_logs_no_pii.py`
- [X] T248 Runbooks: delete on request by e-mail, SES bounces and complaints, stuck deletion alarm: `docs/runbooks/accounts.md`
- [X] T249 Reviewer agent pass on the whole feature against the AGENTS.md checklist; fix findings with tests
- [X] T250 Dev validation of quickstart A1 to A15, recorded in `specs/002-accounts/checklists/release.md`
- [ ] T251 [maintainer] Approve the prod deploy (user pool deletion protection, SES out of sandbox, DNS records)

## Dependencies

- Phase 1 and 2 before every story. T210 (maintainer) blocks real e-mail on dev, not local work.
- US2 before US1 (an account needs a sign-in); US1 before US3 (something to delete) and US6.
- US5 (age question) must be in place before account creation is reachable (T229).
- US4 needs the account chunk (T218) only.
- Inactive accounts reuse US3's deletion.

## Parallel examples

- After T207: T208, T209 and T212, T214 at once.
- US1 tests T219, T220, T221, T222, T226 together, then their code.

## Implementation strategy

MVP = Phases 1 to 5 plus Phase 7 (sign in, keep the streak across devices, delete, and the age
question, which must come before any account is created): a complete, lawful account. Then the
offer (US4), sign out, inactive accounts and polish.

## Notes

- 51 tasks; maintainer actions: T210, T251.
- Each task is one commit (Conventional Commits) on `002-accounts`; a person reviews and merges.
