from __future__ import annotations

from collections.abc import Callable, Mapping

from ._auth import is_authorized
from ._config import ConfigError, Settings
from ._google_ads import GoogleAdsClient, UpstreamServiceError, UpstreamTimeout
from ._http import JSON_HEADERS, error_response, get_header, parse_json_body
from ._keyword_volume import (
    RequestValidationError,
    normalize_google_results,
    validate_keyword_volume_request,
)


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
        return error_response(405, "method_not_allowed", "only POST is supported")

    try:
        active_settings = settings or (settings_loader or Settings.from_env)()
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
        request = validate_keyword_volume_request(payload)
    except RequestValidationError as exc:
        return error_response(400, "invalid_request", str(exc))

    client = client_factory(active_settings)
    try:
        upstream = client.generate_historical_metrics(request)
    except UpstreamTimeout:
        return error_response(504, "upstream_timeout", "Google upstream request timed out")
    except UpstreamServiceError:
        return error_response(502, "upstream_error", "Google upstream request failed")

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
