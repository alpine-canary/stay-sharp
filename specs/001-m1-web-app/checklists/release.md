# Release checklist: M1 validation scenarios V1 to V18

Task T121. Each scenario from [quickstart.md](../quickstart.md), with the date it was run, where,
and the result. "Local" means DynamoDB Local and the Vite dev server; "dev" means the deployed
dev stage. A scenario counts as passed for release only when it passed where the quickstart says.

| # | Scenario | Date | Where | Result |
|---|---|---|---|---|
| V1 | Daily by keyboard, feedback, resume after reload | 2026-11-05 | local, mobile and desktop | Pass |
| V2 | Answers invisible before answering | 2026-11-05 | local: view allowlist unit tests, `leak` e2e; content check on the 20 fixture questions (`--days 70`) | Pass. Real content: not written yet (T122, T123) |
| V3 | Same answer twice counts once | 2026-11-05 | local (integration) | Pass |
| V4 | Speed bonus and relaxed | 2026-11-05 | local (unit and integration) | Pass |
| V5 | Streak, freeze, duplicates in the browser | 2026-11-05 | local (Vitest) | Pass |
| V6 | Challenge with two browsers | 2026-11-05 | local and dev, mobile and desktop | Pass |
| V7 | Publish rules | 2026-11-05 | local (unit and integration) | Pass |
| V8 | Scoring alarm (fault drill) | 2026-11-05 | dev | Pass: paging alarm in 71 s, clean log line (commit 7e82b8e) |
| V9 | Canary rollback (canary drill) | 2026-11-05 | dev | Pass: self-check stop in 132 s, alarm rollback in 190 s (commit 78b0c71) |
| V10 | Accessibility and Lighthouse | 2026-11-06 | local and dev | axe: no violation on any view, light and dark, local and dev; relaxed reachable before and during a play. Lighthouse on dev (new design, Junior level), mobile and desktop: 100 x4 on every page (home, play, practice, privacy). Locally, mobile performance still varies between 99 and 100 from run to run |
| V11 | Infra rules | 2026-11-05 | local (CDK assertions, 104 tests) | Pass |
| V12 | Budget | 2026-11-05 | local (CDK assertions) | Pass |
| V13 | Replay is not an answer key | 2026-11-05 | local (integration) | Pass |
| V14 | Practice cannot reach future content | 2026-11-05 | local (integration); practice route smoke-tested on dev | Pass |
| V15 | Storage failure paths | 2026-11-05 | local (integration) | Pass |
| V16 | Midnight | 2026-11-05 | local, mocked server clock | Pass |
| V17 | First question under 2 s on a throttled phone | 2026-11-06 | dev | Pass: 1.6 to 1.7 s (new design) |
| V18 | Public leak guard | 2026-11-05 | local (fingerprint unit tests) | Unit part passes. The push of a branch with a future prompt needs the GitHub repositories and secrets (maintainer) |

## Open before release

- **V18 end to end** and **T084, T093**: GitHub repositories, branch protection and secrets.
- **T119**: the manual keyboard and screen reader check by a person
  (`docs/accessibility-check.md`).
- **T122 to T124**: 140 questions written and approved by people, published to prod.
