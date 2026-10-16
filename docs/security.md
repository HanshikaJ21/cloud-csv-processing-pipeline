# Security decisions

- **Public access:** the bucket blocks public ACLs and policies and ignores public ACLs. Bucket-owner-enforced ownership disables ACL-based access management.
- **Transport and at-rest protection:** the bucket uses S3-managed AES-256 encryption and denies non-TLS bucket requests. Do not put sensitive customer data in this portfolio demo.
- **Lambda role:** the function has an execution role, not embedded keys. Its permissions are object-scoped: `s3:GetObject`/`s3:GetObjectVersion` for `incoming/*`, `s3:PutObject` for `processed/*`, and `logs:CreateLogStream`/`logs:PutLogEvents` scoped to its log group. It has no delete, list, public access, administrator, or processed-object read permission.
- **Human deployer:** the person using SAM/CloudFormation needs separate identity permissions to create/update/delete the stack resources and pass the execution role. Those deployment permissions are not granted to the running Lambda role. Use a least-privilege user/role, MFA, and temporary credentials where available; never create access keys for this code.
- **Logging:** logs do not include CSV cells, object keys, account identifiers, credentials, or exception messages. AWS service diagnostics remain available in the Lambda/CloudFormation consoles.
- **Optional Vercel hosting:** browser uploads are sent to the Vercel-hosted processing function. The app does not intentionally persist CSV contents, but Vercel operates the hosting and function infrastructure. Do not upload confidential or personal data; review Vercel's privacy and data-processing terms before hosting real data.
- **Limits:** the 5 MiB input cap, 25,000-row cap, bounded decimal exponent, 15-second timeout, 128 MiB memory, and reserved concurrency of two limit accidental workload growth. They do not guarantee a zero bill.
- **Review before deploy:** inspect the SAM change set, selected region, bucket name, account billing status, and the actual estimated resource changes. Never upload private/customer data.

If you manually configure this through the Console, match the same prefix/suffix filter, role policy, public-access block, encryption, TLS-only bucket policy, and seven-day log retention. Do not give the Lambda role broad managed policies such as `AdministratorAccess` or `AmazonS3FullAccess`.
