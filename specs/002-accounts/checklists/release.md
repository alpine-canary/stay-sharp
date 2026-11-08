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
| A8 | Passkey add and sign in | 2026-11-07 | local and dev | Pass (virtual authenticator locally; on dev the maintainer added a passkey on a real device and signed in with it) |
| A9 | Wrong or expired code | 2026-11-07 | local and dev | Pass (e2e, plain refusal; the maintainer on dev). A wrong code now also offers a passkey where the device has one, whether or not the address has an account |
| A10 | Delete | 2026-11-07 | local and dev | Pass (integration and e2e, retry after an injected failure; deletion races covered since the review). Dev: the maintainer deleted their account; the log says `account deleted` and the user pool is empty |
| A11 | Sign out | 2026-11-07 | local | Pass (e2e: new anonymous id, tokens and sync state gone, sign-in brings the progress back) |
| A12 | Logs | 2026-11-07 | local and dev | Pass. Integration test over a whole account life (it found and fixed botocore DEBUG dumps). Dev: no log line holds the address |
| A13 | Lighthouse and axe | 2026-11-07 | local and dev | axe: no violation on any account screen, light and dark. Lighthouse on dev, desktop: 100 x4 on every page, /account included. Mobile: accessibility, best practices and SEO 100 everywhere; performance 97 to 100 from run to run on the same build. Measured again at 22:45 (load 18 to 41): every page 97 to 100, and the home page 100 then 98 with the same HTML, CSS and scripts as /account; the lost points are first paint (1.3 s against 1.7 s) moving with the machine's load. To confirm 100 on a quiet machine |
| A14 | Sign-in service down | 2026-11-07 | local | Pass (e2e: the daily plays and scores; the account page says sign-in is not available) |
| A15 | Inactive deletion | 2026-11-07 | local and dev | Pass (integration, mocked clock: warning at 23 months, deletion at 24, never sooner than 30 days after the warning). Dev: the hourly job runs without error |

Also checked on dev on 2026-11-07:

- Full e2e suite against dev: 25 passed. V17 (first question under 2 s on a throttled phone)
  measured 1.81 to 2.05 s at load 20 to 90. Measured again at 22:43 (load 18 to 27): 1.725,
  1.714 and 1.752 s, three passes, against 1.6 to 1.7 s on 2026-11-06. M2 adds about 2.6 KB
  gzipped to the first load (about 15 ms at that speed).
- First-screen size: 85 147 B gzipped, within the budget in `front/bundle-budget.json`.

All 15 scenarios pass on 2026-11-07. Still to do before prod: mobile Lighthouse performance 100 confirmed
on a quiet machine, SES production access (refused once; on 2026-11-08 the alias `stay-sharp@lumineth.com` was
created and a test e-mail through it arrived, the CLI refused a second request with
ConflictException, and the maintainer answered the refused case in the Support Center, pointing to the live preview since the final domain does not exist yet), and the maintainer's approval (T251).
