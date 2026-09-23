from __future__ import annotations

from typing import Any, Literal

from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations

from api.lib._config import BigQuerySettings, ConfigError, Settings
from api.lib._google_ads import GoogleAdsClient, UpstreamServiceError, UpstreamTimeout
from api.lib._google_bigquery import (
    BigQueryServiceError,
    BigQueryTimeout,
    GoogleTrendsBigQueryClient,
)
from api.lib._keyword_volume import (
    RequestValidationError,
    normalize_google_results,
    validate_keyword_volume_request,
)
from api.lib._trends import TrendsRequestValidationError, validate_trends_request
from api.lib._trending_now import (
    GoogleTrendingNowClient,
    TrendingNowProtocolError,
    TrendingNowRateLimited,
    TrendingNowRequestValidationError,
    TrendingNowServiceError,
    TrendingNowTimeout,
    validate_trending_now_request,
)


MCP_MAX_KEYWORDS = 100

mcp = MCPServer(
    "newwords-discovery",
    instructions=(
        "Read-only SEO discovery data. Use get_trending_now for real-time "
        "Google Trending Now discovery, get_trending_keywords for daily "
        "Top/Rising lifecycle validation, and get_keyword_volume only after "
        "a candidate has passed the SEO opportunity filter."
    ),
)

READ_ONLY_EXTERNAL = ToolAnnotations(
    read_only_hint=True,
    idempotent_hint=True,
    open_world_hint=True,
)


def _public_config_error() -> RuntimeError:
    return RuntimeError("Newwords Discovery server configuration is incomplete.")


@mcp.tool(
    title="Get trending keywords",
    description=(
        "Return Google Trends Top or Rising candidates for one country and "
        "refresh date, including rank, percent gain when available, complete "
        "rolling weekly history, history metadata, and BigQuery usage. "
        "Use this as the discovery source; do not treat rank or Trends score "
        "as search volume or SEO difficulty."
    ),
    annotations=READ_ONLY_EXTERNAL,
)
def get_trending_keywords(
    kind: Literal["rising", "top"] = "rising",
    country_code: str = "US",
    refresh_date: str | None = None,
    limit: int = 25,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "kind": kind,
        "country_code": country_code,
        "limit": limit,
    }
    if refresh_date:
        payload["refresh_date"] = refresh_date

    try:
        request = validate_trends_request(payload)
        settings = BigQuerySettings.from_env()
    except TrendsRequestValidationError as exc:
        raise ValueError(str(exc)) from exc
    except ConfigError as exc:
        raise _public_config_error() from exc

    try:
        upstream = GoogleTrendsBigQueryClient(settings).fetch_terms(request)
    except BigQueryTimeout as exc:
        raise RuntimeError("Google Trends BigQuery request timed out.") from exc
    except BigQueryServiceError as exc:
        raise RuntimeError("Google Trends BigQuery request failed.") from exc

    return {
        "source": "google_trends_bigquery",
        "query": {
            "kind": request.kind,
            "country_code": request.country_code,
            "refresh_date": request.refresh_date,
            "limit": request.limit,
        },
        "history": {
            "window": "rolling_5_years",
            "granularity": "week",
            "score_aggregation": upstream["history"]["score_aggregation"],
        },
        "usage": upstream["usage"],
        "results": upstream["results"],
    }


@mcp.tool(
    title="Get trending now",
    description=(
        "Return Google Trends Trending Now results from the current web RPC "
        "for one country and one supported window: 4, 24, 48, or 168 hours. "
        "This is the real-time discovery source. It does not use BigQuery, "
        "Google Ads, the Google Trends API Alpha, or RSS fallback. "
        "If Google rate-limits or changes the undocumented RPC, the tool fails "
        "explicitly instead of silently substituting another source."
    ),
    annotations=READ_ONLY_EXTERNAL,
)
def get_trending_now(
    country_code: str = "US",
    hours: Literal[4, 24, 48, 168] = 4,
    limit: int = 50,
    hl: str = "en",
) -> dict[str, Any]:
    try:
        request = validate_trending_now_request(
            {
                "country_code": country_code,
                "hours": hours,
                "limit": limit,
                "hl": hl,
            }
        )
    except TrendingNowRequestValidationError as exc:
        raise ValueError(str(exc)) from exc

    try:
        return GoogleTrendingNowClient().fetch(request)
    except TrendingNowRateLimited as exc:
        raise RuntimeError(
            "Google Trending Now RPC rate limited the request."
        ) from exc
    except TrendingNowTimeout as exc:
        raise RuntimeError("Google Trending Now RPC request timed out.") from exc
    except (TrendingNowProtocolError, TrendingNowServiceError) as exc:
        raise RuntimeError("Google Trending Now RPC request failed.") from exc


@mcp.tool(
    title="Get keyword volume",
    description=(
        "Return Google Ads historical keyword metrics for retained candidates. "
        "Default market is United States (geo 2840), English (language 1000), "
        "Google Search. Google Ads competition is advertising competition, "
        "not SEO keyword difficulty. This tool is a validation step, not a "
        "new-keyword discovery source."
    ),
    annotations=READ_ONLY_EXTERNAL,
)
def get_keyword_volume(
    keywords: list[str],
    geo_target_constant: str = "2840",
    language_constant: str = "1000",
    network: Literal["GOOGLE_SEARCH", "GOOGLE_SEARCH_AND_PARTNERS"] = "GOOGLE_SEARCH",
) -> dict[str, Any]:
    if len(keywords) > MCP_MAX_KEYWORDS:
        raise ValueError(
            f"keywords may contain at most {MCP_MAX_KEYWORDS} items through MCP"
        )

    try:
        request = validate_keyword_volume_request(
            {
                "keywords": keywords,
                "geo_target_constant": geo_target_constant,
                "language_constant": language_constant,
                "network": network,
            }
        )
        settings = Settings.from_env()
    except RequestValidationError as exc:
        raise ValueError(str(exc)) from exc
    except ConfigError as exc:
        raise _public_config_error() from exc

    try:
        upstream = GoogleAdsClient(settings).generate_historical_metrics(request)
    except UpstreamTimeout as exc:
        raise RuntimeError("Google Ads request timed out.") from exc
    except UpstreamServiceError as exc:
        raise RuntimeError("Google Ads request failed.") from exc

    return {
        "source": "google_ads",
        "query": {
            "geo_target_constant": request.geo_target_constant,
            "language_constant": request.language_constant,
            "network": request.network,
        },
        "results": normalize_google_results(upstream),
    }


_transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=False
)

app = mcp.streamable_http_app(
    streamable_http_path="/api/mcp",
    json_response=True,
    stateless_http=True,
    max_request_body_size=256 * 1024,
    transport_security=_transport_security,
)
