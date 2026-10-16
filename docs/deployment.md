# Deployment guide

## Stop and check first

Deployment is entirely optional. **Do not proceed unless you explicitly decide to create AWS resources.** Neither path below is run by this repository. Read [cost-management.md](cost-management.md), confirm the account is not being upgraded from a Free plan, and review the resources/region before approving a deployment. If avoiding all charges is mandatory and eligibility is uncertain, stop and use local tests only.

Both deployment paths create the same logical resources: one private S3 bucket, one Lambda function and execution role, a CloudWatch log group, S3 notification configuration, and the required permission/policy resources. Do not use both paths against the same environment. Pick one.

## Common prerequisites

- An AWS account and a selected region, with billing/plan eligibility checked as described in [cost-management.md](cost-management.md).
- A globally unique bucket name: lowercase letters, digits, and hyphens, 3–63 characters. Do not include confidential information.
- The `incoming/` and `processed/` object prefixes are created automatically by uploads/writes; S3 has no real folders.
- For the Console path, your human identity needs permission to create the listed resources. For SAM, install Python 3.14, AWS SAM CLI, and AWS CLI, then configure an approved authentication method. Never paste credentials into this repository.

## Path A: AWS Management Console

The Console path is manual and should mirror the security and settings in `template.yaml`. Do not also deploy the SAM stack.

1. **Account/billing check:** open Billing and Cost Management. Confirm plan/credits and do not accept a paid-plan conversion. If uncertain, stop.
2. **Region:** choose one region where Lambda Python 3.14 is available. Keep S3, Lambda, and CloudWatch together in that region.
3. **Bucket:** create a general-purpose bucket with a unique name. Keep Block Public Access fully enabled, Bucket owner enforced object ownership, and default SSE-S3 encryption. Do not enable versioning, replication, logging, inventory, or optional analytics for this demo.
4. **Bucket policy:** add the TLS-only deny from `template.yaml`, substituting the bucket ARN. S3 notification configuration needs its AWS-managed invocation permission; do not add a public bucket policy.
5. **Execution role:** create an AWS Lambda trusted role and attach an inline policy like the following, replacing the placeholders. The account ID is present only in the CloudWatch log-group ARN; do not publish it unnecessarily.

   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": ["s3:GetObject", "s3:GetObjectVersion"],
         "Resource": "arn:aws:s3:::<BUCKET>/incoming/*"
       },
       {
         "Effect": "Allow",
         "Action": "s3:PutObject",
         "Resource": "arn:aws:s3:::<BUCKET>/processed/*"
       },
       {
         "Effect": "Allow",
         "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
         "Resource": "arn:aws:logs:<REGION>:<ACCOUNT-ID>:log-group:/aws/lambda/<FUNCTION-NAME>:*"
       }
     ]
   }
   ```

   The role is for code at runtime. The human deployment identity is separate and needs resource-management permission.
6. **Log group and function:** create `/aws/lambda/<FUNCTION-NAME>` with seven-day retention. Create a Lambda function using Python 3.14, 128 MiB, 15-second timeout, reserved concurrency 2, and the role above. Locally, create a ZIP with the handler file at its root:

   ```powershell
   # LOCAL ONLY: creates lambda.zip; it does not contact AWS.
   Compress-Archive -Path .\src\* -DestinationPath .\lambda.zip -Force
   ```

   Upload `lambda.zip` in the Lambda Console. Handler: `lambda_function.lambda_handler`. Environment: `MAX_INPUT_BYTES=5242880`. Set JSON application logs; the function emits JSON records.
7. **Notification:** add an S3 ObjectCreated notification with prefix `incoming/` and suffix `.csv`, targeting the function. Allow S3 invocation when prompted. The deployment order can require creating the function first, then adding the notification. Test that this does not change bucket access to public.
8. **Test:** upload `sample-data/sales.csv` to `incoming/sales.csv`. The S3 event invokes Lambda. Find the generated object in `processed/` (its name is a digest, not `sales.csv`). Download it and verify the `revenue` column and deduplication.
9. **Logs:** open CloudWatch Logs > the configured log group. Expect compact JSON `csv_processed` records; logs intentionally omit source keys and CSV data.
10. **Troubleshooting:** `AccessDenied` means the execution role's scoped S3/log permissions or S3 invoke permission is missing; a missing trigger means checking prefix/suffix and region; `rejected` means inspect the returned validation error and upload a valid UTF-8 CSV. S3 notifications are asynchronous and may retry transient failures.
11. **Cleanup:** empty both prefixes and delete all bucket objects, then remove the notification, function, execution role/policies, log group, bucket policy, and bucket. Confirm no resources remain in that region and check Billing after usage data updates. Follow the full checklist in [cost-management.md](cost-management.md).

Console interfaces change; use the AWS Console documentation for exact current UI labels. Do not add broad policies to work around an error.

## Path B: AWS SAM CLI

### Review before using resource-changing commands

`sam build` is local. The following commands contact AWS and create/update resources:

```powershell
# LOCAL ONLY: package/build the SAM application.
sam build

