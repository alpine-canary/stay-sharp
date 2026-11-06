# Quickstart: validating optional accounts (M2)

Local runs use DynamoDB Local and a fake sign-in (a test user pool stub that issues signed test
tokens, `api/testing/fake_cognito.py`); dev runs use the real user pool and SES in sandbox mode
with the maintainer's verified address. Prod needs the maintainer's approval.

| # | Scenario | How | Expected |
|---|---|---|---|
| A1 | No prompt before the first daily (SC-105, FR-102) | e2e, fresh browser: home, play, result | No sign-up prompt anywhere; "Account" link present |
| A2 | Offer at streak 3, hidden 7 days after dismiss (FR-102) | e2e with seeded local progress | Offer once; dismissed, absent for 7 days of the mocked clock |
| A3 | Under 16 stores nothing (FR-116) | e2e: Account, answer "No" | Friendly page; no request to the sign-in service or the API |
| A4 | Create with an e-mail code (FR-104, FR-109) | dev: real e-mail; local: fake | Signed in; `GET /me` 200; progress copy equals the browser's |
| A5 | Second browser merge (FR-110, FR-112, SC-103) | integration: two player ids with overlapping days | Each date and level once; the later play is a replay; streak recomputed; repeated merge changes nothing |
| A6 | Progress follows within 1 minute (FR-111) | e2e: two contexts, play on one, reopen the other | Today shows as played on both |
| A7 | Version conflict (FR-111) | integration: two PUTs with the same version | One 200, one 409 with the stored copy; merged retry 200 |
| A8 | Passkey add and sign in (FR-105) | dev, a device with a passkey; local: virtual authenticator in Playwright | Sign-in with the passkey only |
| A9 | Wrong or expired code (FR-106) | dev and local | Plain refusal, no hint whether the e-mail exists |
| A10 | Delete (FR-114, FR-115, SC-104) | integration and dev | 204 only when done; no item for the account or its player hashes; challenge shows "deleted player"; Cognito user gone; retry after an injected failure finishes |
| A11 | Sign out (FR-113) | e2e | Progress gone from the browser, new anonymous id; sign in again brings it back |
| A12 | Logs (FR-117) | integration: capture logs during A4 to A10 | No e-mail, name, code, token or IP |
| A13 | Lighthouse and axe (FR-118, SC-106) | lhci mobile and desktop, axe light and dark, local and dev | 100 x4 on every page including /account; no violation |
| A14 | Sign-in service down (FR-121) | e2e with the fake returning 503 | Game playable; account page says sign-in is unavailable |
| A15 | Inactive deletion (FR-120) | integration with a mocked clock | Warning at 23 months, deletion at 24 |
