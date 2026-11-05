# Runbook: restore the table after lost or damaged data

Who: the maintainer. Where: the AWS account `stay-sharp`, region `eu-central-2`, SSO profile
`stay-sharp`. Research R17.

Point-in-time recovery (PITR) is on for `staysharp-dev` and `staysharp-prod` (CDK,
`infra/stacks/data_stack.py`). It can restore the table as it was at any second of the last
35 days, always into a **new** table. The prod table has deletion protection.

## When to use it

- A bad release or a script wrote wrong data, or deleted items it should not have.
- Content items (`Q#`, `DAILY#`, `POOL#`, `STOCK#`) are owned by publish: for those, publishing
  again from the content repository is usually simpler than a restore.

## 1. Pick the restore point

The last second **before** the damage, in UTC. Check what PITR allows:

```sh
aws dynamodb describe-continuous-backups --table-name staysharp-prod \
  --profile stay-sharp --region eu-central-2 \
  --query "ContinuousBackupsDescription.PointInTimeRecoveryDescription"
```

## 2. Restore into a side table

```sh
aws dynamodb restore-table-to-point-in-time --source-table-name staysharp-prod \
  --target-table-name staysharp-prod-restore-<yyyymmdd> \
  --restore-date-time <yyyy-mm-ddThh:mm:ssZ> --billing-mode-override PAY_PER_REQUEST \
  --profile stay-sharp --region eu-central-2 --query "TableDescription.TableStatus"
```

Wait until the side table is `ACTIVE` (several minutes; the dev drill took the time recorded
below). The side table has no TTL and no PITR, and is not in CDK: it is temporary.

## 3. Compare

Count both tables (exact counts; `describe-table` counts are up to 6 hours old):

```sh
for t in staysharp-prod staysharp-prod-restore-<yyyymmdd>; do
  aws dynamodb scan --table-name "$t" --select COUNT --profile stay-sharp \
    --region eu-central-2 --query Count --output text
done
```

With more than 1 MB of data the scan pages; add `--page-size 1000` and sum the counts, or rely on
the copy tool's dry run below, which reads the whole snapshot.

## 4. Copy the snapshot back into the live table

The live table keeps everything CDK set (TTL, PITR, alarms, permissions); only items are put
back. Items written after the restore point and absent from the snapshot stay.

```sh
AWS_PROFILE=stay-sharp AWS_REGION=eu-central-2 uv run --directory api \
  python -m staysharp.tools.restore_copy --source staysharp-prod-restore-<yyyymmdd> \
  --target staysharp-prod            # dry run: counts only
# then, the same with --write
```

The tool prints counts only, never keys or values. Writing needs `dynamodb:BatchWriteItem` on the
live table: use the maintainer's SSO role, not a CI role.

## 5. Clean up

```sh
aws dynamodb delete-table --table-name staysharp-prod-restore-<yyyymmdd> \
  --profile stay-sharp --region eu-central-2 --query "TableDescription.TableStatus"
```

Write down the date, the restore point, the counts and what was wrong in the incident notes.

## Drill log

| Date | Stage | Restore point | Live items | Restored items | Time to ACTIVE | Copy dry run | Cleaned up |
|---|---|---|---|---|---|---|---|
| 2026-11-05 | dev | latest restorable (12:37 UTC) | 252 | 252 | about 3 minutes | 252 items; `--write` also run, 252 after | yes |
