# Runbook: roll back a bad release

Who: the maintainer. Where: the AWS account `stay-sharp`, region `eu-central-2`, SSO profile
`stay-sharp`. Everything below goes through CDK or the CLI; nothing is changed by hand in the
console (an emergency change is written back into code the same day).

## 1. What happens by itself

| Moment | What stops a bad API version | What you receive |
|---|---|---|
| Before traffic | The pre-traffic hook runs the self-check on the new version. A failure stops the deployment; `live` never moves. | "DeploymentFailure" from CodeDeploy, the `SelfCheckFailures` alarm |
| During the canary (prod: 10 % for 5 minutes) | Three alarms scoped to the new version: Lambda errors through `live`, `ScoringFailures` of that version, API 5xx. Any of them rolls back. | "DeploymentRollback" from CodeDeploy, the alarm itself |
| After 100 % | **Nothing rolls back by itself any more.** The paging alarm (`PagingScoringFailures`) and the health alarms still e-mail you. | The alarm e-mails |

The site is uploaded only after the API canary has completed, so a stopped API release never
changes the site.

## 2. API: after 100 %, point `live` back

1. Find the version to go back to (the one before the bad release):

   ```sh
   aws lambda list-versions-by-function --function-name staysharp-prod-api \
     --profile stay-sharp --region eu-central-2 --query "Versions[-3:].[Version,LastModified]"
   aws lambda get-alias --function-name staysharp-prod-api --name live \
     --profile stay-sharp --region eu-central-2
   ```

2. Revert the commit on `main` and let the deploy workflow ship it (preferred: the code and AWS
   stay the same). It goes through the canary like any release.
3. If players are hurt now and the workflow is too slow, move the alias back with CodeDeploy, so
   the hook and the alarms still apply:

   ```sh
   aws deploy create-deployment --application-name staysharp-prod-api \
     --deployment-group-name staysharp-prod-api --profile stay-sharp --region eu-central-2 \
     --revision 'revisionType=AppSpecContent,appSpecContent={content="{\"version\":0.0,\"Resources\":[{\"api\":{\"Type\":\"AWS::Lambda::Function\",\"Properties\":{\"Name\":\"staysharp-prod-api\",\"Alias\":\"live\",\"CurrentVersion\":\"<bad>\",\"TargetVersion\":\"<good>\"}}}]}"}'
   ```

   Then revert the commit on `main` the same day, so the next deploy does not bring the bad
   version back.

## 3. Front end: point the origin path back

Every release stays in the bucket under `site/<commit>/`. Going back is a redeploy of the web
stack with the previous commit (the files are already there, nothing is uploaded):

```sh
cd infra
npx --yes aws-cdk@2.1147.0 deploy staysharp-prod-web --exclusively --profile stay-sharp \
  -c siteCommit=<previous 12-character commit>
```

HTML is served with `must-revalidate`, so players get the previous site within seconds.

## 4. Data

Answers are written once and never changed by a release. If a release wrote wrong data, read
the point-in-time recovery notes (research R17, `specs/001-m1-web-app/research.md`) before
touching the table.

## 5. Afterwards

- Write down what happened, the time to detect and the time to recover.
- Add the missing test or alarm before the next release.