# AWS RESOURCE-CREATING: guided deploy creates/updates resources only after you approve.
sam deploy --guided
```

`sam deploy --guided` asks for a stack name, region, bucket name, and whether to confirm changes. It proposes the resources listed above and, after your explicit confirmation, creates or updates them. Choose a short stack name (50 characters or fewer) so the generated Lambda function name remains within AWS's limit. If a change-set summary is shown, inspect it; answer `N` or cancel if it contains unexpected resources, if the account plan would need upgrading, or if charges are not acceptable. Never use `--no-confirm-changeset` for this project.

1. Complete common account, billing, region, and bucket-name checks first.
2. Install SAM CLI and AWS CLI locally. Authenticate using the organization's/account's approved SSO or role-based method. Do not create application access keys.
3. In the project directory, run `sam validate --lint` and `sam build` locally.
4. Review `template.yaml`. `sam deploy --guided` creates the stack, S3 bucket, Lambda function/role, seven-day log group, and S3 notification. The bucket name is a required parameter because S3 names are globally unique.
5. Only after reviewing and approving the proposed change set, allow deployment to proceed. The function uses Python 3.14 and a five-MiB input cap.
6. Upload a test file (resource-changing AWS command):

   ```powershell
   aws s3 cp .\sample-data\sales.csv s3://<BUCKET-NAME>/incoming/sales.csv
   ```

7. Inspect outputs:

   ```powershell
   aws s3 ls s3://<BUCKET-NAME>/processed/
   ```

   These commands access AWS but do not create infrastructure. The output filename is a digest. Download it with `aws s3 cp s3://<BUCKET-NAME>/processed/<DIGEST>.csv .\sales-processed.csv` and inspect the `revenue` column.
8. Inspect logs with the CloudWatch Console or:

   ```powershell
   aws logs tail /aws/lambda/<STACK-NAME>-csv-processor --since 10m
   ```

9. **Cleanup is resource-changing:** first delete bucket contents, then delete the stack:

   ```powershell
   aws s3 rm s3://<BUCKET-NAME>/ --recursive
   sam delete --stack-name <STACK-NAME> --region <REGION>
   ```

   Verify CloudFormation stack deletion, S3 bucket removal, Lambda function removal, and log-group removal. Then check Billing/Cost Explorer after its reporting delay. `aws s3 rm --recursive` deletes data; confirm the bucket name and contents before running it.

### Common deployment issues

- **Bucket name unavailable:** choose a new globally unique name; do not include an account ID or personal data.
- **SAM validation/transform error:** run `sam validate --lint`, verify the current SAM CLI version supports Python 3.14, and inspect the reported logical resource.
- **Existing bucket/stack name:** use a new bucket or stack name rather than importing or overwriting an unrelated resource.
- **No Lambda invocation:** confirm the notification event type, exact `incoming/` prefix, `.csv` suffix, and same-region location.
- **Failed delete:** empty the bucket, retry stack deletion, and verify that no stack-managed resource was manually orphaned.
