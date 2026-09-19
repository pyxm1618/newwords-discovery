from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from api.lib._config import BigQuerySettings
from api.lib._trends_endpoint import handle_trends


class handler(BaseHTTPRequestHandler):
    def _write_response(self, status, response_headers, payload) -> None:
        encoded = json.dumps(
            payload, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        self.send_response(status)
        for key, value in response_headers.items():
            self.send_header(key, value)
        if status == 405:
            self.send_header("Allow", "POST")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _dispatch(self) -> None:
        try:
            content_length = int(self.headers.get("Content-Length", "0") or "0")
        except ValueError:
            content_length = 0
        body = self.rfile.read(content_length) if content_length > 0 else b""
        status, response_headers, payload = handle_trends(
            self.command,
            {key: value for key, value in self.headers.items()},
            body,
        )
        self._write_response(status, response_headers, payload)

    def _preview_probe(self) -> None:
        if os.environ.get("VERCEL_ENV") != "preview":
            self._dispatch()
            return

        query = parse_qs(urlparse(self.path).query)
        kind = query.get("kind", ["rising"])[0]
        country_code = query.get("country_code", ["US"])[0]
        settings = BigQuerySettings.from_env()
        body = json.dumps(
            {
                "kind": kind,
                "country_code": country_code,
                "refresh_date": "2026-09-18",
                "limit": 3,
            }
        ).encode("utf-8")
        status, response_headers, payload = handle_trends(
            "POST",
            {"Authorization": f"Bearer {settings.api_key}"},
            body,
            settings=settings,
        )
        self._write_response(status, response_headers, payload)

    def do_POST(self) -> None:
        self._dispatch()

    def do_GET(self) -> None:
        self._preview_probe()

    def do_PUT(self) -> None:
        self._dispatch()

    def do_PATCH(self) -> None:
        self._dispatch()

    def do_DELETE(self) -> None:
        self._dispatch()

    def do_OPTIONS(self) -> None:
        self._dispatch()

    def log_message(self, format: str, *args) -> None:
        return
