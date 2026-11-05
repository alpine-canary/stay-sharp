# Data model: M1 - public daily game without accounts

**Date**: 2026-11-03 (revised after the plan audit) | **Spec**: [spec.md](./spec.md) |
**Research**: [research.md](./research.md)

One DynamoDB table per stage, `staysharp-<stage>` (on-demand, PITR on, deletion protection on in
prod, TTL attribute `expiresAt`). Keys are strings. Dates are `YYYY-MM-DD` in Europe/Zurich;
timestamps are UTC ISO 8601 with milliseconds. TTL deletion can lag up to about two days, so every
read that depends on expiry compares `expiresAt` with now.

## Access patterns

| # | Pattern | Key | Used by |
|---|---|---|---|
| A1 | Daily set for a date and level | `PK=DAILY#<date>#<level>`, `SK=SET` | start, open |
| A2 | A question at a given version | `PK=Q#<qid>`, `SK=V#<n>` | open, answer, practice |
| A3 | A player's play | `PK=P#<playerId>`, `SK=PLAY#<playId>` | start, resume, result |
| A4 | A player's answer to one question of a play | `PK=P#<playerId>`, `SK=ANS#<playId>#<index>` | open, answer |
| A5 | A practice attempt | `PK=P#<playerId>`, `SK=PRA#<attemptId>` | practice |
| A6 | A challenge and its results | `PK=CH#<challengeId>`, `SK=META` / `SK=R#<playerHash>` | challenge |
| A7 | Past published questions of a deck (practice pool) | Query `PK=POOL#<level>#<deck>`, `SK < <today>` | practice next |
| A8 | Future days with a complete set | Query `PK=STOCK#<level>`, `SK > <today>` | stock check |
| A9 | Return rate (SC-010), monthly | Read-only scan of `PLAY#` items, counted offline by player hash | report script |

`playId` = `<date>.<level>.<mode>`, mode `daily` or `replay`, scoped by the player key.

## Entities

### Question (`Q#<qid>` / `V#<n>`)

| Field | Type | Rules |
|---|---|---|
| qid | string | `^[a-z0-9_]{3,64}$`, unique, no date-like pattern |
| version | int | 1, 2, ...; each edit is a new item (no `V#CURRENT`, S11) |
| level | enum | `senior`, `starter` (later `mid`, `lead`) |
| deck | enum | senior: `spot`, `better`, `fail`, `acronym`, `news`; starter: `logic`, `readcode`, `whatif`, `words`, `aisense` |
| prompt, code, language | | as in `contracts/question.schema.json` |
| choices | list[4] | `{id, text}`; `id` = 8 random base32 characters assigned at the first publish and kept across versions; order shuffled at the first publish |
| choiceOrder | list[4] | the choice ids in authoring order, so later versions keep the ids (never sent) |
| answerChoiceId, answerLines | | lines within `1..lines(code)` |
| explanation | string | |
| sourceUrl, sourceDate | | required for `news`, and for `aisense` when citing a fact |
| dailyEligible | bool | false for samples and prototype questions |
| approvedBy, approvedAt, secondReader | | `secondReader` required for Starter |
| changeReason | string? | required from version 2 |
| publishedAt | timestamp | when this version was written (FR-027: date and reason of each edit) |

Never returned before an answer: `answerChoiceId`, `answerLines`, `explanation`, `sourceUrl`,
`sourceDate`, and none of the authoring fields (R1 allowlist).

### Daily set (`DAILY#<date>#<level>` / `SET`)

`gameNumber`; `items[5]` = `{index, deck, qid, version, targetSeconds}` in FR-001 order;
`publishedAt`. Written only by publish; publish refuses changes to today or past days.

### Play (`P#<playerId>` / `PLAY#<playId>`)

| Field | Type | Rules |
|---|---|---|
| date, level, mode | | |
| relaxed | bool | false at start unless asked; can go false -> true at any time, never back |
| relaxedFrom | int? | index of the first question played relaxed |
| challengeId | string? | set when started from a challenge link |
| startedAt | timestamp | |
| answered | string set | indexes graded so far, added with `ADD` (C1) |
| grades | map | index -> 0, 0.5 or 1 |
| score, bonus, elapsedMs | number | added with `ADD` |
| expiresAt | epoch s | startedAt + 90 days |

`finished` = `size(answered) = 5`, derived. States: `started` -> `in_progress` -> `finished`.
A `replay` play for today is refused until the `daily` play of that date and level is finished
(C3).

### Answer (`P#<playerId>` / `ANS#<playId>#<index>`)

`qid`, `version` (copied from the daily set at open), `servedAt` (written once), `choiceId`,
`line`, `grade`, `bonus`, `answeredAt`, `elapsedMs`, `expiresAt` = the play's `expiresAt` (same
base time as the play, W1). States `served` -> `graded`. Transaction and cancellation table:
research R2.

### Practice attempt (`P#<playerId>` / `PRA#<attemptId>`)

Same fields as Answer plus `deck`. `attemptId` = random id from `practice/next`. At most 200
attempts per player per day (counter item `PRACOUNT#<date>`, conditional `ADD`). `expiresAt` = 14
days (S5).

### Challenge (`CH#<challengeId>`)

| Item | Fields |
|---|---|
| `META` | `date`, `level`, `ownerHash` = HMAC(pepper, playerId), `owner` snapshot `{grades[5], score, bonus, elapsedMs, relaxed}`, `results` (count), `createdAt`, `expiresAt` (30 days) |
| `R#<playerHash>` | colleague snapshot, written in the same transaction as their fifth answer (R2), `attribute_not_exists`; `META.results < 50` checked in the same transaction |

`challengeId` = 12 random base32 characters, stored on the owner's play; creating it twice
returns the same id. `GET` compares `expiresAt` with now and answers `expired` (W4). A colleague
who already finished that set gets their snapshot written from their existing play on first
view (spec Story 4, 3a).

### Practice pool (`POOL#<level>#<deck>` / `<date>#<qid>`)

Payload: `version`. Written by publish for every question of a published day; read only with
`SK < today`. Prototype questions are written with their original dates (2026-10-23 to
2026-11-05) and `dailyEligible = false`.

### Stock (`STOCK#<level>` / `<date>`)

One marker per published complete set.

### Local progress (browser, `localStorage` key `staysharp.v1`)

`{ playerId, level, relaxed, days: {<level>: {<playDate>: {score, bonus, relaxed}}},
freeze: {<level>: {held, earnedWeek, usedOn[]}}, longest: {<level>: n},
deckStats: {<level>: {<deck>: {answered, correct}}}, boxes: {<qid>: 1..5} }`. Answers marked
`duplicate` are never counted. Streak, longest and freeze are derived from `days` by
`front/src/progress/streak.ts` (replayed in date order, so they cannot drift); the stored
`freeze` and `longest` fields are kept for the shape check only. `correct` counts halves. Versioned; broken data is reset with a message, never a crash.

## Validation summary

- Pydantic models match `contracts/openapi.yaml`; unknown fields rejected; body over 2 KB refused
  at the edge (WAF) and again in the Lambda.
- `X-Player-Id` must be a UUIDv4.
- `line` must be within the line count of the served question version (not only <= 30).
- Dates: research R6.
- Content: `contracts/question.schema.json`, `contracts/schedule.schema.json`, plus the publish
  checks in research R4.
