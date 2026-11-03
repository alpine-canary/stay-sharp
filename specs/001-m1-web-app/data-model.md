# Data model: M1 - public daily game without accounts

**Date**: 2026-11-03 | **Spec**: [spec.md](./spec.md) | **Research**: [research.md](./research.md)

One DynamoDB table `stay-sharp-<env>` (on-demand, point-in-time recovery on, deletion protection
on in prod, TTL attribute `expiresAt`). Keys are strings. Dates are `YYYY-MM-DD` in
Europe/Zurich; timestamps are UTC ISO 8601 with milliseconds.

## Access patterns

| # | Pattern | Key | Used by |
|---|---|---|---|
| A1 | Daily set for a date and level | `PK=DAILY#<date>#<level>`, `SK=SET` | open, pre-traffic check |
| A2 | A question, current version | `PK=Q#<qid>`, `SK=V#CURRENT` | open, answer |
| A3 | A question, given version | `PK=Q#<qid>`, `SK=V#<n>` | answer (grades against the version that was served) |
| A4 | A player's play | `PK=P#<playerId>`, `SK=PLAY#<playId>` | start, resume, result |
| A5 | A player's answer to one question of a play | `PK=P#<playerId>`, `SK=ANS#<playId>#<index>` | open, answer |
| A6 | A practice attempt | `PK=P#<playerId>`, `SK=PRA#<attemptId>` | practice open, answer |
| A7 | A challenge and its results | `PK=CH#<challengeId>`, `SK=META` and `SK=R#<playerHash>` | challenge create, view |
| A8 | Past published days of a deck (practice pool) | `PK=POOL#<level>#<deck>`, `SK=<date>#<qid>` | practice next |
| A9 | Days with a complete set ahead | Query `PK=STOCK#<level>`, `SK >= today` | stock check |

`playId` = `<date>.<level>.<mode>` (`mode` = `daily` or `replay`; scoped by the player key, so it
needs no randomness). A challenge played on a past date uses mode `replay` with
`challengeId` stored on the play.

## Entities

### Question (`Q#<qid>` / `V#<n>` and `V#CURRENT`)

| Field | Type | Rules |
|---|---|---|
| qid | string | `^[a-z0-9_]{3,64}$`, unique |
| version | int | starts at 1; each edit writes a new version |
| level | enum | `senior`, `starter` (later `mid`, `lead`); `selftest` for the hidden self-test set |
| deck | enum | senior: `spot`, `better`, `fail`, `acronym`, `news`; starter: `logic`, `readcode`, `whatif`, `words`, `aisense` |
| prompt | string | 1-400 chars |
| code | string? | up to 30 lines, 100 chars per line; required for `spot`, `better`, `readcode` |
| language | enum? | `python`, `typescript`, `php`, `sql`, `cdk`, `text` |
| choices | list | exactly 4, each `{id, text}`; `id` = 8 random base32 chars assigned at publish; order shuffled at publish |
| answerChoiceId | string | one of `choices[].id` |
| answerLines | list[int]? | required for `spot`, each within `1..lines(code)` |
| explanation | string | 1-1200 chars |
| sourceUrl, sourceDate | string? | required for `news` and `aisense` when they cite a fact; `https` only |
| status | enum | only `approved` is publishable |
| approvedBy, approvedAt | string | from the content repository commit |
| changeLog | list | `{version, at, reason}` |

Never returned by `open`: `answerChoiceId`, `answerLines`, `explanation`, `sourceUrl`,
`sourceDate`, `status`, `approvedBy`, `changeLog`.

### Daily set (`DAILY#<date>#<level>` / `SET`)

| Field | Type | Rules |
|---|---|---|
| date, level | | |
| gameNumber | int | days since launch day + 1, same at every level |
| items | list[5] | `{index, deck, qid, version, targetSeconds}`, decks in the fixed order of FR-001 |
| publishedAt | timestamp | |

Written only by the publish step. Immutable once its date has started (publish refuses changes
to today or past days).

### Play (`P#<playerId>` / `PLAY#<playId>`)

| Field | Type | Rules |
|---|---|---|
| date, level, mode | | mode `daily` or `replay` |
| relaxed | bool | fixed at start |
| challengeId | string? | set when started from a challenge link |
| startedAt | timestamp | |
| answeredMask | int | bit i set when question i is graded |
| grades | map | index -> 0, 0.5 or 1 |
| score | number | sum of grades, 0-5, half steps |
| bonus | number | sum of bonuses, 0-1.0, steps of 0.2 |
| elapsedMs | int | sum over answered questions |
| finishedAt | timestamp? | set by the transaction that sets the last bit |
| expiresAt | epoch s | startedAt + 90 days |

State: `started` -> `in_progress` (1-4 bits) -> `finished` (5 bits). No transition back.

### Answer (`P#<playerId>` / `ANS#<playId>#<index>`)

| Field | Type | Rules |
|---|---|---|
| qid, version | | copied from the daily set at open |
| servedAt | timestamp | written once by open (`if_not_exists`) |
| choiceId, line | | written once by answer |
| grade | number | condition `attribute_not_exists(grade)` |
| bonus | number | 0 or 0.2 |
| answeredAt, elapsedMs | | |
| expiresAt | epoch s | 90 days |

State: `served` -> `graded`. A second answer with the same `choiceId` and `line` returns the
stored grade; a different one is refused (`409`).

### Practice attempt (`P#<playerId>` / `PRA#<attemptId>`)

Same fields as Answer, plus `deck`. `attemptId` is a random id issued by `practice/next`.
Expires after 90 days. Never touches a Play.

### Challenge (`CH#<challengeId>`)

| Item | Fields |
|---|---|
| `META` | `date`, `level`, `ownerHash` (SHA-256 of the challenger's player id with a per-environment pepper), `owner` result snapshot `{grades[5], score, bonus, elapsedMs, relaxed}`, `createdAt`, `expiresAt` (30 days) |
| `R#<playerHash>` | result snapshot of a colleague who finished the set, written when their play finishes; at most 50 per challenge |

`challengeId` = 12 random base32 characters. Creating a challenge twice for the same play
returns the same id (stored on the play).

### Practice pool (`POOL#<level>#<deck>` / `<date>#<qid>`)

Written by the publish step for every question of a published day, readable by practice only
when `date < today`. Prototype questions are written here with date `2026-10-23` to
`2026-11-05` and never appear in a daily set (FR-024c).

### Stock (`STOCK#<level>` / `<date>`)

One marker item per published complete daily set; `stock_check` counts markers from today and
publishes `StockDaysAhead`.

### Local progress (browser only, `localStorage` key `staysharp.v1`)

`{ playerId, level, relaxed, days: { "<level>": { "<date>": {score, bonus, finished: true} } },
freeze: { "<level>": {held: bool, earnedWeek, usedOn[]} }, longest: {"<level>": n},
deckStats: {"<level>": {"<deck>": {answered, correct}}}, boxes: {"<qid>": 1..5} }`.
Versioned; unknown or broken data is reset with a message, never a crash.

## Validation summary

- Every request body is validated by Pydantic models matching `contracts/openapi.yaml`; unknown
  fields are rejected; body size limit 2 KB.
- `X-Player-Id` must be a UUIDv4.
- `open` and `answer` for mode `daily` accept `date` = today, or yesterday when the play was
  started yesterday (R6). Future dates are always refused.
- Question files are validated against `contracts/question.schema.json` before publish.
