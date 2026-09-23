from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse

import pytest

from api.lib._trending_now import (
    GoogleTrendingNowClient,
    TrendingNowProtocolError,
    TrendingNowRateLimited,
    TrendingNowRequestValidationError,
    build_trending_now_http_request,
    normalize_trending_rows,
    parse_batchexecute_response,
    validate_trending_now_request,
)


class _FakeTransport:
    def __init__(self, payload):
        self.payload = payload
        self.seen = []

    def fetch(self, request):
        self.seen.append(request)
        return self.payload


def test_validate_trending_now_defaults_to_us_four_hours_and_fifty_rows():
    request = validate_trending_now_request({})

    assert request.country_code == "US"
    assert request.hours == 4
    assert request.limit == 50
    assert request.hl == "en"


@pytest.mark.parametrize("hours", [4, 24, 48, 168])
def test_validate_trending_now_accepts_supported_windows(hours):
    request = validate_trending_now_request(
        {"country_code": "br", "hours": hours, "limit": 25, "hl": "pt-BR"}
    )

    assert request.country_code == "BR"
    assert request.hours == hours
    assert request.limit == 25
    assert request.hl == "pt-BR"


@pytest.mark.parametrize("hours", [1, 6, 12, 72])
def test_validate_trending_now_rejects_unsupported_windows(hours):
    with pytest.raises(TrendingNowRequestValidationError, match="hours must be one of"):
        validate_trending_now_request({"hours": hours})


def test_validate_trending_now_rejects_invalid_country_and_limit():
    with pytest.raises(TrendingNowRequestValidationError):
        validate_trending_now_request({"country_code": "USA"})
    with pytest.raises(TrendingNowRequestValidationError):
        validate_trending_now_request({"limit": 101})


def test_build_trending_now_http_request_targets_i0ofe_without_credentials():
    request = validate_trending_now_request(
        {"country_code": "IN", "hours": 4, "limit": 20, "hl": "en-IN"}
    )

    http_request = build_trending_now_http_request(request)
    parsed_url = urlparse(http_request.url)
    query = parse_qs(parsed_url.query)
    form = parse_qs(http_request.body.decode("utf-8"))
    outer = json.loads(form["f.req"][0])
    inner = json.loads(outer[0][0][1])

    assert parsed_url.netloc == "trends.google.com"
    assert parsed_url.path.endswith("/batchexecute")
    assert query["rpcids"] == ["i0OFE"]
    assert query["source-path"] == ["/trending"]
    assert query["hl"] == ["en-IN"]
    assert inner == [None, None, "IN", 0, "en-IN", 4, 1]
    assert "Authorization" not in http_request.headers


def test_parse_batchexecute_response_extracts_i0ofe_frame():
    payload = [None, [["term", None, "US", [100], None, None, 50000, None, 900, [], [], [], "term"]]]
    frame = [["wrb.fr", "i0OFE", json.dumps(payload), None, None, None, "generic"]]
    body = ")]}'\n\n123\n" + json.dumps(frame)

    assert parse_batchexecute_response(body) == payload


def test_parse_batchexecute_response_rejects_missing_rpc_frame():
    with pytest.raises(TrendingNowProtocolError, match="i0OFE"):
        parse_batchexecute_response(")]}'\n[[]]")


def test_normalize_trending_rows_preserves_rpc_fields_and_limits():
    request = validate_trending_now_request(
        {"country_code": "US", "hours": 4, "limit": 1}
    )
    payload = [
        None,
        [
            [
                "example trend",
                None,
                "US",
                [1783296000],
                None,
                None,
                50000,
                None,
                1200,
                ["example trend", "example query"],
                [18],
                [[123, "en", "US"]],
                "example trend",
            ],
            ["second", None, "US", [1783296001], None, None, 10000, None, 500, [], [], [], "second"],
        ],
    ]

    results = normalize_trending_rows(payload, request)

    assert len(results) == 1
    item = results[0]
    assert item["position"] == 1
    assert item["query"] == "example trend"
    assert item["search_volume"] == 50000
    assert item["search_volume_label"] == "50000+"
    assert item["increase_percentage"] == 1200
    assert item["start_timestamp"] == 1783296000
    assert item["ended_at"] is None
    assert item["active"] is True
    assert item["trend_breakdown"] == ["example trend", "example query"]
    assert item["category_ids"] == [18]
    assert item["news_refs"] == [{"id": 123, "lang": "en", "geo": "US"}]
    assert item["source"] == "google_trending_now_rpc"


def test_google_trending_now_client_uses_transport_and_returns_envelope():
    request = validate_trending_now_request(
        {"country_code": "US", "hours": 4, "limit": 5}
    )
    transport = _FakeTransport(
        [None, [["term", None, "US", [1783296000], None, None, 20000, None, 600, [], [], [], "term"]]]
    )

    result = GoogleTrendingNowClient(transport=transport).fetch(request)

    assert transport.seen == [request]
    assert result["source"] == "google_trending_now_rpc"
    assert result["query"] == {
        "country_code": "US",
        "hours": 4,
        "limit": 5,
        "hl": "en",
    }
    assert result["results"][0]["query"] == "term"
    assert result["observed_at"].endswith("Z")


def test_google_trending_now_client_does_not_fallback_on_rate_limit():
    class RateLimitedTransport:
        def fetch(self, request):
            raise TrendingNowRateLimited("rate limited")

    request = validate_trending_now_request({})

    with pytest.raises(TrendingNowRateLimited):
        GoogleTrendingNowClient(transport=RateLimitedTransport()).fetch(request)
