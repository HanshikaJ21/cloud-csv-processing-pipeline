import sys

import pytest

sys.path.insert(0, "src")
from lambda_function import S3ProcessingError, lambda_handler, process_record


class FakeBody:
    def __init__(self, payload, chunk_size=None):
        self.payload = payload
        self.offset = 0
        self.chunk_size = chunk_size

    def read(self, amount=-1):
        if amount < 0:
            amount = len(self.payload) - self.offset
        if self.chunk_size is not None:
            amount = min(amount, self.chunk_size)
        end = min(self.offset + amount, len(self.payload))
        chunk = self.payload[self.offset:end]
        self.offset = end
        return chunk


class FakeS3:
    def __init__(self, payload):
        self.payload = payload
        self.etag = "abc123"
        self.read_chunk_size = None
        self.objects = {}
        self.fail_get = None
        self.fail_put = None

    def get_object(self, **kwargs):
        if self.fail_get:
            raise self.fail_get
        return {
            "Body": FakeBody(self.payload, self.read_chunk_size),
            "ETag": self.etag,
            "ContentLength": len(self.payload),
        }

    def put_object(self, **kwargs):
        if self.fail_put:
            raise self.fail_put
        if kwargs["Key"] in self.objects:
            raise S3Error("PreconditionFailed")
        self.objects[kwargs["Key"]] = kwargs


class S3Error(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


def s3_record(key="incoming/sales.csv"):
    return {
        "eventSource": "aws:s3",
        "eventName": "ObjectCreated:Put",
        "s3": {
            "bucket": {"name": "example-bucket"},
            "object": {"key": key.replace("/", "%2F"), "eTag": "abc123", "size": 50},
        },
    }


def test_success_and_duplicate_delivery_do_not_overwrite():
    s3 = FakeS3(b"product,quantity,unit_price\nWidget,2,1.25\n")
    first = process_record(s3_record(), s3)
    second = process_record(s3_record(), s3)

    assert first["status"] == "success"
    assert first["rows_processed"] == 1
    assert second["status"] == "duplicate"
    assert second["output_key"] == first["output_key"]
    assert len(s3.objects) == 1
    assert next(iter(s3.objects.values()))["IfNoneMatch"] == "*"
    assert first["output_key"].startswith("processed/")


def test_bounded_reader_handles_short_stream_reads():
    s3 = FakeS3(b"product,quantity,unit_price\nWidget,2,1.25\n")
    s3.read_chunk_size = 7
    result = process_record(s3_record(), s3)
    assert result["status"] == "success"


def test_changed_source_content_produces_a_different_output_key():
    s3 = FakeS3(b"product,quantity,unit_price\nA,1,2\n")
    original = process_record(s3_record(), s3)
    changed_record = s3_record()
    changed_record["s3"]["object"]["eTag"] = "new-etag"
    s3.etag = "new-etag"

    changed = process_record(changed_record, s3)
    assert changed["status"] == "success"
    assert changed["output_key"] != original["output_key"]
    assert len(s3.objects) == 2


def test_stale_event_for_overwritten_source_is_rejected():
    s3 = FakeS3(b"product,quantity,unit_price\nA,1,2\n")
    s3.etag = "new-etag"
    result = process_record(s3_record(), s3)
    assert result["status"] == "rejected"
    assert result["output_key"] is None
    assert not s3.objects


def test_versioned_event_fetches_exact_version():
    class VersionAwareS3(FakeS3):
        def get_object(self, **kwargs):
            self.requested_version = kwargs.get("VersionId")
            return {"Body": FakeBody(self.payload)}

    s3 = VersionAwareS3(b"product,quantity,unit_price\nA,1,2\n")
    record = s3_record()
    record["s3"]["object"]["versionId"] = "version-1"
    result = process_record(record, s3)
    assert result["status"] == "success"
    assert s3.requested_version == "version-1"


@pytest.mark.parametrize("record", [{}, {"eventSource": "aws:s3"}, None])
def test_malformed_records_are_rejected_without_aws_calls(record):
    result = process_record(record, FakeS3(b""))
    assert result["status"] == "rejected"
    assert result["output_key"] is None


def test_wrong_prefix_or_extension_is_rejected():
    assert process_record(s3_record("processed/file.csv"), FakeS3(b""))["status"] == "rejected"
    assert process_record(s3_record("incoming/file.txt"), FakeS3(b""))["status"] == "rejected"


@pytest.mark.parametrize("operation", ["get", "put"])
def test_s3_errors_are_logged_and_raised_for_lambda_retry(operation):
    s3 = FakeS3(b"product,quantity,unit_price\nA,1,2\n")
    error = S3Error("AccessDenied")
    error.args = ("AccessDenied for private/incoming/customer.csv",)
    if operation == "get":
        s3.fail_get = error
    else:
        s3.fail_put = error

    with pytest.raises(S3ProcessingError, match="S3 processing failed") as raised:
        process_record(s3_record(), s3)
    assert "customer.csv" not in str(raised.value)
    assert raised.value.__cause__ is None


def test_lambda_handler_rejects_malformed_event():
    result = lambda_handler({"Records": []}, None)
    assert result["status"] == "rejected"


def test_lambda_handler_handles_malformed_records_with_injected_s3_client():
    result = lambda_handler({"Records": [None]}, None, FakeS3(b""))
    assert result["status"] == "rejected"
    assert result["results"][0]["status"] == "rejected"


def test_lambda_handler_returns_record_summaries_with_injected_s3_client():
    s3 = FakeS3(b"product,quantity,unit_price\nA,2,1.25\n")
    result = lambda_handler({"Records": [s3_record()]}, None, s3)
    assert result["status"] == "success"
    assert result["results"][0]["total_revenue"] == "2.50"


def test_oversized_event_is_rejected_without_fetch():
    record = s3_record()
    record["s3"]["object"]["size"] = 6 * 1024 * 1024
    result = process_record(record, FakeS3(b""))
    assert result["status"] == "rejected"
