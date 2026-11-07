# Release check: optional accounts (M2)

Scenarios from `specs/002-accounts/quickstart.md`. "Local" runs on DynamoDB Local with the fake
sign-in; "dev" is https://d3fzlsqovr82ud.cloudfront.net with the real user pool and SES (still in
the SES sandbox). The machine running the checks on 2026-11-07 was heavily loaded (load average
10 to 80), which matters for the timing results below.

| # | Scenario | Date | Where | Result |
|---|---|---|---|---|
| A1 | No prompt before the first daily | 2026-11-07 | local | Pass (e2e, mobile and desktop) |
| A2 | Offer at streak 3, hidden 7 days after dismiss | 2026-11-07 | local | Pass (e2e: offer once, Not now hides it; unit: 6 days hidden, back after 7). The offer now loads only when due |
| A3 | Under 16 stores nothing | 2026-11-07 | local | Pass (e2e: no request to sign-in or API, storage unchanged) |
| A4 | Create with an e-mail code | 2026-11-07 | local and dev | Pass. Dev: the maintainer signed in with a real code sent from Zurich |
| A5 | Second browser merge | 2026-11-07 | local | Pass (integration). Since the review: two unfinished dailies never leave a replay beside an open daily, and "first finished" uses the finish time |
| A6 | Progress follows within 1 minute | 2026-11-07 | local | Pass (e2e, two contexts) |
| A7 | Version conflict | 2026-11-07 | local | Pass (integration); a second conflict while joining is left for the next sync (unit) |
| A8 | Passkey add and sign in | 2026-11-07 | local | Pass (virtual authenticator). Dev: passkeys on since 2026-11-07, **not yet tried on a real device** |
| A9 | Wrong or expired code | 2026-11-07 | local | Pass (e2e, plain refusal). Dev: **not yet tried** |
| A10 | Delete | 2026-11-07 | local | Pass (integration and e2e, retry after an injected failure; deletion races covered since the review). Dev: **not yet tried** (it deletes the maintainer's dev account) |
| A11 | Sign out | 2026-11-07 | local | Pass (e2e: new anonymous id, tokens and sync state gone, sign-in brings the progress back) |
| A12 | Logs | 2026-11-07 | local and dev | Pass. Integration test over a whole account life (it found and fixed botocore DEBUG dumps). Dev: no log line holds the address |
| A13 | Lighthouse and axe | 2026-11-07 | local and dev | axe: no violation on any account screen, light and dark. Lighthouse on dev, desktop: 100 x4 on every page, /account included. Mobile: accessibility, best practices and SEO 100 everywhere; performance 97 to 100 from run to run on the same build (home 100 then 98), so to measure again on a quiet machine |
| A14 | Sign-in service down | 2026-11-07 | local | Pass (e2e: the daily plays and scores; the account page says sign-in is not available) |
| A15 | Inactive deletion | 2026-11-07 | local and dev | Pass (integration, mocked clock: warning at 23 months, deletion at 24, never sooner than 30 days after the warning). Dev: the hourly job runs without error |

Also checked on dev on 2026-11-07:

- Full e2e suite against dev: 25 passed. V17 (first question under 2 s on a throttled phone)
  measured 1.81 to 2.05 s, against 1.6 to 1.7 s on 2026-11-06. M2 adds about 2.6 KB gzipped to
  the first load (about 15 ms at that speed); the rest follows the machine's load. To measure
  again on a quiet machine before prod.
- First-screen size: 85 147 B gzipped, within the budget in `front/bundle-budget.json`.

Left for the maintainer on dev (one phone, a few minutes): add a passkey, sign out, sign in
with the passkey (A8); type a wrong code once (A9); delete the account (A10).
