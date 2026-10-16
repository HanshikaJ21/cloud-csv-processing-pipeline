"""Run a local browser UI for the CSV processor; this server does not use AWS."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from src.lambda_function import MAX_INPUT_BYTES, InvalidCSV, transform_csv

ROOT = Path(__file__).resolve().parent
STATIC_FILES = {
    "/": (ROOT / "public" / "index.html", "text/html; charset=utf-8"),
    "/index.html": (ROOT / "public" / "index.html", "text/html; charset=utf-8"),
    "/app.js": (ROOT / "public" / "app.js", "text/javascript; charset=utf-8"),
    "/styles.css": (ROOT / "public" / "styles.css", "text/css; charset=utf-8"),
}


def process_upload(payload: bytes) -> dict[str, object]:
    if len(payload) > MAX_INPUT_BYTES:
        raise InvalidCSV(f"File exceeds the {MAX_INPUT_BYTES}-byte size limit.")
    output, summary = transform_csv(payload)
    return {**summary, "cleaned_csv": output.decode("utf-8")}


class LocalUIHandler(BaseHTTPRequestHandler):
    server_version = "LocalCSVUI"
    sys_version = ""

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; connect-src 'self'; style-src 'self'; "
            "script-src 'self'; img-src 'self' data:; base-uri 'none'; "
            "form-action 'self'; frame-ancestors 'none'",
        )
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")

    def do_GET(self) -> None:
        route = urlsplit(self.path).path
        if route == "/api/info":
            self._send_json(
                200,
                {"mode": "local", "max_input_bytes": MAX_INPUT_BYTES},
            )
            return
        asset = STATIC_FILES.get(route)
        if asset is None:
            self._send_json(404, {"status": "not_found", "error": "Page not found."})
            return
        file_path, content_type = asset
        try:
            body = file_path.read_bytes()
        except OSError:
            self._send_json(500, {"status": "error", "error": "Unable to load the UI."})
            return
        self._send(200, body, content_type)

    def do_POST(self) -> None:
        if urlsplit(self.path).path != "/api/process":
            self._send_json(404, {"status": "not_found", "error": "Endpoint not found."})
            return
        if self.headers.get("Transfer-Encoding"):
            self._send_json(400, {"status": "rejected", "error": "Chunked uploads are not supported."})
            return
        try:
            content_length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            self._send_json(400, {"status": "rejected", "error": "A valid Content-Length is required."})
            return
        if content_length < 0:
            self._send_json(400, {"status": "rejected", "error": "Content-Length cannot be negative."})
            return
        if content_length > MAX_INPUT_BYTES:
            self._send_json(
                413,
                {"status": "rejected", "error": f"File exceeds the {MAX_INPUT_BYTES}-byte size limit."},
            )
            return

        payload = self.rfile.read(content_length)
        if len(payload) != content_length:
            self._send_json(400, {"status": "rejected", "error": "Upload ended before all bytes were received."})
            return
        try:
            result = process_upload(payload)
        except InvalidCSV as exc:
            self._send_json(400, {"status": "rejected", "error": str(exc)})
            return
        except Exception as exc:
            print(json.dumps({"event": "local_processing_failed", "error_type": type(exc).__name__}))
            self._send_json(500, {"status": "error", "error": "Processing failed unexpectedly."})
            return
        self._send_json(200, {"status": "success", **result})

    def log_message(self, format: str, *args: object) -> None:
        # The default access log includes request paths; keep local logs content-free.
        print(json.dumps({"event": "local_http_request", "status": str(args[1]) if len(args) > 1 else "unknown"}))


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 8000), LocalUIHandler)
    print("Local CSV UI running at http://127.0.0.1:8000 (Ctrl+C to stop).")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping local CSV UI.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
