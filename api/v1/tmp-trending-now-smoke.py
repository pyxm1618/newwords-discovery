from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler

from api.lib._config import BigQuerySettings, Settings
from api.lib._google_ads import GoogleAdsClient
from api.lib._google_bigquery import GoogleTrendsBigQueryClient
from api.lib._keyword_volume import (
    normalize_google_results,
    validate_keyword_volume_request,
)
from api.lib._trending_now import (
    GoogleTrendingNowClient,
    validate_trending_now_request,
)
from api.lib._trends import validate_trends_request


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        result = {"realtime": {}, "regression": {}}
        try:
            realtime_client = GoogleTrendingNowClient()
            for country_code in ("US", "IN", "BR"):
                request = validate_trending_now_request(
                    {
                        "country_code": country_code,
                        "hours": 4,
                        "limit": 1,
                        "hl": "en",
                    }
                )
                payload = realtime_client.fetch(request)
                rows = payload.get("results") or []
                if not rows:
                    raise RuntimeError(
                        f"Trending Now returned no rows for {country_code}"
                    )
                result["realtime"][country_code] = {
                    "source": payload.get("source"),
                    "observed_at": payload.get("observed_at"),
                    "count": len(rows),
                    "first_query": rows[0].get("query"),
                }

            trends_request = validate_trends_request(
                {"kind": "rising", "country_code": "US", "limit": 1}
            )
            trends = GoogleTrendsBigQueryClient(
                BigQuerySettings.from_env()
            ).fetch_terms(trends_request)
            if not trends.get("results"):
                raise RuntimeError("existing BigQuery path returned no rows")
            result["regression"]["bigquery"] = {
                "ok": True,
                "term": trends["results"][0].get("term"),
                "usage": trends.get("usage"),
            }

            ads_request = validate_keyword_volume_request(
                {"keywords": ["i ching online"]}
            )
            ads = normalize_google_results(
                GoogleAdsClient(Settings.from_env())
                .generate_historical_metrics(ads_request)
            )
            if not ads:
                raise RuntimeError("existing Google Ads path returned no rows")
            result["regression"]["google_ads"] = {
                "ok": True,
                "keyword": ads[0].get("keyword"),
                "avg_monthly_searches": ads[0].get("avg_monthly_searches"),
            }

            status = 200
            body = {"ok": True, **result}
        except Exception as exc:
            status = 500
            body = {
                "ok": False,
                "error_type": type(exc).__name__,
                "error": str(exc),
                **result,
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
