# Cost and eligibility checklist

**A zero budget is a stop condition, not a cost estimate. Do not deploy until the account plan, credits, regional rates, and expected usage have been checked in the AWS Billing console.** This project has not been deployed, and this repository cannot determine your account's remaining allowance or eligibility.

## What AWS currently publishes

As checked on 2026-10-16:

- The AWS Free Tier page describes a **Free plan** for new accounts with $100 in credits at signup and up to $100 more over six months. The page says a Free plan account closes after six months or when credits run out, whichever comes first, and says it will not be charged unless converted to a Paid plan. This is account-plan-specific; do not convert or upgrade to deploy this demo.
- Lambda's pricing page describes request and compute charges and may present different offers/eligibility by account, region, and date. S3 charges can include storage and request charges. CloudWatch can charge for log ingestion/storage and other features. Rates differ by region and plan.
- AWS pricing pages are live and may change. Check each linked pricing page and the account's Billing & Cost Management console on the day you consider deploying. A displayed Free Tier allowance or promotional credit is not a promise that every account qualifies or that all usage is covered.

Official references:

- [AWS Free Tier and account plans](https://aws.amazon.com/free/)
- [AWS Lambda pricing](https://aws.amazon.com/lambda/pricing/)
- [Amazon S3 pricing](https://aws.amazon.com/s3/pricing/)
- [Amazon CloudWatch pricing](https://aws.amazon.com/cloudwatch/pricing/)
- [AWS Billing and Cost Management](https://console.aws.amazon.com/billing/)

## Before deployment

1. Confirm the account plan is still **Free**, if that is the condition you require. Decline any prompt to switch/upgrade to Paid. If the console requires conversion, stop.
2. In Billing, verify remaining promotional credits, expiration, Free Tier eligibility, current usage, and whether the account has a payment method or existing charges.
3. Select one region and check the region-specific prices for Lambda requests/compute, S3 storage/PUT/GET requests, and CloudWatch log ingestion/storage. CloudFormation and IAM are part of this setup, but any other enabled service, support plan, data transfer, taxes, and existing resources can affect the bill.
4. This template creates one S3 bucket, one Lambda function and execution role, one CloudWatch log group, a bucket policy, and S3 notification permissions/configuration. No EC2, NAT gateway, RDS, provisioned concurrency, custom metrics, or paid API is used.
5. Upload only a tiny sample, run it a few times, and delete the stack and bucket contents promptly after verifying. The seven-day log retention reduces retained logs, but ingestion can still be billable.
6. If you cannot verify that the actual plan covers all likely charges, do not deploy. Run tests locally instead.

There is no reliable universal dollar estimate here: free allowances, credit balances, regional pricing, taxes, and account eligibility are account-specific. No claim that this project costs zero is made.

## Teardown and verify

1. Remove every object under `incoming/` and `processed/` (and any incomplete multipart uploads, if created). An S3 bucket cannot be deleted while it contains objects.
2. Delete the CloudFormation/SAM stack in the same region. This removes the function, log group, role/policies, bucket, notification, and bucket policy if the resources are still managed by that stack.
3. If the stack fails to delete because the bucket is non-empty, empty it, then retry stack deletion. Do not manually delete a stack-managed resource unless you understand how to recover stack state.
4. In CloudFormation, confirm the stack is gone. In S3, confirm the bucket is gone. In Lambda and CloudWatch Logs, confirm the function and its log group are gone. Check all regions you used.
5. Review Billing > Bills/Charges and Cost Explorer after usage data has had time to update. Check for other existing resources too; deleting this stack does not remove unrelated resources or undo charges already incurred.

For local testing, pytest and the standard library run without AWS resources or AWS charges.

## Optional Vercel-hosted UI

Vercel is independent of AWS. Its current [Hobby plan](https://vercel.com/docs/plans/hobby) is documented as free for personal use and includes finite CDN/function quotas; over-limit behavior, plan terms, and eligibility should be checked in your Vercel account before deployment. The app does not require a paid Vercel feature, but uploading CSVs invokes a hosted function and uses transfer/compute resources. Do not upgrade, enable paid add-ons, attach a paid custom domain, or upload real confidential data for this demo. Read [vercel-deployment.md](vercel-deployment.md) and delete the Vercel project if you no longer want it hosted.
