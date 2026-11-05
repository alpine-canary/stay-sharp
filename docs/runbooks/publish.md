# Runbook: write, approve, schedule and publish questions

Who: the maintainer. Questions for today or a later day live only in the private repository
`stay-sharp-content`. They never go into this public repository, its history, its build output
or any public place (FR-024b). The publish code lives here (`api/src/staysharp/publish/`); the
content repository installs it as a package.

## 1. Layout of the content repository

```
stay-sharp-content/
  pyproject.toml            installs staysharp[publish] from this repository, pinned to a commit
  questions/<level>/<id>.yaml
  schedules/<level>/schedule.yaml
  fixtures/                 fake content for dev, with a .fixtures file at its root
  .github/workflows/        validate, leak check, publish
```

## 2. Write

One file per question, in the format of `specs/001-m1-web-app/contracts/question.schema.json`:
`id`, `level`, `deck`, `prompt`, four `choices`, `answer.choice` (and `answer.lines` for Spot the
bug), `explanation`, and `source` (`url`, `date`) for AI this week.

- The id is stable and means nothing: no date, weekday, month or week number (`news_mcp_auth`, not
  `news_2026_12_01`). Publish refuses date-like ids.
- Starter questions follow FR-024a: readers from 12, plain words, no brand promotion, sources
  suitable for that age.
- A new question starts with `status: draft`. Drafts are validated but never published.

## 3. Approve

Set `status: approved`, `approved_by` and `approved_at`. A Starter question also needs
`second_reader`: someone other than the author has read it. Only approved questions are published
(FR-025). No question text is written by a model in M1.

## 4. Schedule

`schedules/<level>/schedule.yaml` lists five ids per date in the deck order of FR-001 (senior:
spot, better, fail, acronym, news; starter: logic, readcode, whatif, words, aisense) and a target
time in seconds for every deck. A question is scheduled on one date only. Samples and anything
already public (`daily_eligible: false`) are never scheduled (FR-024c).

Keep past dates in the file: publish checks that they still match what was published.

## 5. Publish

1. Open a pull request in the content repository. CI runs:
   - `python -m staysharp.tools.publish validate . --stage prod` (reads the stored versions, so an
     edit without a new `change_reason` is caught before the merge);
   - `python -m staysharp.tools.publish leak-check .` (layer 1 of the leak guard, below).
2. Merge to `main`. CI runs, with the content role (OIDC, content keys of the table only):
   - `publish apply . --stage prod`: all or nothing. Every check runs before the first write;
     writes go in transactions of at most 100 items, questions first, then whole days.
   - `publish leak-check . --record`: on success it writes the time to
     `/staysharp/prod/leak-guard/last-pass`. The prod deploy refuses to run when that is missing
     or older than 24 hours.
   - `publish fingerprints . --out fingerprints.json`, then uploads it to
     `s3://<LEAK_GUARD_BUCKET>/leak-guard/fingerprints.json` for the public scan.
3. Read the counts it prints (question versions, days written, unchanged). Output never contains
   question text.

If apply prints `refused`, nothing was written: fix each `id: reason` and push again. If it
prints `failed` (a transaction failed), the earlier transactions are written and no set points
at a missing question. Re-run the job: unchanged questions and days are skipped.

Dev only takes fixture content: `publish apply fixtures --stage dev`. The command refuses a folder
without `.fixtures` for dev, and a folder with it for prod.

## 6. Edit a published question

Change the file and add a new `change_reason` (different from the previous one). Publish writes
version n+1 with the time and the reason (FR-027). Grades already given never change: they are
stored on the player's answers, which publish never reads or writes. Choice ids stay the same.

- Today and past days cannot change. A past or today's set keeps the version it was published
  with; the new version is used by future sets and new practice entries.
- A future day can change: publish rewrites its set and removes the old practice entries.
- Level and deck of an id never change; write a new question instead.
- Changing only approval fields is not a new version.

## 7. When a question may be copied here

Only after its day has passed (FR-024b). The public leak scan (layer 2) fails any pull request or
push that contains text of a question scheduled for today or later, in a file or anywhere in the
history.

If the scan finds one, its text is already public: deleting the file does not remove it from the
history. Treat the question as leaked. In the content repository, set `daily_eligible: false`,
schedule another question in its place, and publish (a future day can change). The next
fingerprint file no longer lists it and the scan passes. If the day is today, the set cannot
change: note it and let the day pass.

## 8. The two leak-guard layers (research R4)

| Layer | Where | What |
|---|---|---|
| 1 | content CI, offline | Runs the API's own view builder over every question of today + 7 days and fails if the view carries the explanation, the source link, an answer field or any field outside the allowlist. |
| 2 | public CI and every release | HMAC digests of 12-word shingles of each future prompt, code, correct choice and explanation. The scan reads every tracked file and every blob of the full history and prints paths and counts only. |

The key `LEAK_GUARD_KEY` is an Actions secret in both repositories (the same value; generate it
with `openssl rand -hex 32`). Fork pull requests get no secret: they are skipped and scanned again
on the push to `main` after the merge.

## 9. Stock warning

The stock check runs every morning (05:00 UTC). It counts, per level, the days in a row from
tomorrow that have a published set. The alarm "StockLowSenior" or "StockLowStarter" e-mails you
when that is below 7 (prod), or when no value arrived. To clear it, write, approve, schedule and
publish more days. "StockCheckMissed" means the check did not run at all: look at the function
`staysharp-<stage>-stock-check` and its EventBridge rule.

## 10. One-time setup

| Where | Name | Value |
|---|---|---|
| both repositories, secret | `LEAK_GUARD_KEY` | the same random 32-byte hex key |
| both repositories, variable | `LEAK_GUARD_BUCKET` | the `FingerprintBucketName` output of `staysharp-account` |
| content repository, variable | `AWS_CONTENT_ROLE_ARN` | the role `staysharp-github-contentpublish` |
| content repository, variable | `LAUNCH_DATE` | the day of game #1 |

Set `LEAK_GUARD_BUCKET` in this repository only after the content repository has uploaded its
first fingerprint file: the leak-guard job is skipped until then.
