"""Vercel-hosted FastAPI app for the CSV Studio interface."""

from __future__ import annotations

import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.lambda_function import MAX_INPUT_BYTES, InvalidCSV, transform_csv

VERCEL_REQUEST_LIMIT = 4 * 1024 * 1024
UPLOAD_LIMIT = (
    min(MAX_INPUT_BYTES, VERCEL_REQUEST_LIMIT)
    if os.environ.get("VERCEL") == "1"
    else MAX_INPUT_BYTES
)

app = FastAPI(
    title="CSV Studio",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.get("/api/info")
async def processor_info() -> dict[str, object]:
    return {
        "mode": "vercel" if os.environ.get("VERCEL") == "1" else "local",
        "max_input_bytes": UPLOAD_LIMIT,
    }


@app.post("/api/process")
async def process_file(request: Request) -> JSONResponse:
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            declared_size = int(content_length)
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={"status": "rejected", "error": "Invalid Content-Length header."},
            )
        if declared_size < 0:
            return JSONResponse(
                status_code=400,
                content={"status": "rejected", "error": "Invalid Content-Length header."},
            )
        if declared_size > UPLOAD_LIMIT:
            return JSONResponse(
                status_code=413,
                content={
                    "status": "rejected",
                    "error": f"File exceeds the {UPLOAD_LIMIT}-byte size limit.",
                },
            )

    payload = await request.body()
    if len(payload) > UPLOAD_LIMIT:
        return JSONResponse(
            status_code=413,
            content={"status": "rejected", "error": f"File exceeds the {UPLOAD_LIMIT}-byte size limit."},
        )
    try:
        cleaned_csv, summary = transform_csv(payload)
    except InvalidCSV as exc:
        return JSONResponse(status_code=400, content={"status": "rejected", "error": str(exc)})
    return JSONResponse(
        status_code=200,
        content={"status": "success", **summary, "cleaned_csv": cleaned_csv.decode("utf-8")},
    )
