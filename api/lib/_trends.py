from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

DEFAULT_KIND = "rising"
DEFAULT_COUNTRY_CODE = "US"
MAX_LIMIT = 25
ALLOWED_KINDS = {"top", "rising"}

_TABLES = {
    ("US", "top"): "bigquery-public-data.google_trends.top_terms",
    ("US", "rising"): "bigquery-public-data.google_trends.top_rising_terms",
    ("INTL", "top"): "bigquery-public-data.google_trends.international_top_terms",
    ("INTL", "rising"): "bigquery-public-data.google_trends.international_top_rising_terms",
}


class TrendsRequestValidationError(ValueError):
    pass


@dataclass(frozen=True)
class TrendsRequest:
    kind: str
    country_code: str
    refresh_date: str
    limit: int


def _default_refresh_date() -> str:
    return (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()


def validate_trends_request(payload: object) -> TrendsRequest:
    if not isinstance(payload, dict):
        raise TrendsRequestValidationError("request body must be a JSON object")

    kind = payload.get("kind", DEFAULT_KIND)
    if not isinstance(kind, str):
        raise TrendsRequestValidationError("kind must be one of: rising, top")
    kind = kind.strip().lower()
    if kind not in ALLOWED_KINDS:
        raise TrendsRequestValidationError("kind must be one of: rising, top")

    country_code = payload.get("country_code", DEFAULT_COUNTRY_CODE)
    if not isinstance(country_code, str):
        raise TrendsRequestValidationError("country_code must be a two-letter ISO code")
    country_code = country_code.strip().upper()
    if not re.fullmatch(r"[A-Z]{2}", country_code):
        raise TrendsRequestValidationError("country_code must be a two-letter ISO code")

    refresh_date = payload.get("refresh_date") or _default_refresh_date()
    if not isinstance(refresh_date, str):
        raise TrendsRequestValidationError("refresh_date must be YYYY-MM-DD")
    refresh_date = refresh_date.strip()
    try:
        datetime.strptime(refresh_date, "%Y-%m-%d")
    except ValueError as exc:
        raise TrendsRequestValidationError("refresh_date must be YYYY-MM-DD") from exc

    limit = payload.get("limit", MAX_LIMIT)
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise TrendsRequestValidationError(f"limit must be an integer from 1 to {MAX_LIMIT}")
    if not 1 <= limit <= MAX_LIMIT:
        raise TrendsRequestValidationError(f"limit must be an integer from 1 to {MAX_LIMIT}")

    return TrendsRequest(
        kind=kind,
        country_code=country_code,
        refresh_date=refresh_date,
        limit=limit,
    )


def trends_table_name(request: TrendsRequest) -> str:
    market = "US" if request.country_code == "US" else "INTL"
    return _TABLES[(market, request.kind)]


def build_trends_query(request: TrendsRequest) -> str:
    table = trends_table_name(request)
    country_filter = ""
    if request.country_code != "US":
        country_filter = "\n  AND country_code = @country_code"

    return f"""SELECT
  term,
  MIN(rank) AS rank
FROM `{table}`
WHERE refresh_date = @refresh_date{country_filter}
GROUP BY term
ORDER BY rank ASC, term ASC
LIMIT {request.limit}
"""
