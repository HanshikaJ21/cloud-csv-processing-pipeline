import sys

import pytest

sys.path.insert(0, ".")
from local_ui import process_upload
from src.lambda_function import InvalidCSV, MAX_INPUT_BYTES


def test_local_ui_uses_shared_processor_and_returns_downloadable_csv():
    result = process_upload(
        b"product,quantity,unit_price\nWidget,2,1.25\nWidget,2,1.25\n"
    )

    assert result == {
        "rows_processed": 1,
        "duplicates_removed": 1,
        "total_revenue": "2.50",
        "cleaned_csv": "product,quantity,unit_price,revenue\nWidget,2,1.25,2.50\n",
    }


def test_local_ui_rejects_oversized_upload():
    with pytest.raises(InvalidCSV, match="size limit"):
        process_upload(b"x" * (MAX_INPUT_BYTES + 1))


def test_local_ui_reports_invalid_csv():
    with pytest.raises(InvalidCSV, match="missing required columns"):
        process_upload(b"name\nWidget\n")
