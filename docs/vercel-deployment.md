# Deploy the browser demo to Vercel

This deploys the **CSV Studio browser interface and FastAPI processing endpoint**. It does not deploy, configure, or invoke AWS S3 or Lambda. The AWS SAM stack remains a separate optional deployment.

## Privacy and plan check

The hosted UI sends each selected CSV to a Vercel Function for processing. The app does not intentionally save the uploaded CSV, but request data passes through Vercel's hosting infrastructure. **Do not upload confidential, regulated, or personal data.** Review Vercel's privacy terms and your account/team policies before proceeding.

Vercel currently documents the Hobby plan as free for personal projects with included CDN and function quotas. Its published terms say most exceeded usage limits pause until the limit resets; this does not make the plan unlimited, and terms or eligibility can change. Check your Vercel account plan and current [plan details](https://vercel.com/docs/plans/hobby) before importing or deploying. Keep the project on Hobby, do not select Pro, enable paid add-ons, or buy a custom domain for this demo. If Vercel asks you to upgrade or enter a paid plan, stop.

## What deployment contains

- `public/` provides the static browser UI from Vercel's CDN.
- `app.py` provides a FastAPI function with `/api/info` and `/api/process`.
- `src/lambda_function.py` is reused for the validated CSV transformation.
- The hosted endpoint caps request bodies at 4 MiB (local/AWS processing uses 5 MiB).
- No AWS account, access keys, environment variables, bucket, database, or other cloud service is required for this deployment.
- Since the GitHub repository is public, its source code is already visible to everyone.

## Deploy using the GitHub repository

1. Sign in to [Vercel](https://vercel.com/). Use your personal Hobby team for a personal portfolio project if eligible; verify plan and billing first.
2. Select **Add New → Project**, connect GitHub if prompted, and import `HanshikaJ21/cloud-csv-processing-pipeline`.
3. Set the project root to the repository root. Vercel should detect the Python runtime from `requirements.txt` and the `app` FastAPI application from `app.py`. Keep the default build settings unless Vercel requests a specific configuration.
4. Confirm the configured Python version is 3.14 (from `.python-version`), inspect the settings and plan, then select **Deploy**. This uploads project source and creates a Vercel deployment. Review any billing/upgrade prompt and cancel if it requires a paid plan you do not want.
5. Wait for the deployment to finish. Open its assigned `*.vercel.app` URL. The page should show **VERCEL PROCESSING** and a notice that files are sent to Vercel.
6. Upload `sample-data/sales.csv`. Expected: 2 rows kept, 1 duplicate removed, total revenue `15.00`. Download the cleaned CSV and inspect its `revenue` column.
7. Test an invalid CSV and verify the UI shows `Rejected` rather than returning a partial output.
8. In Vercel's project dashboard, inspect deployment and function logs. This app intentionally does not log the request body or CSV rows.

## Deploy from the Vercel CLI (alternative)

Use this only if you have installed the Vercel CLI and signed in locally. Run commands from the repository root:

```powershell
# Local dependency install (uses local Python; no Vercel project created).
python -m pip install -r requirements.txt

# Connects to Vercel and creates/links a Vercel project configuration.
vercel link

# Creates a preview deployment.
vercel deploy
```

Review the selected account/team and prompts carefully. To publish to production after reviewing the preview:

```powershell
# Creates or updates the production deployment and its assigned URL.
vercel deploy --prod
```

Do not use `--yes` to skip the prompts on a first deployment. The Vercel dashboard/Git route is preferred because it avoids local token setup and creates deployments from later Git pushes.

## Verify and remove

- If the root page fails, inspect Vercel build logs for Python runtime detection. Confirm root directory is the repository root, `.python-version` is present, and `app.py` defines a FastAPI instance called `app`.
- If the status remains **PROCESSOR UNAVAILABLE**, inspect function logs for `/api/info` and confirm the Python function deployed.
- If requests are rejected for size, remain under the displayed 4 MiB hosted limit.
- To stop future automatic deploys, disconnect the Git repository in Vercel project settings or delete the Vercel project. This does not delete the GitHub repository.
- In the Vercel dashboard, delete the project when finished and verify the project/deployments are removed. Review Vercel usage/billing after its reporting delay.

Official references: [Python runtime](https://vercel.com/docs/functions/runtimes/python), [FastAPI deployment](https://vercel.com/docs/frameworks/backend/fastapi), [Git deployments](https://vercel.com/docs/git), [Hobby plan](https://vercel.com/docs/plans/hobby).
