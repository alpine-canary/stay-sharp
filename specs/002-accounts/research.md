# Research: Optional accounts (M2)

Each entry: decision, why, alternatives. Facts about services were read on 2026-11-06 and are
re-checked at the first dev deploy (T2xx "verify service facts").

## A1. Sign-in service

- **Decision**: Amazon Cognito user pool in `eu-central-2` (Zurich), Essentials feature plan,
  choice-based sign-in (`USER_AUTH` flow) with two first factors only: e-mail one-time code
  (`EMAIL_OTP`) and passkeys (`WEB_AUTHN`). No password factor. No hosted UI: the website calls
  the Cognito user pool API directly.
- **Why**: managed, in Zurich (Cognito launched there in March 2024), free for the first 10,000
  monthly active users on Essentials, issues JWTs that API Gateway can check without code, and
  supports passwordless sign-in. Staying in the M1 account and region keeps data in Switzerland
  (Principle VI).
- **Alternatives**: a custom magic-link service on Lambda and DynamoDB (more code to own and
  secure, signing keys to rotate); Auth0 or Clerk (data outside the AWS account, cost, a third
  party for a side project); Amplify UI (large bundle, threatens Lighthouse 100).
- **Notes**: Cognito does not allow MFA and passwordless for the same user: MFA stays off.
  E-mail one-time codes need the pool to send through Amazon SES. A code (not a link) is what
  Cognito sends; the spec accepts a code or a link (FR-104).

## A2. Sending e-mail

- **Decision**: Amazon SES with the domain identity `lumineth.com` (DKIM), sender
  `stay-sharp@lumineth.com`, in `eu-central-2` if SES is offered there, else `eu-central-1`.
  The SES account leaves the sandbox before prod (maintainer request).
- **Why**: required by Cognito for e-mail codes; cheap; DKIM records go into the `lumineth.com`
  zone like the M1 certificate records (maintainer action, account-setup runbook).
- **Alternatives**: Cognito's default e-mail (does not support e-mail codes and has a daily
  cap).

## A3. Passkey relying party

- **Decision**: relying party ID = the site's host: `stay-sharp.lumineth.com` in prod, the dev
  CloudFront host in dev. Set per stage in CDK.
- **Why**: the passkey ceremony runs in the site's own pages (API flow, no hosted UI), so the
  ID must match the page's origin.

## A4. One player id per account

- **Decision**: an account owns one **primary player id**: the id of the browser that created
  it. Signing in on another browser replaces that browser's anonymous id with the primary one
  after a server-side merge of the anonymous id's records into it. All M1 rules that are "once
  per player id" (one scored daily per date and level, challenge results, practice limits) then
  hold per account without new code.
- **Why**: the M1 server is keyed by player id; changing the key would touch every route.
- **Merge rule** (FR-110, FR-112): for each date and level, the first finished daily wins; an
  unfinished or later play of the same date and level becomes an unscored replay record. Merges
  are idempotent: re-running one changes nothing.
- **Alternatives**: keep several player ids per account and check "once per account" on every
  answer (a new read in the hottest path); key everything by account id (rewrites M1).

## A5. Progress copy on the server

- **Decision**: the browser's progress (per level: days, longest, freeze, skill counts,
  practice boxes) is stored as one item per account, with a version number. The browser sends
  its whole progress after each change with the version it last saw; the server accepts it with
  a conditional write and returns 409 with the stored copy on a version mismatch; the browser
  merges (pure, tested function) and retries. Size limit 64 KB.
- **Why**: M1 computes everything in the browser; storing the result keeps one source of truth
  per account with no server logic to duplicate. Conditional writes follow Principle IV.
- **Alternatives**: recompute progress on the server from plays (duplicate logic in two
  languages); event log per change (more items, more code).

## A6. Account API and authorisation

- **Decision**: new routes under `/api/v1/me`, behind an API Gateway JWT authorizer bound to
  the user pool app client: `GET /me`, `PUT /me` (display name), `POST /me/adopt`,
  `GET /me/progress`, `PUT /me/progress`, `DELETE /me`. M1 routes stay public; when a valid
  token comes with an M1 request, nothing changes (the player id is already the account's).
- **Why**: the authorizer rejects bad tokens before Lambda runs; no token parsing in code.

## A7. Deleting an account

- **Decision**: `DELETE /me` marks the account `deleting` (conditional), deletes the player's
  items by key (plays, answers, practice, progress copy, account), anonymises challenge results
  of that player ("deleted player"), deletes the Cognito user (`AdminDeleteUser`), then deletes
  the marker. Each step is idempotent; a retry continues where it stopped. The response is 204
  only when every step has finished. A daily job finishes any account left `deleting` for more
  than 10 minutes (a dead-letter style safety net) and alarms if one stays more than 1 hour.
- **Why**: FR-114, Principle IV (retries, no success before the work is done).

## A8. Inactive accounts

- **Decision**: a daily scheduled function finds accounts inactive for 23 months (by a sparse
  index on `lastActiveMonth`), sends the warning e-mail once, and deletes accounts inactive for
  24 months with the same steps as A7.
- **Why**: FR-120, storage limitation principle of the nFADP and GDPR.

## A9. Front end

- **Decision**: the account pages and the Cognito calls are a separate code chunk loaded only
  when the player opens "Account" or the result offer; the first screen and the game code do
  not grow. Tokens are kept in memory and `sessionStorage` (refresh token in `localStorage` only
  when the player ticks "keep me signed in on this device"). WebAuthn uses the browser API
  directly.
- **Why**: Lighthouse 100 and the 2 s first question (M1 SC-007) must hold.
- **Alternatives**: Amplify Auth (about 60 KB gzip more on every page).

## A10. Age question

- **Decision**: the first account screen asks "Are you 16 or older?" before the e-mail. "No"
  shows a friendly page and stores nothing (spec clarification 2026-11-06).

## A11. Cost

- **Decision**: Cognito Essentials free tier (10,000 monthly active users), SES at about USD 0.10
  per 1,000 e-mails, two small Lambda functions and DynamoDB on-demand: well under USD 1 a month
  at 1,000 accounts (SC-107). The existing USD 20 budget alarm covers it.
