from __future__ import annotations

import anyio

import api.mcp as mcp_module


class _FakeTrendsClient:
    def __init__(self, settings):
        self.settings = settings

    def fetch_terms(self, request):
        return {
            "history": {"score_aggregation": "mean_across_available_regions"},
            "usage": {
                "total_bytes_processed": 123,
                "total_bytes_billed": 456,
                "cache_hit": False,
            },
            "results": [
                {
                    "term": "example term",
                    "rank": 1,
                    "percent_gain": 250,
                    "history": [
                        {
                            "week": "2026-09-20",
                            "score": 42,
                            "region_count": 10,
                        }
                    ],
                }
            ],
        }


class _FakeAdsClient:
    def __init__(self, settings):
        self.settings = settings

    def generate_historical_metrics(self, request):
        return {
            "results": [
                {
                    "text": request.keywords[0],
                    "keywordMetrics": {
                        "avgMonthlySearches": 1234,
                        "competition": "LOW",
                        "competitionIndex": "10",
                        "lowTopOfPageBidMicros": "1000000",
                        "highTopOfPageBidMicros": "2000000",
                        "monthlySearchVolumes": [],
                    },
                }
            ]
        }


def test_mcp_lists_expected_read_only_tools():
    tools = anyio.run(mcp_module.mcp.list_tools)
    by_name = {tool.name: tool for tool in tools}

    assert set(by_name) == {"get_trending_keywords", "get_trending_now", "get_keyword_volume"}
    assert by_name["get_trending_keywords"].annotations.read_only_hint is True
    assert by_name["get_trending_now"].annotations.read_only_hint is True
    assert by_name["get_keyword_volume"].annotations.read_only_hint is True


def test_get_trending_keywords_uses_existing_trends_contract(monkeypatch):
    monkeypatch.setattr(
        mcp_module.BigQuerySettings,
        "from_env",
        classmethod(lambda cls: object()),
    )
    monkeypatch.setattr(
        mcp_module,
        "GoogleTrendsBigQueryClient",
        _FakeTrendsClient,
    )

    result = mcp_module.get_trending_keywords(
        kind="rising",
        country_code="US",
        refresh_date="2026-09-22",
        limit=5,
    )

    assert result["source"] == "google_trends_bigquery"
    assert result["query"] == {
        "kind": "rising",
        "country_code": "US",
        "refresh_date": "2026-09-22",
        "limit": 5,
    }
    assert result["results"][0]["term"] == "example term"
    assert result["usage"]["total_bytes_processed"] == 123


def test_get_keyword_volume_uses_existing_ads_contract(monkeypatch):
    monkeypatch.setattr(
        mcp_module.Settings,
        "from_env",
        classmethod(lambda cls: object()),
    )
    monkeypatch.setattr(mcp_module, "GoogleAdsClient", _FakeAdsClient)

    result = mcp_module.get_keyword_volume(["i ching online"])

    assert result["source"] == "google_ads"
    assert result["query"]["geo_target_constant"] == "2840"
    assert result["results"][0]["keyword"] == "i ching online"
    assert result["results"][0]["avg_monthly_searches"] == 1234


def test_mcp_keyword_volume_has_stricter_public_batch_limit():
    try:
        mcp_module.get_keyword_volume(
            [f"keyword-{index}" for index in range(mcp_module.MCP_MAX_KEYWORDS + 1)]
        )
    except ValueError as exc:
        assert "at most 100" in str(exc)
    else:
        raise AssertionError("expected MCP batch limit to reject oversized request")
