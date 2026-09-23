from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler

from api.lib._trending_now import (
    GoogleTrendingNowClient,
    validate_trending_now_request,
)


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        result = {}
        try:
            client = GoogleTrendingNowClient()
            for country_code in ("US", "IN", "BR"):
                request = validate_trending_now_request(
                    {
                        "country_code": country_code,
                        "hours": 4,
                        "limit": 3,
                        "hl": "en",
                    }
                )
                payload = client.fetch(request)
                rows = payload.get("results") or []
                result[country_code] = {
                    "source": payload.get("source"),
                    "observed_at": payload.get("observed_at"),
                    "count": len(rows),
                    "first": rows[0] if rows else None,
                }
            status = 200
            body = {"ok": True, "countries": result}
        except Exception as exc:
            status = 500
            body = {
                "ok": False,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "countries": result,
            }

        encoded = json.dumps(
            body, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args) -> None:
        return
