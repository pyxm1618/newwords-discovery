from __future__ import annotations

import json
import re
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request as UrlRequest, urlopen


RPC_ID = "i0OFE"
BATCH_URL = "https://trends.google.com/_/TrendsUi/data/batchexecute"
ALLOWED_HOURS = {4, 24, 48, 168}
DEFAULT_COUNTRY_CODE = "US"
DEFAULT_HOURS = 4
DEFAULT_LIMIT = 50
DEFAULT_HL = "en"
MAX_LIMIT = 100
DEFAULT_TIMEOUT_SECONDS = 20


class TrendingNowRequestValidationError(ValueError):
    pass


class TrendingNowTimeout(RuntimeError):
    pass


class TrendingNowRateLimited(RuntimeError):
    pass


class TrendingNowServiceError(RuntimeError):
    pass


class TrendingNowProtocolError(RuntimeError):
    pass


@dataclass(frozen=True)
class TrendingNowRequest:
    country_code: str
    hours: int
    limit: int
    hl: str


@dataclass(frozen=True)
class TrendingNowHttpRequest:
    url: str
    body: bytes
    headers: dict[str, str]


class TrendingNowTransport(Protocol):
    def fetch(self, request: TrendingNowRequest) -> Any: ...


def validate_trending_now_request(payload: object) -> TrendingNowRequest:
    if not isinstance(payload, dict):
        raise TrendingNowRequestValidationError("request body must be a JSON object")

    country_code = payload.get("country_code", DEFAULT_COUNTRY_CODE)
    if not isinstance(country_code, str):
        raise TrendingNowRequestValidationError(
            "country_code must be a two-letter ISO code"
        )
    country_code = country_code.strip().upper()
    if not re.fullmatch(r"[A-Z]{2}", country_code):
        raise TrendingNowRequestValidationError(
            "country_code must be a two-letter ISO code"
        )

    hours = payload.get("hours", DEFAULT_HOURS)
    if isinstance(hours, bool) or not isinstance(hours, int):
        raise TrendingNowRequestValidationError(
            "hours must be one of: 4, 24, 48, 168"
        )
    if hours not in ALLOWED_HOURS:
        raise TrendingNowRequestValidationError(
            "hours must be one of: 4, 24, 48, 168"
        )

    limit = payload.get("limit", DEFAULT_LIMIT)
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise TrendingNowRequestValidationError(
            f"limit must be an integer from 1 to {MAX_LIMIT}"
        )
    if not 1 <= limit <= MAX_LIMIT:
        raise TrendingNowRequestValidationError(
            f"limit must be an integer from 1 to {MAX_LIMIT}"
        )

    hl = payload.get("hl", DEFAULT_HL)
    if not isinstance(hl, str) or not hl.strip():
        raise TrendingNowRequestValidationError("hl must be a non-empty locale")
    hl = hl.strip()
    if len(hl) > 35 or not re.fullmatch(r"[A-Za-z0-9-]+", hl):
        raise TrendingNowRequestValidationError(
            "hl must contain only letters, digits, and hyphens"
        )

    return TrendingNowRequest(
        country_code=country_code,
        hours=hours,
        limit=limit,
        hl=hl,
    )


def build_trending_now_http_request(
    request: TrendingNowRequest,
) -> TrendingNowHttpRequest:
    inner_payload = [
        None,
        None,
        request.country_code,
        0,
        request.hl,
        request.hours,
        1,
    ]
    outer_payload = [
        [[RPC_ID, json.dumps(inner_payload, separators=(",", ":")), None, "generic"]]
    ]

    query = urlencode(
        {
            "rpcids": RPC_ID,
            "source-path": "/trending",
            "hl": request.hl,
            "rt": "c",
        }
    )
    body = urlencode(
        {"f.req": json.dumps(outer_payload, separators=(",", ":"))}
    ).encode("utf-8")
    return TrendingNowHttpRequest(
        url=f"{BATCH_URL}?{query}",
        body=body,
        headers={
            "Accept": "*/*",
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "Origin": "https://trends.google.com",
            "Referer": "https://trends.google.com/trending",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/143.0.0.0 Safari/537.36"
            ),
        },
    )


def _extract_json_arrays(text: str) -> list[str]:
    arrays: list[str] = []
    index = 0
    while index < len(text):
        if text[index] != "[":
            index += 1
            continue

        start = index
        depth = 0
        in_string = False
        escaped = False
        while index < len(text):
            char = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                index += 1
                continue

            if char == '"':
                in_string = True
            elif char == "[":
                depth += 1
            elif char == "]":
                depth -= 1
                if depth == 0:
                    arrays.append(text[start : index + 1])
                    index += 1
                    break
            index += 1
        else:
            break
    return arrays


def parse_batchexecute_response(text: str, rpc_id: str = RPC_ID) -> Any:
    body = text.strip()
    if body.startswith(")]}'"):
        body = body[4:]

    for raw_array in _extract_json_arrays(body):
        try:
            parsed = json.loads(raw_array)
        except json.JSONDecodeError:
            continue
        if not isinstance(parsed, list):
            continue
        for candidate in parsed:
            if (
                isinstance(candidate, list)
                and len(candidate) >= 3
                and candidate[0] == "wrb.fr"
                and candidate[1] == rpc_id
                and isinstance(candidate[2], str)
            ):
                try:
                    return json.loads(candidate[2])
                except json.JSONDecodeError as exc:
                    raise TrendingNowProtocolError(
                        f"Google Trending Now RPC {rpc_id} returned invalid JSON"
                    ) from exc

    raise TrendingNowProtocolError(
        f"Google Trending Now batchexecute response did not include {rpc_id}"
    )


