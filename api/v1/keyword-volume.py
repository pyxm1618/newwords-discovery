from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler

from api.lib._endpoint import handle_keyword_volume


class handler(BaseHTTPRequestHandler):
    def _dispatch(self) -> None:
        try:
            content_length = int(self.headers.get("Content-Length", "0") or "0")
        except ValueError:
            content_length = 0
        body = self.rfile.read(content_length) if content_length > 0 else b""
        status, response_headers, payload = handle_keyword_volume(
            self.command,
            {key: value for key, value in self.headers.items()},
            body,
        )
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

    def do_POST(self) -> None:
        self._dispatch()

    def do_GET(self) -> None:
        self._dispatch()

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
