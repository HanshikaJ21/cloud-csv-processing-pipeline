# Local browser UI

This is an optional local demonstration UI for the same CSV validation and transformation code used by Lambda. It does **not** upload data to S3, call AWS, or use AWS credentials. The browser sends the selected file only to the local server listening on `127.0.0.1`.

## Run it

From the project folder:

```powershell
python local_ui.py
```

Open <http://127.0.0.1:8000> in a browser. Select or drop a `.csv` file, choose **Process file**, review row/duplicate/revenue totals, and download the cleaned CSV. Press `Ctrl+C` in the terminal to stop the server.

The server binds only to the loopback address, accepts files up to 5 MiB, and serves only known UI assets. No cloud resources are created and local use does not incur AWS or hosting charges. Treat uploaded data as private even though it stays on the device.

This interface is a local demo, not a production web application and not an AWS upload console. Vercel hosting is documented separately in [vercel-deployment.md](vercel-deployment.md). An AWS-connected UI would need a separately designed identity/authentication and authorization flow; browser code must never contain AWS credentials.
