"""S3-triggered CSV validation and transformation."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
from decimal import Decimal, InvalidOperation, localcontext
from typing import Any
from urllib.parse import unquote_plus

REQUIRED_COLUMNS = ("product", "quantity", "unit_price")
OUTPUT_COLUMNS = ("product", "quantity", "unit_price", "revenue")
MAX_INPUT_BYTES = int(os.environ.get("MAX_INPUT_BYTES", str(5 * 1024 * 1024)))
MAX_FIELD_CHARS = 64
MAX_ROWS = 25000
MAX_PRICE_EXPONENT = 100
QUANTITY_PATTERN = re.compile(r"^[0-9]+$")


class InvalidCSV(ValueError):
    """Raised when the file is readable but does not satisfy the input contract."""


class S3ProcessingError(RuntimeError):
    """A sanitized AWS failure that Lambda can retry without logging service details."""


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


def transform_csv(payload: bytes) -> tuple[bytes, dict[str, Any]]:
    """Validate and transform CSV bytes without performing any AWS calls."""
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise InvalidCSV("CSV must use UTF-8 or UTF-8 with a BOM.") from exc

    if not text.strip():
        raise InvalidCSV("CSV file is empty.")

    stream = io.StringIO(text, newline="")
    reader = csv.reader(stream, strict=True)
    try:
        headers = next(reader)
    except StopIteration as exc:
        raise InvalidCSV("CSV file is empty.") from exc
    except csv.Error as exc:
        raise InvalidCSV("CSV syntax is invalid.") from exc

    normalized_headers = [header.strip().casefold() for header in headers]
    if len(set(normalized_headers)) != len(normalized_headers):
        raise InvalidCSV("CSV contains duplicate column names.")
    missing = [name for name in REQUIRED_COLUMNS if name not in normalized_headers]
    if missing:
        raise InvalidCSV("CSV is missing required columns: " + ", ".join(missing) + ".")

    indices = {name: normalized_headers.index(name) for name in REQUIRED_COLUMNS}
    seen: set[tuple[str, int, Decimal]] = set()
    transformed: list[tuple[str, int, Decimal, Decimal]] = []
    duplicate_count = 0
    input_rows = 0

    try:
        with localcontext() as context:
            context.prec = 256
            for row in reader:
                input_rows += 1
                if input_rows > MAX_ROWS:
                    raise InvalidCSV(f"CSV exceeds the {MAX_ROWS}-record limit.")
                if len(row) != len(headers):
                    raise InvalidCSV(f"CSV record {input_rows + 1} has an unexpected number of fields.")

                product = row[indices["product"]].strip()
                if not product:
                    raise InvalidCSV(f"CSV record {input_rows + 1} has an empty product name.")

                raw_quantity = row[indices["quantity"]].strip()
                if len(raw_quantity) > MAX_FIELD_CHARS or not QUANTITY_PATTERN.fullmatch(raw_quantity):
                    raise InvalidCSV(f"CSV record {input_rows + 1} has an invalid quantity.")
                quantity = int(raw_quantity)

                raw_price = row[indices["unit_price"]].strip()
                if not raw_price or len(raw_price) > MAX_FIELD_CHARS:
                    raise InvalidCSV(f"CSV record {input_rows + 1} has an invalid unit price.")
                try:
                    unit_price = Decimal(raw_price)
                except InvalidOperation as exc:
                    raise InvalidCSV(f"CSV record {input_rows + 1} has an invalid unit price.") from exc
                if not unit_price.is_finite():
                    raise InvalidCSV(f"CSV record {input_rows + 1} has an invalid unit price.")
                if (
                    abs(unit_price.as_tuple().exponent) > MAX_PRICE_EXPONENT
                    or unit_price.adjusted() > MAX_PRICE_EXPONENT
                    or unit_price.adjusted() < -MAX_PRICE_EXPONENT
                ):
                    raise InvalidCSV(f"CSV record {input_rows + 1} has a unit price outside the supported range.")
                if unit_price < 0:
                    raise InvalidCSV(f"CSV record {input_rows + 1} has a negative unit price.")

                dedupe_key = (product.casefold(), quantity, unit_price.normalize())
                if dedupe_key in seen:
                    duplicate_count += 1
                    continue

                seen.add(dedupe_key)
                transformed.append((product, quantity, unit_price, unit_price * quantity))
            if reader.line_num == 0:
                raise InvalidCSV("CSV file is empty.")
    except csv.Error as exc:
        raise InvalidCSV("CSV syntax is invalid.") from exc

    if input_rows == 0:
        raise InvalidCSV("CSV contains a header but no data rows.")

    with localcontext() as context:
        context.prec = 256
        total_revenue = sum((record[3] for record in transformed), Decimal(0))
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(OUTPUT_COLUMNS)
    for product, quantity, unit_price, revenue in transformed:
        writer.writerow((product, quantity, _decimal_text(unit_price), _decimal_text(revenue)))

    summary: dict[str, Any] = {
        "rows_processed": len(transformed),
        "duplicates_removed": duplicate_count,
        "total_revenue": _decimal_text(total_revenue),
    }
    return output.getvalue().encode("utf-8"), summary


def _reject(message: str, input_key: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "rejected",
        "input_key": input_key,
        "output_key": None,
        "rows_processed": 0,
        "duplicates_removed": 0,
        "total_revenue": "0",
        "error": message,
    }
    _log({"event": "csv_rejected", "error_type": "InvalidCSV"})
    return result


def _log(record: dict[str, Any]) -> None:
    print(json.dumps(record, separators=(",", ":"), sort_keys=True))


def _output_key(bucket: str, key: str, identity: str, payload: bytes) -> str:
    source_digest = hashlib.sha256(payload).hexdigest()
    digest = hashlib.sha256(
        f"{bucket}\n{key}\n{identity}\n{source_digest}".encode("utf-8")
    ).hexdigest()
    return f"processed/{digest}.csv"


def _event_identity(s3_object: dict[str, Any]) -> str:
    version_id = s3_object.get("versionId")
    etag = s3_object.get("eTag")
    if version_id:
        if not isinstance(version_id, str):
            raise ValueError("S3 event versionId must be a string.")
        return "version:" + str(version_id)
    if etag:
        if not isinstance(etag, str):
            raise ValueError("S3 event eTag must be a string.")
        return "etag:" + str(etag)
    raise ValueError("S3 event is missing both versionId and eTag.")


def _read_bounded(body: Any, limit: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while total <= limit:
        chunk = body.read(min(64 * 1024, limit + 1 - total))
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
    if total > limit:
        raise InvalidCSV(f"Input exceeds the {limit}-byte size limit.")
    return b"".join(chunks)


def process_record(record: dict[str, Any], s3_client: Any) -> dict[str, Any]:
    """Process one S3 event record. AWS failures are deliberately re-raised for retry."""
    try:
        if not isinstance(record, dict):
            raise ValueError("S3 event record must be an object.")
        if record.get("eventSource") != "aws:s3":
            raise ValueError("Event source is not S3.")
        event_name = record.get("eventName", "")
        if not isinstance(event_name, str) or not event_name.startswith("ObjectCreated:"):
            raise ValueError("Event is not an S3 object-created event.")

        s3_data = record["s3"]
        bucket = s3_data["bucket"]["name"]
        s3_object = s3_data["object"]
        key = unquote_plus(s3_object["key"], encoding="utf-8", errors="strict")
        identity = _event_identity(s3_object)
        version_id = s3_object.get("versionId")
        event_etag = s3_object.get("eTag")
        size = s3_object.get("size")
        if not isinstance(bucket, str) or not bucket or not isinstance(key, str):
            raise ValueError("S3 event contains an invalid bucket or object key.")
        if not key.startswith("incoming/") or not key.lower().endswith(".csv"):
            raise ValueError("Object key is outside the accepted incoming CSV prefix.")
        if size is not None and (not isinstance(size, int) or size < 0 or size > MAX_INPUT_BYTES):
            raise InvalidCSV(f"Input exceeds the {MAX_INPUT_BYTES}-byte size limit.")
    except InvalidCSV as exc:
        return _reject(str(exc))
    except (KeyError, TypeError, ValueError) as exc:
        _log({"event": "event_rejected", "error_type": type(exc).__name__})
        return _reject("Malformed or unsupported S3 event.")

    try:
        get_object_args = {"Bucket": bucket, "Key": key}
        if version_id:
            get_object_args["VersionId"] = version_id
        response = s3_client.get_object(**get_object_args)
        content_length = response.get("ContentLength")
        if isinstance(content_length, int) and content_length > MAX_INPUT_BYTES:
            return _reject(f"Input exceeds the {MAX_INPUT_BYTES}-byte size limit.", key)
        if not version_id:
            response_etag = response.get("ETag")
            if (
                not isinstance(event_etag, str)
                or not isinstance(response_etag, str)
                or event_etag.strip('"') != response_etag.strip('"')
            ):
                return _reject("Source object changed before it could be read.", key)
        body = response["Body"]
        try:
            payload = _read_bounded(body, MAX_INPUT_BYTES)
        except InvalidCSV as exc:
            return _reject(str(exc), key)

        output_bytes, summary = transform_csv(payload)
        output_key = _output_key(bucket, key, identity, payload)
        try:
            s3_client.put_object(
                Bucket=bucket,
                Key=output_key,
                Body=output_bytes,
                ContentType="text/csv; charset=utf-8",
                IfNoneMatch="*",
            )
        except Exception as exc:
            response_data = getattr(exc, "response", {})
            error = response_data.get("Error", {}) if isinstance(response_data, dict) else {}
            if error.get("Code") == "PreconditionFailed":
                result = {
                    "status": "duplicate",
                    "input_key": key,
                    "output_key": output_key,
                    "rows_processed": 0,
                    "duplicates_removed": 0,
                    "total_revenue": "0",
                }
                _log(
                    {
                        "event": "duplicate_delivery",
                        "status": "duplicate",
                        "output_key": output_key,
                    }
                )
                return result
            raise

        result = {
            "status": "success",
            "input_key": key,
            "output_key": output_key,
            **summary,
        }
        _log(
            {
                "event": "csv_processed",
                "status": "success",
                "output_key": output_key,
                **summary,
            }
        )
        return result
    except InvalidCSV as exc:
        return _reject(str(exc), key)
    except Exception as exc:
        response_data = getattr(exc, "response", {})
        error = response_data.get("Error", {}) if isinstance(response_data, dict) else {}
        candidate = error.get("Code")
        error_code = (
            candidate
            if isinstance(candidate, str) and re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", candidate)
            else type(exc).__name__
        )
        _log({"event": "s3_processing_failed", "error_code": str(error_code)})
        raise S3ProcessingError(f"S3 processing failed ({error_code}).") from None


def lambda_handler(event: Any, context: Any, s3_client: Any = None) -> dict[str, Any]:
    """AWS Lambda entry point for S3 notifications."""
    del context
    if not isinstance(event, dict) or not isinstance(event.get("Records"), list) or not event["Records"]:
        return _reject("Malformed S3 notification event.")

    if s3_client is None:
        try:
            import boto3

            s3_client = boto3.client("s3")
        except Exception as exc:
            _log({"event": "s3_client_initialization_failed", "error_type": type(exc).__name__})
            raise S3ProcessingError("Unable to initialize the S3 client.") from None

    results = [process_record(record, s3_client) for record in event["Records"]]
    overall_status = "success"
    if any(result["status"] == "rejected" for result in results):
        overall_status = "rejected"
    elif any(result["status"] == "duplicate" for result in results):
        overall_status = "duplicate"
    return {"status": overall_status, "results": results}
