# Data model: Optional accounts (M2)

Same single DynamoDB table as M1. New items only; M1 items keep their keys. `<sub>` is the
Cognito user id (opaque); `<ph>` is the M1 player hash (HMAC of the player id with the pepper).

| Item | PK | SK | Attributes | Notes |
|---|---|---|---|---|
| Account | `ACC#<sub>` | `META` | `primaryPlayer` (player id), `primaryHash` (`<ph>`), `displayName?`, `adult` (true), `createdAt`, `lastActiveMonth`, `state` (`active` or `deleting`), `warnedAt?` | No e-mail: Cognito holds it. `lastActiveMonth` feeds the sparse index `GSI_INACTIVE` (PK `lastActiveMonth`) |
| Player link | `PLY#<ph>` | `ACCOUNT` | `sub` | One per player id adopted, so a merge or deletion finds every id |
| Progress copy | `ACC#<sub>` | `PROGRESS` | `version` (number), `body` (JSON, at most 64 KB), `updatedAt` | Conditional write on `version` |
| Merge record | `ACC#<sub>` | `MERGE#<ph>` | `doneAt`, `moved` (count), `replays` (count) | Makes a merge idempotent; kept 30 days (TTL) |

## Rules

- **Validation**: display name 2 to 24 characters, `^[\p{L}\p{N} _-]+$`, no `http`, no `www.`,
  checked against a small blocked-words list; progress body validated against the progress
  schema (`contracts/progress.schema.json`) and its size.
- **Create** (`POST /me/adopt` with no account yet): conditional put of `ACC#<sub>/META`
  (`attribute_not_exists`), player link, progress copy version 1, in one transaction.
- **Adopt another browser** (`POST /me/adopt` with an anonymous player id): if `MERGE#<ph>`
  exists, return the stored result; else re-key that id's plays and answers to the primary
  hash (first finished daily per date and level wins; the other becomes a replay record), write
  the player link and the merge record. Each moved play is one transaction; the merge record is
  written last.
- **State**: `active` -> `deleting` -> (deleted). A `deleting` account refuses every request
  except `DELETE /me`.
- **Delete**: by key, from the player links: plays, answers, practice records, progress copy,
  merge records, player links, account; challenge results of those player hashes are rewritten
  as "deleted player"; then the Cognito user.
- **Logs**: `sub` is never logged in full; logs carry `account_hash` (HMAC of `sub`) and
  `player_hash`, as M1.
