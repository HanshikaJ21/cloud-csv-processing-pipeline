import csv
import io
import sys
from decimal import Decimal

import pytest

sys.path.insert(0, "src")
from lambda_function import InvalidCSV, transform_csv


def rows(payload):
    return list(csv.DictReader(io.StringIO(payload.decode("utf-8"))))


def test_valid_csv_uses_decimal_and_writes_expected_columns():
    payload, summary = transform_csv(
        b"product,quantity,unit_price\nWidget,3,0.10\nGadget,2,1.25\n"
    )

    assert rows(payload) == [
        {"product": "Widget", "quantity": "3", "unit_price": "0.10", "revenue": "0.30"},
        {"product": "Gadget", "quantity": "2", "unit_price": "1.25", "revenue": "2.50"},
    ]
    assert summary == {
        "rows_processed": 2,
        "duplicates_removed": 0,
        "total_revenue": "2.80",
    }
    assert Decimal(summary["total_revenue"]) == Decimal("2.80")


def test_total_revenue_keeps_precision_beyond_default_decimal_context():
    payload, summary = transform_csv(
        b"product,quantity,unit_price\nA,123456789012345678901234567890,1\n"
    )
    assert rows(payload)[0]["revenue"] == "123456789012345678901234567890"
    assert summary["total_revenue"] == "123456789012345678901234567890"


def test_utf8_bom_is_supported():
    payload, _ = transform_csv("\ufeffproduct,quantity,unit_price\nA,1,2\n".encode("utf-8"))
    assert rows(payload)[0]["product"] == "A"


def test_duplicate_rows_are_removed_after_normalization():
    payload, summary = transform_csv(
        b"product,quantity,unit_price\nWidget,2,1.0\n widget ,2,1.00\nOther,2,1.0\n"
    )
    assert len(rows(payload)) == 2
    assert summary["duplicates_removed"] == 1


@pytest.mark.parametrize(
    "source,message",
    [
        (b"name,quantity,unit_price\nA,1,2\n", "missing required columns"),
        (b"product,quantity,unit_price\n ,1,2\n", "empty product"),
        (b"product,quantity,unit_price\nA,1.5,2\n", "invalid quantity"),
        (b"product,quantity,unit_price\nA,1,nope\n", "invalid unit price"),
        (b"product,quantity,unit_price\nA,-1,2\n", "invalid quantity"),
        (b"product,quantity,unit_price\nA,1,-2\n", "negative unit price"),
        (b"product,quantity,unit_price\nA,1,1e999\n", "supported range"),
        (b"", "empty"),
        (b"product,quantity,unit_price\n", "no data rows"),
        (b"product,quantity,unit_price\nA,1,2\n\xff", "UTF-8"),
        (b"product,quantity,unit_price\nA,1\n", "unexpected number"),
        (b"product,quantity,unit_price\nA,1,2\n\n", "unexpected number"),
    ],
)
def test_invalid_csv_is_rejected(source, message):
    with pytest.raises(InvalidCSV, match=message):
        transform_csv(source)


def test_negative_quantity_is_rejected():
    with pytest.raises(InvalidCSV, match="invalid quantity"):
        transform_csv(b"product,quantity,unit_price\nA,-3,2\n")


def test_duplicate_headers_are_rejected():
    with pytest.raises(InvalidCSV, match="duplicate column"):
        transform_csv(b"product,Product,quantity,unit_price\nA,A,1,2\n")


def test_row_limit_is_enforced():
    source = b"product,quantity,unit_price\n" + b"A,1,1\n" * 25001
    with pytest.raises(InvalidCSV, match="25000-record limit"):
        transform_csv(source)
