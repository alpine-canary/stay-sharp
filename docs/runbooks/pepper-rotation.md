# Runbook: rotate the pepper

Who: the maintainer. Where: the AWS account `stay-sharp`, region `eu-central-2`, SSO profile
`stay-sharp`. Research R16.

## What the pepper is for

One secret per stage, `staysharp/<stage>/pepper` in Secrets Manager (CDK,
`infra/stacks/data_stack.py`). The API turns each anonymous player id into
`HMAC-SHA256(pepper, playerId)`:

- in logs (`player_hash`), so logs never hold the raw id;
- in challenges (`ownerHash` and the `R#<playerHash>` result keys), so a challenge never holds it.

## What rotating breaks

After a rotation the same player gets a new hash. So:

- **live challenges break**: the owner is no longer recognised as the owner, and a colleague who
  finished is shown as "not finished yet". Challenges last 30 days.
- log lines before and after the rotation can no longer be matched to the same player. That is
  acceptable: logs are kept one month.

Plays, answers, practice and local progress are keyed by the raw id and are not affected.

## When

Only when the pepper may have leaked (for example it appeared in a log, a ticket or a terminal
recording), or once a year as hygiene. Never as a reflex.

## Steps

1. **Announce it 30 days ahead**, on the site's news and wherever the game is shared: "On <date>,
   challenge links created before <date> stop working." In a real leak, rotate at once and say
   so the same day instead.
2. **Dev first.** Rotate dev, play a daily and a challenge with two browsers, and check the logs
   show `player_hash` values (and still no raw id):

   ```sh
   aws secretsmanager put-secret-value --secret-id staysharp/dev/pepper \
     --secret-string "$(openssl rand -hex 32)" --profile stay-sharp --region eu-central-2 \
     --query VersionId
   ```

   The value is generated in the command and never printed. The API reads the pepper once per
   cold start, so force new cold starts by publishing a new version (deploy the API stack again
   with the same code, or wait until idle instances are recycled).
3. **Prod**, on the announced date, with the same command on `staysharp/prod/pepper`, then a
   deploy of `staysharp-prod-api` so every instance reads the new value.
4. Watch `ChallengesOpened` and the 4xx rate for a day; a rise of "not finished yet" on old
   links is expected.

Secrets Manager keeps the previous version as `AWSPREVIOUS`. Going back
(`update-secret-version-stage`) restores old challenges only if no challenge was created in
between; prefer going forward.

## Log

| Date | Stage | Reason | Announced on | Checked by |
|---|---|---|---|---|
