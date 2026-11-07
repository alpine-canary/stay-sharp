# Runbook: accounts (M2)

Who: the maintainer. Where: the AWS account `stay-sharp`, region `eu-central-2`, SSO profile
`stay-sharp`. Replace `<stage>` with `prod` or `dev`. Nothing is changed by hand in the console.
Never paste an e-mail address, a code or a token into a ticket, a commit or a log.

## 1. A player asks by e-mail to delete their account

The page **Delete my account** does it in a minute; use this only when the player cannot sign
in (lost access to the address, or asks in writing).

1. Answer only from the address the account belongs to. If the request comes from another
   address, ask the player to write from the account's address, or to sign in and use the
   button. This is the only identity check: never ask for anything else.
2. Find the account's id (`sub`) from the address. The address stays in your terminal:

   ```sh
   aws cognito-idp list-users --profile stay-sharp --region eu-central-2 \
     --user-pool-id "$(aws cognito-idp list-user-pools --max-results 10 --profile stay-sharp \
       --region eu-central-2 --query "UserPools[?Name=='staysharp-<stage>'].Id" --output text)" \
     --filter 'email = "<the address>"' --query 'Users[].Username' --output text
   ```

   Nothing found: there is no account (or it was already deleted). Say so to the player.
3. Delete it with the same steps as the button (the account, its games, its progress, then the
   sign-in user), from the repository:

   ```sh
   AWS_PROFILE=stay-sharp STAGE=<stage> TABLE_NAME=staysharp-<stage> \
     USER_POOL_ID=<pool id> uv run --directory api python -c \
     "from staysharp import clock; from staysharp.store import deletion; \
      deletion.delete_account('<sub>', clock.now(), deletion.cognito_delete_user('<pool id>'))"
   ```

   If it stops half-way, run it again: every step can be repeated. The hourly job also finishes
   any deletion left half-way after 10 minutes.
4. Answer the player within 30 days (GDPR art. 12, nFADP art. 25): "Your Stay Sharp account and
   everything kept with it are deleted. Backups keep a copy for up to 35 days, then it is gone."
   Delete their e-mail from your mailbox when the exchange is over.

## 2. Alarm "StuckAccountDeletions"

An account deletion is still not finished an hour after it was asked. The hourly job
(`staysharp-<stage>-account-jobs`) retries every hour.

1. Look at the job's last runs (counts and error types only; never addresses):

   ```sh
   aws logs tail /aws/lambda/staysharp-<stage>-account-jobs --since 3h \
     --profile stay-sharp --region eu-central-2
   ```

2. `deletion still failing` with `error_type`:
   - `ClientError` from Cognito (throttling, outage): wait for the next hour.
   - Anything from DynamoDB: check the table's health and the alarms of the API.
   - Anything else: a bug. Reproduce with the integration tests
     (`api/tests/integration/test_deletion.py`), fix, release.
3. The alarm clears by itself when the job has finished the deletion.

## 3. Alarm "AccountJobsErrors"

The hourly job failed: a deletion, an inactivity warning or a deletion of an inactive account
still fails after the others were done. The log line names the step (`deletion still failing`,
`inactive account step failed`) with the account's hash and the error type. Same checks as
section 2. For `inactive account step failed` with an SES error, see section 4.

## 4. SES: bounces, complaints, paused sending

Code e-mails and the inactivity warning leave from `stay-sharp@lumineth.com` through SES in
`eu-central-2` (research A2). SES sends bounce and complaint notices by e-mail to that address:
keep the IONOS alias `stay-sharp@lumineth.com` that forwards to you (account-setup section 7).

- **Alarm "SesBounceRate" (4 %) or "SesComplaintRate" (0.08 %)**, prod only. SES pauses
  sending at 10 % bounces or 0.5 % complaints, and then nobody can sign in with a code
  (passkeys still work; the game still works without an account).
  1. Look at the notices forwarded by the alias: same address many times (a typo or a test
     loop), or many addresses (someone abusing the sign-up form).
  2. A loop or a bad address: SES keeps it on the account's suppression list, so it is not
     sent to again. Check:

     ```sh
     aws sesv2 list-suppressed-destinations --profile stay-sharp --region eu-central-2
     ```

  3. Abuse of the form (codes asked for addresses that never asked): sign-up calls go to
     Cognito directly, not through the web ACL. The sender function sends at most 5 codes an
     hour and 10 a day to one address, and 300 an hour in all (`staysharp.handlers.mail_sender`,
     log line `sign-in e-mail limited`). Lower these limits there and release if needed.
- **Sending paused** (`aws sesv2 get-account ... --query SendingEnabled` is `false`): answer
  AWS's case from the Support console with what you found and what changed, then wait for the
  review. Nothing to change in the code.
- **Players say no code arrives**: check the sender function's last runs:

  ```sh
  aws logs tail /aws/lambda/staysharp-<stage>-mail-sender --since 1h \
    --profile stay-sharp --region eu-central-2
  ```

  `sign-in e-mail sent` means SES accepted it: the mail is in the player's spam folder or held
  by their provider. `sign-in e-mail failed` with `error_type` names the cause (for example
  `MessageRejected` while the account is still in the SES sandbox).

## 5. Inactive accounts (FR-120)

Nothing to do: the hourly job warns an account 23 months after its last use and deletes it 24
months after, never sooner than 30 days after the warning. Signing in, opening the game signed
in or saving progress counts as use and cancels the warning. Sign-ups never confirmed are
removed after 7 days. The counts are the metrics `InactiveAccountsWarned` and
`InactiveAccountsDeleted` (namespace `StaySharp`).
