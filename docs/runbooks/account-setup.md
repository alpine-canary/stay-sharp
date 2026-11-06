# Runbook: AWS account set-up

Who: the maintainer, once per AWS account. Takes about one hour, plus DNS wait.

This file holds no account ids, portal URLs or e-mail addresses. Those stay in the maintainer's
`~/.aws/config` and password manager.

## 1. Account and sign-in

1. In the AWS Organization's management account, create a member account named `stay-sharp`
   with a dedicated root e-mail address.
2. In IAM Identity Center, assign the maintainer's user to that account with a permission set
   limited to a 4-hour session. Turn MFA on for Identity Center sign-in.
3. Root user of the member account: no daily use. Either use centralized root access from the
   management account (preferred: no root password exists) or set a long password and MFA and
   store both offline.
4. On the maintainer machine, add an SSO session and a profile named `stay-sharp` in
   `~/.aws/config` with region `eu-central-2`. Sign in:

   ```sh
   aws sso login --profile stay-sharp
   ```

## 2. Enable the Zurich region first

`eu-central-2` is an opt-in region. Until it is enabled, every call there fails with
`InvalidClientTokenId`.

```sh
aws account enable-region --region-name eu-central-2 --profile stay-sharp
aws account get-region-opt-status --region-name eu-central-2 --profile stay-sharp
```

Wait until the status is `ENABLED` (a few minutes), then check:

```sh
aws sts get-caller-identity --profile stay-sharp --region eu-central-2
```

## 3. CDK bootstrap with a narrowed execution policy

The default bootstrap makes the CloudFormation execution role an account administrator. We give
it only the services in the plan, from `infra/bootstrap/execution-policy.json`.

```sh
cd infra
aws iam create-policy --profile stay-sharp \
  --policy-name staysharp-cfn-execution \
  --policy-document file://bootstrap/execution-policy.json
npx --yes aws-cdk@2.1147.0 bootstrap --profile stay-sharp \
  --cloudformation-execution-policies "arn:aws:iam::<account>:policy/staysharp-cfn-execution" \
  aws://<account>/eu-central-2 aws://<account>/us-east-1
```

`<account>` is the account id; type it in the terminal, never in a committed file. When the
policy document changes, publish a new policy version with `aws iam create-policy-version
--set-as-default` and run the bootstrap command again.

## 4. DNS records for lumineth.com

The site is `stay-sharp.lumineth.com`. The `lumineth.com` zone is served by Route 53 in another AWS account,
not in `stay-sharp`; this project never manages it. Add the records there by hand.

1. Deploy the edge stack once (it requests the certificate in `us-east-1`). The stack waits for
   DNS validation.
2. In the ACM console (`us-east-1`), or in the stack events, read the validation CNAME name and
   value. Add that CNAME record in the `lumineth.com` zone. Keep it: ACM uses it to renew.
3. After the web stack is deployed, add the site record in the `lumineth.com` zone: CNAME
   `stay-sharp` to the CloudFront distribution domain name (`dxxxxxxxx.cloudfront.net`).
4. Check:

   ```sh
   dig +short CNAME stay-sharp.lumineth.com
   curl -sI https://stay-sharp.lumineth.com/api/v1/health
   ```

## 5. Maintainer e-mail for alarms

The alarm topic reads the maintainer e-mail from an SSM parameter, so it never enters the
repository:

```sh
aws ssm put-parameter --profile stay-sharp --region eu-central-2 \
  --name /staysharp/<stage>/alarm-email --type String --value "<address>"
```

Confirm the SNS subscription e-mail after the first deploy of each stage.

## 6. GitHub

1. Set the repository variable `AWS_DIFF_ROLE_ARN` (and later the deploy role ARNs) from the
   account stack outputs. Variables, not secrets: role ARNs are not secret, but keep them out of
   committed files.
2. Create the environment `production` with the maintainer as required reviewer.

## 7. Sign-in e-mails (accounts, M2)

Cognito sends the sign-in codes from `stay-sharp@lumineth.com` through SES in `eu-central-2`
(stack `staysharp-mail`, one per account). Checked on 2026-11-06: SES is offered in
`eu-central-2`; the account starts in the SES sandbox (200 e-mails a day, verified recipients
only).

1. **Bootstrap policy.** The execution policy now allows `cognito-idp:*`, `ses:*` and the
   Cognito e-mail service-linked role. Publish the new policy version and run the bootstrap
   again (section 3) before the first deploy of an `-auth` stack.
2. **Deploy the mail stack**, then print the three DKIM records:

   ```sh
   make dkim-records
   ```

   Each line is a CNAME: `<token>._domainkey.lumineth.com` to `<token>.dkim.amazonses.com`. Add
   the three in the `lumineth.com` zone (same place as section 4) and keep them. SES checks them
   by itself; `make dkim-records` shows `SUCCESS` once they are seen (up to 72 hours, usually
   minutes).
3. **DMARC and SPF.** DKIM signed with `lumineth.com` is enough for DMARC alignment. If the zone
   has a DMARC record with `p=reject`, nothing changes for these e-mails. No SPF change is
   needed (SES uses its own MAIL FROM domain).
4. **Dev, while in the sandbox:** SES sends only to verified addresses. Verify the address you
   test with, from your terminal (never written in the repository):

   ```sh
   aws sesv2 create-email-identity --profile stay-sharp --region eu-central-2 \
     --email-identity "<your address>"
   ```

   and click the link SES sends.
5. **Before prod:** ask for SES production access (transactional mail, sign-in codes only, a
   few per player per month):

   ```sh
   aws sesv2 put-account-details --profile stay-sharp --region eu-central-2 \
     --production-access-enabled --mail-type TRANSACTIONAL \
     --website-url https://stay-sharp.lumineth.com \
     --use-case-description "One-time sign-in codes for an optional account of a free daily quiz. Sent only when a player asks for one. Bounces and complaints go to the maintainer."
   ```

6. **Dev passkeys.** After the first `staysharp-dev-web` deploy, set the context `devSiteHost`
   to the dev CloudFront host (`dxxxxxxxx.cloudfront.net`) in `infra/cdk.json` and redeploy
   `staysharp-dev-auth`. Without it, dev signs in with e-mail codes only.
