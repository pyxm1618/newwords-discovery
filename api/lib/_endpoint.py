from __future__ import annotations

import json
from collections.abc import Callable, Mapping

from ._auth import is_authorized
from ._config import BigQuerySettings, ConfigError, Settings
from ._google_ads import GoogleAdsClient, UpstreamServiceError, UpstreamTimeout
from ._google_bigquery import (
    BigQueryServiceError,
    BigQueryTimeout,
    GoogleTrendsBigQueryClient,
)
from ._keyword_volume import (
    RequestValidationError,
    normalize_google_results,
    validate_keyword_volume_request,
)
from ._trends import TrendsRequestValidationError, validate_trends_request

JSON_HEADERS = {"Content-Type": "application/json; charset=utf-8"}


def _error(status: int, code: str, message: str):
    return status, dict(JSON_HEADERS), {"error": {"code": code, "message": message}}


def _header(headers: Mapping[str, str], name: str) -> str | None:
    target = name.lower()
    for key, value in headers.items():
        if key.lower() == target:
            return value
    return None


def handle_keyword_volume(
    method: str,
    headers: Mapping[str, str],
    body: bytes,
    *,
    settings: Settings | None = None,
    settings_loader: Callable[[], Settings] | None = None,
    client_factory: Callable[[Settings], GoogleAdsClient] = GoogleAdsClient,
):
    if method.upper() != "POST":
        return _error(405, "method_not_allowed", "only POST is supported")

    try:
        active_settings = settings or (settings_loader or Settings.from_env)()
    except ConfigError:
        return _error(
            500,
            "server_configuration_error",
            "server configuration is incomplete",
        )

    if not is_authorized(_header(headers, "Authorization"), active_settings.api_key):
        return _error(401, "unauthorized", "valid bearer token required")

    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _error(400, "invalid_request", "request body must be valid JSON")

    try:
        request = validate_keyword_volume_request(payload)
    except RequestValidationError as exc:
        return _error(400, "invalid_request", str(exc))

    client = client_factory(active_settings)
    try:
        upstream = client.generate_historical_metrics(request)
    except UpstreamTimeout:
        return _error(504, "upstream_timeout", "Google upstream request timed out")
    except UpstreamServiceError:
        return _error(502, "upstream_error", "Google upstream request failed")

    return (
        200,
        dict(JSON_HEADERS),
        {
            "source": "google_ads",
            "query": {
                "geo_target_constant": request.geo_target_constant,
                "language_constant": request.language_constant,
                "network": request.network,
            },
            "results": normalize_google_results(upstream),
        },
    )


def handle_trends(
    method: str,
    headers: Mapping[str, str],
    body: bytes,
    *,
    settings: BigQuerySettings | None = None,
    settings_loader: Callable[[], BigQuerySettings] | None = None,
    client_factory: Callable[
        [BigQuerySettings], GoogleTrendsBigQueryClient
    ] = GoogleTrendsBigQueryClient,
):
    if method.upper() != "POST":
        return _error(405, "method_not_allowed", "only POST is supported")

    try:
        active_settings = settings or (settings_loader or BigQuerySettings.from_env)()
    except ConfigError:
        return _error(
            500,
            "server_configuration_error",
            "server configuration is incomplete",
        )

    if not is_authorized(_header(headers, "Authorization"), active_settings.api_key):
        return _error(401, "unauthorized", "valid bearer token required")

    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _error(400, "invalid_request", "request body must be valid JSON")

    try:
        request = validate_trends_request(payload)
    except TrendsRequestValidationError as exc:
        return _error(400, "invalid_request", str(exc))

    try:
        client = client_factory(active_settings)
        upstream = client.fetch_terms(request)
    except BigQueryTimeout:
        return _error(504, "upstream_timeout", "BigQuery request timed out")
    except BigQueryServiceError:
        return _error(502, "upstream_error", "BigQuery request failed")

    return (
        200,
        dict(JSON_HEADERS),
        {
            "source": "google_trends_bigquery",
            "query": {
                "kind": request.kind,
                "country_code": request.country_code,
                "refresh_date": request.refresh_date,
                "limit": request.limit,
            },
            "usage": upstream["usage"],
            "results": upstream["results"],
        },
    )
