import pytest

from api.lib._keyword_volume import (
    RequestValidationError,
    normalize_google_results,
    validate_keyword_volume_request,
)


def test_request_defaults_and_deduplicates_keywords_preserving_order():
    request = validate_keyword_volume_request(
        {"keywords": [" i ching online ", "i ching reading", "i ching online"]}
    )

    assert request.keywords == ("i ching online", "i ching reading")
    assert request.geo_target_constant == "2840"
    assert request.language_constant == "1000"
    assert request.network == "GOOGLE_SEARCH"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"keywords": []},
        {"keywords": "i ching online"},
        {"keywords": [""]},
        {"keywords": [123]},
    ],
)
def test_request_rejects_invalid_keywords(payload):
    with pytest.raises(RequestValidationError):
        validate_keyword_volume_request(payload)


def test_request_rejects_more_than_10000_keywords():
    with pytest.raises(RequestValidationError):
        validate_keyword_volume_request({"keywords": [f"kw-{i}" for i in range(10001)]})


def test_request_rejects_invalid_network():
    with pytest.raises(RequestValidationError):
        validate_keyword_volume_request(
            {"keywords": ["i ching online"], "network": "DISPLAY"}
        )


def test_request_accepts_explicit_google_constants():
    request = validate_keyword_volume_request(
        {
            "keywords": ["i ching online"],
            "geo_target_constant": 2840,
            "language_constant": "1000",
            "network": "GOOGLE_SEARCH_AND_PARTNERS",
        }
    )

    assert request.geo_target_constant == "2840"
    assert request.language_constant == "1000"
    assert request.network == "GOOGLE_SEARCH_AND_PARTNERS"


def test_normalization_preserves_missing_metrics_as_none_and_numeric_zero_as_zero():
    data = {
        "results": [
            {
                "text": "three coin method",
                "keywordMetrics": {
                    "competitionIndex": "0",
                    "monthlySearchVolumes": [
                        {"year": "2026", "month": "AUGUST"}
                    ],
                },
            }
        ]
    }

    results = normalize_google_results(data)

    assert results == [
        {
            "keyword": "three coin method",
            "avg_monthly_searches": None,
            "competition": None,
            "competition_index": 0,
            "low_top_of_page_bid_micros": None,
            "high_top_of_page_bid_micros": None,
            "monthly_search_volumes": [
                {"year": 2026, "month": "AUGUST", "monthly_searches": None}
            ],
        }
    ]
