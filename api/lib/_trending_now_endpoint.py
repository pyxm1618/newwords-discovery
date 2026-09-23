from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from ._auth import is_authorized
from ._config import ConfigError
from ._http import JSON_HEADERS, error_response, get_header, parse_json_body
from ._trending_now import (
    GoogleTrendingNowClient,
    TrendingNowProtocolError,
    TrendingNowRateLimited,
    TrendingNowRequestValidationError,
    TrendingNowServiceError,
    TrendingNowTimeout,
    validate_trending_now_request,
)


@dataclass(frozen=True)
class TrendingNowSettings:
    api_key: str

    @classmethod
    def from_env(cls) -> "TrendingNowSettings":
        api_key = os.environ.get("SEO_DATA_API_KEY", "").strip()
        if not api_key:
            raise ConfigError(
                "missing required environment variable: SEO_DATA_API_KEY"
            )
        return cls(api_key=api_key)


def handle_trending_now(
    method: str,
    headers: Mapping[str, str],
    body: bytes,
    *,
    settings: TrendingNowSettings | None = None,
    settings_loader: Callable[[], TrendingNowSettings] | None = None,
    client_factory: Callable[[], GoogleTrendingNowClient] = GoogleTrendingNowClient,
):
    if method.upper() != "POST":
        return error_response(405, "method_not_allowed", "only POST is supported")

    try:
        active_settings = settings or (
            settings_loader or TrendingNowSettings.from_env
        )()
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
        return error_response(
            401,
            "unauthorized",
            "valid bearer token required",
        )

    try:
        payload = parse_json_body(body)
    except ValueError as exc:
        return error_response(400, "invalid_request", str(exc))

    try:
        request = validate_trending_now_request(payload)
    except TrendingNowRequestValidationError as exc:
        return error_response(400, "invalid_request", str(exc))

    try:
        result = client_factory().fetch(request)
    except TrendingNowRateLimited:
        return error_response(
            502,
            "upstream_rate_limited",
            "Google Trending Now RPC rate limited the request",
        )
    except TrendingNowTimeout:
        return error_response(
            504,
            "upstream_timeout",
            "Google Trending Now RPC request timed out",
        )
    except (TrendingNowProtocolError, TrendingNowServiceError):
        return error_response(
            502,
            "upstream_error",
            "Google Trending Now RPC request failed",
        )

    return 200, dict(JSON_HEADERS), result