def _timestamp_from_value(value: Any) -> int | None:
    if isinstance(value, list) and value:
        value = value[0]
    if isinstance(value, bool):
        return None
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return None
    return numeric


def _iso_from_timestamp(value: int | None) -> str | None:
    if value is None:
        return None
    try:
        return (
            datetime.fromtimestamp(value, tz=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )
    except (OverflowError, OSError, ValueError):
        return None


def _optional_number(value: Any) -> int | float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if numeric.is_integer():
        return int(numeric)
    return numeric


def _search_volume_label(value: int | float | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and not value.is_integer():
        return f"{value}+"
    return f"{int(value)}+"


def _category_ids(value: Any) -> list[int]:
    if not isinstance(value, list):
        return []
    result: list[int] = []
    for item in value:
        if isinstance(item, bool):
            continue
        try:
            result.append(int(item))
        except (TypeError, ValueError):
            continue
    return result


def _news_refs(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    result: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, list) or not item:
            continue
        try:
            article_id = int(item[0])
        except (TypeError, ValueError):
            continue
        result.append(
            {
                "id": article_id,
                "lang": str(item[1]) if len(item) > 1 and item[1] is not None else "",
                "geo": str(item[2]) if len(item) > 2 and item[2] is not None else "",
            }
        )
    return result


def _explore_url(query: str, request: TrendingNowRequest) -> str:
    if request.hours == 4:
        date_token = "now 4-H"
    elif request.hours == 24:
        date_token = "now 1-d"
    else:
        date_token = "now 7-d"
    return (
        "https://trends.google.com/trends/explore?"
        + urlencode(
            {
                "date": date_token,
                "geo": request.country_code,
                "q": query,
            },
            quote_via=quote,
        )
    )


def normalize_trending_rows(
    payload: Any,
    request: TrendingNowRequest,
) -> list[dict[str, Any]]:
    if not isinstance(payload, list) or len(payload) < 2 or not isinstance(
        payload[1], list
    ):
        return []

    results: list[dict[str, Any]] = []
    for row in payload[1]:
        if not isinstance(row, list) or not row or not isinstance(row[0], str):
            continue

        query = row[0]
        geo = (
            row[2]
            if len(row) > 2 and isinstance(row[2], str)
            else request.country_code
        )
        start_timestamp = _timestamp_from_value(row[3] if len(row) > 3 else None)
        end_timestamp = _timestamp_from_value(row[4] if len(row) > 4 else None)
        search_volume = _optional_number(row[6] if len(row) > 6 else None)
        increase_percentage = _optional_number(row[8] if len(row) > 8 else None)
        breakdown = (
            [item for item in row[9] if isinstance(item, str)]
            if len(row) > 9 and isinstance(row[9], list)
            else []
        )
        normalized_query = (
            row[12]
            if len(row) > 12 and isinstance(row[12], str) and row[12]
            else query
        )

        results.append(
            {
                "position": len(results) + 1,
                "query": query,
                "normalized_query": normalized_query,
                "country_code": geo,
                "search_volume": search_volume,
                "search_volume_label": _search_volume_label(search_volume),
                "increase_percentage": increase_percentage,
                "started_at": _iso_from_timestamp(start_timestamp),
                "ended_at": _iso_from_timestamp(end_timestamp),
                "start_timestamp": start_timestamp,
                "end_timestamp": end_timestamp,
                "active": end_timestamp is None,
                "trend_breakdown": breakdown,
                "category_ids": _category_ids(row[10] if len(row) > 10 else None),
                "news_refs": _news_refs(row[11] if len(row) > 11 else None),
                "explore_url": _explore_url(normalized_query, request),
                "source": "google_trending_now_rpc",
            }
        )
        if len(results) >= request.limit:
            break

    return results


class GoogleTrendingNowTransport:
    def __init__(self, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS):
        self.timeout_seconds = timeout_seconds

    def fetch(self, request: TrendingNowRequest) -> Any:
        spec = build_trending_now_http_request(request)
        http_request = UrlRequest(
            spec.url,
            data=spec.body,
            headers=spec.headers,
            method="POST",
        )
        try:
            with urlopen(http_request, timeout=self.timeout_seconds) as response:
                text = response.read().decode("utf-8")
        except HTTPError as exc:
            if exc.code == 429:
                raise TrendingNowRateLimited(
                    "Google Trending Now RPC rate limited the request"
                ) from exc
            raise TrendingNowServiceError(
                f"Google Trending Now RPC returned HTTP {exc.code}"
            ) from exc
        except (TimeoutError, socket.timeout) as exc:
            raise TrendingNowTimeout("Google Trending Now RPC timed out") from exc
        except URLError as exc:
            if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                raise TrendingNowTimeout(
                    "Google Trending Now RPC timed out"
                ) from exc
            raise TrendingNowServiceError(
                "Google Trending Now RPC request failed"
            ) from exc

        return parse_batchexecute_response(text)


class GoogleTrendingNowClient:
    def __init__(self, transport: TrendingNowTransport | None = None):
        self.transport = transport or GoogleTrendingNowTransport()

    def fetch(self, request: TrendingNowRequest) -> dict[str, Any]:
        payload = self.transport.fetch(request)
        observed_at = (
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )
        return {
            "source": "google_trending_now_rpc",
            "observed_at": observed_at,
            "query": {
                "country_code": request.country_code,
                "hours": request.hours,
                "limit": request.limit,
                "hl": request.hl,
            },
            "source_url": (
                "https://trends.google.com/trending?"
                + urlencode(
                    {
                        "geo": request.country_code,
                        "hl": request.hl,
                        "hours": request.hours,
                    }
                )
            ),
            "results": normalize_trending_rows(payload, request),
        }
