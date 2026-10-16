import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app as hosted_app

client = TestClient(hosted_app.app)


def test_processor_info_returns_mode_and_limit(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    response = client.get("/api/info")

    assert response.status_code == 200
    assert response.json() == {
        "mode": "vercel",
        "max_input_bytes": hosted_app.UPLOAD_LIMIT,
    }


def test_processing_endpoint_returns_cleaned_csv_and_summary():
    response = client.post(
        "/api/process",
        content=b"product,quantity,unit_price\nWidget,2,1.25\nWidget,2,1.25\n",
        headers={"content-type": "text/csv"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "success",
        "rows_processed": 1,
        "duplicates_removed": 1,
        "total_revenue": "2.50",
        "cleaned_csv": "product,quantity,unit_price,revenue\nWidget,2,1.25,2.50\n",
    }


def test_processing_endpoint_rejects_invalid_input():
    response = client.post("/api/process", content=b"name\nWidget\n")

    assert response.status_code == 400
    assert response.json()["status"] == "rejected"
    assert "missing required columns" in response.json()["error"]


def test_processing_endpoint_rejects_uploads_over_configured_limit(monkeypatch):
    monkeypatch.setattr(hosted_app, "UPLOAD_LIMIT", 16)
    response = client.post(
        "/api/process",
        content=b"x",
        headers={"content-length": "17"},
    )

    assert response.status_code == 413
    assert response.json()["status"] == "rejected"
