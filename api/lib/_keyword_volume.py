from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DEFAULT_GEO_TARGET_CONSTANT = "2840"
DEFAULT_LANGUAGE_CONSTANT = "1000"
DEFAULT_NETWORK = "GOOGLE_SEARCH"
MAX_KEYWORDS = 10_000
ALLOWED_NETWORKS = {"GOOGLE_SEARCH", "GOOGLE_SEARCH_AND_PARTNERS"}


class RequestValidationError(ValueError):
    pass


@dataclass(frozen=True)
class KeywordVolumeRequest:
    keywords: tuple[str, ...]
    geo_target_constant: str = DEFAULT_GEO_TARGET_CONSTANT
    language_constant: str = DEFAULT_LANGUAGE_CONSTANT
    network: str = DEFAULT_NETWORK


def _normalize_constant(value: Any, field: str, default: str) -> str:
    if value is None:
        return default
    if isinstance(value, int):
        value = str(value)
    if not isinstance(value, str):
        raise RequestValidationError(f"{field} must be a numeric Google Ads constant id")
    value = value.strip()
    if not value.isdigit():
        raise RequestValidationError(f"{field} must be a numeric Google Ads constant id")
    return value


def validate_keyword_volume_request(payload: object) -> KeywordVolumeRequest:
    if not isinstance(payload, dict):
        raise RequestValidationError("request body must be a JSON object")

    raw_keywords = payload.get("keywords")
    if not isinstance(raw_keywords, list) or not raw_keywords:
        raise RequestValidationError("keywords must be a non-empty array of strings")
    if len(raw_keywords) > MAX_KEYWORDS:
        raise RequestValidationError(f"keywords may contain at most {MAX_KEYWORDS} items")

    keywords: list[str] = []
    seen: set[str] = set()
    for raw in raw_keywords:
        if not isinstance(raw, str):
            raise RequestValidationError("keywords must be a non-empty array of strings")
        keyword = raw.strip()
        if not keyword:
            raise RequestValidationError("keywords must be a non-empty array of strings")
        if keyword not in seen:
            seen.add(keyword)
            keywords.append(keyword)

    network = payload.get("network", DEFAULT_NETWORK)
    if not isinstance(network, str) or network not in ALLOWED_NETWORKS:
        allowed = ", ".join(sorted(ALLOWED_NETWORKS))
        raise RequestValidationError(f"network must be one of: {allowed}")

    return KeywordVolumeRequest(
        keywords=tuple(keywords),
        geo_target_constant=_normalize_constant(
            payload.get("geo_target_constant"),
            "geo_target_constant",
            DEFAULT_GEO_TARGET_CONSTANT,
        ),
        language_constant=_normalize_constant(
            payload.get("language_constant"),
            "language_constant",
            DEFAULT_LANGUAGE_CONSTANT,
        ),
        network=network,
    )


def _optional_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_google_results(data: dict[str, Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in data.get("results", []) or []:
        metrics = item.get("keywordMetrics") or {}
        monthly = []
        for entry in metrics.get("monthlySearchVolumes", []) or []:
            monthly.append(
                {
                    "year": _optional_int(entry.get("year")),
                    "month": entry.get("month"),
                    "monthly_searches": _optional_int(entry.get("monthlySearches")),
                }
            )

        normalized.append(
            {
                "keyword": item.get("text"),
                "close_variants": list(item.get("closeVariants") or []),
                "avg_monthly_searches": _optional_int(metrics.get("avgMonthlySearches")),
                "competition": metrics.get("competition"),
                "competition_index": _optional_int(metrics.get("competitionIndex")),
                "low_top_of_page_bid_micros": _optional_int(
                    metrics.get("lowTopOfPageBidMicros")
                ),
                "high_top_of_page_bid_micros": _optional_int(
                    metrics.get("highTopOfPageBidMicros")
                ),
                "monthly_search_volumes": monthly,
            }
        )
    return normalized
