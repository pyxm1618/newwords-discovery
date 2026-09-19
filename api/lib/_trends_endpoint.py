from __future__ import annotations

from collections.abc import Callable, Mapping

from ._auth import is_authorized
from ._config import BigQuerySettings, ConfigError
from ._google_bigquery import (
    BigQueryServiceError,
    BigQueryTimeout,
    GoogleTrendsBigQueryClient,
)
from ._http import JSON_HEADERS, error_response, get_header, parse_json_body
from ._trends import TrendsRequestValidationError, validate_trends_request


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
        return error_response(405, "method_not_allowed", "only POST is supported")

    try:
        active_settings = settings or (settings_loader or BigQuerySettings.from_env)()
    except ConfigError:
        return error_response(
            500,
            "server_configuration_error",
            "server configuration is incomplete",
        )

    if not is_authorized(
        get_header(headers, "Authorization"),
        active_settings.api_key,
    ):
        return error_response(401, "unauthorized", "valid bearer token required")

    try:
        payload = parse_json_body(body)
    except ValueError as exc:
        return error_response(400, "invalid_request", str(exc))

    try:
        request = validate_trends_request(payload)
    except TrendsRequestValidationError as exc:
        return error_response(400, "invalid_request", str(exc))

    try:
        client = client_factory(active_settings)
        upstream = client.fetch_terms(request)
    except BigQueryTimeout:
        return error_response(504, "upstream_timeout", "BigQuery request timed out")
    except BigQueryServiceError:
        return error_response(502, "upstream_error", "BigQuery request failed")

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
