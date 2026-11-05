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
| V6 | Challenge with two browsers | 2026-11-05 | local, mobile and desktop; API routes smoke-tested on dev | Pass locally. On dev: pending, the dev site needs the edge stack (WAF) deployed first |
| V7 | Publish rules | 2026-11-05 | local (unit and integration) | Pass |
| V8 | Scoring alarm (fault drill) | 2026-11-05 | dev | Pass: paging alarm in 71 s, clean log line (commit 7e82b8e) |
| V9 | Canary rollback (canary drill) | 2026-11-05 | dev | Pass: self-check stop in 132 s, alarm rollback in 190 s (commit 78b0c71) |
| V10 | Accessibility and Lighthouse | 2026-11-05 | local preview build | axe: no violation on any view, light and dark; relaxed reachable before and during a play. Lighthouse desktop: 100 x4 on every page. Lighthouse mobile: Accessibility, Best Practices, SEO 100; **Performance 98 to 99 (fails the 100 target)**. Against dev: pending |
| V11 | Infra rules | 2026-11-05 | local (CDK assertions, 104 tests) | Pass |
| V12 | Budget | 2026-11-05 | local (CDK assertions) | Pass |
| V13 | Replay is not an answer key | 2026-11-05 | local (integration) | Pass |
| V14 | Practice cannot reach future content | 2026-11-05 | local (integration); practice route smoke-tested on dev | Pass |
| V15 | Storage failure paths | 2026-11-05 | local (integration) | Pass |
| V16 | Midnight | 2026-11-05 | local, mocked server clock | Pass |
| V17 | First question under 2 s on a throttled phone | - | dev only | Not run: needs the new site on dev |
| V18 | Public leak guard | 2026-11-05 | local (fingerprint unit tests) | Unit part passes. The push of a branch with a future prompt needs the GitHub repositories and secrets (maintainer) |

## Open before release

- **V10 mobile performance**: first paint waits for the JavaScript bundle (81 KB compressed), so
  first contentful paint is 1.7 to 2.0 s under Lighthouse's mobile throttling. Reaching 100 needs
  the first screen in the HTML itself (a prerendered shell), not a tweak. Not started.
- **V6, V10, V17 on dev**: deploy `staysharp-edge` (WAF), then the dev site, then run
  `BASE_URL=<dev> pnpm --dir front test:e2e` and the Lighthouse step of the deploy workflow.
- **V18 end to end** and **T084, T093**: GitHub repositories, branch protection and secrets.
- **T119**: the manual keyboard and screen reader check by a person
  (`docs/accessibility-check.md`).
- **T122 to T124**: 140 questions written and approved by people, published to prod.
