from __future__ import annotations

import json

from api.lib._trending_now_endpoint import handle_trending_now


class _Settings:
    api_key = "test-key"


class _FakeClient:
    def fetch(self, request):
        return {
            "source": "google_trending_now_rpc",
            "observed_at": "2026-09-23T00:00:00Z",
            "query": {
                "country_code": request.country_code,
                "hours": request.hours,
                "limit": request.limit,
                "hl": request.hl,
            },
            "results": [{"query": "example", "position": 1}],
        }


def _factory():
    return _FakeClient()


def test_trending_now_endpoint_requires_existing_bearer_auth():
    status, _, payload = handle_trending_now(
        "POST",
        {},
        b"{}",
        settings=_Settings(),
        client_factory=_factory,
    )

    assert status == 401
    assert payload["error"]["code"] == "unauthorized"


def test_trending_now_endpoint_returns_rpc_data_without_bigquery_or_ads_settings():
    status, _, payload = handle_trending_now(
        "POST",
        {"Authorization": "Bearer test-key"},
        json.dumps({"country_code": "BR", "hours": 4, "limit": 10}).encode(),
        settings=_Settings(),
        client_factory=_factory,
    )

    assert status == 200
    assert payload["source"] == "google_trending_now_rpc"
    assert payload["query"]["country_code"] == "BR"
    assert payload["query"]["hours"] == 4
    assert payload["results"][0]["query"] == "example"
