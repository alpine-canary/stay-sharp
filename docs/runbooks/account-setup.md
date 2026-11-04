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
