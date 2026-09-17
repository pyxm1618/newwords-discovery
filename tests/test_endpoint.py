import json

from src.newwords_api.config import ConfigError, Settings
from src.newwords_api.endpoint import handle_keyword_volume
from src.newwords_api.google_ads import GoogleAdsUpstreamError, UpstreamTimeout


def settings():
    return Settings(
        client_id="client",
        client_secret="secret",
        refresh_token="refresh",
        customer_id="1367654543",
        api_key="api-key",
        api_version="v24",
    )


class FakeClient:
    def __init__(self, result=None, error=None):
        self.result = result or {"results": []}
        self.error = error
        self.requests = []

    def generate_historical_metrics(self, request):
        self.requests.append(request)
        if self.error:
            raise self.error
        return self.result


def call(
    *,
    method="POST",
    auth="Bearer api-key",
    payload=None,
    client=None,
    settings_value=None,
    settings_loader=None,
):
    client = client or FakeClient()
    payload = payload if payload is not None else {"keywords": ["i ching online"]}
    return handle_keyword_volume(
        method,
        {"Authorization": auth} if auth is not None else {},
        json.dumps(payload).encode("utf-8"),
        settings=settings_value or settings(),
        settings_loader=settings_loader,
        client_factory=lambda _settings: client,
    )


def test_non_post_method_returns_405():
    status, headers, body = call(method="GET")
    assert status == 405
    assert body["error"]["code"] == "method_not_allowed"


def test_missing_or_wrong_bearer_token_returns_401():
    assert call(auth=None)[0] == 401
    assert call(auth="Bearer wrong")[0] == 401


def test_invalid_json_or_request_returns_400():
    status, _, body = handle_keyword_volume(
        "POST",
        {"Authorization": "Bearer api-key"},
        b"not-json",
        settings=settings(),
        client_factory=lambda _settings: FakeClient(),
    )
    assert status == 400
    assert body["error"]["code"] == "invalid_request"

    status, _, body = call(payload={"keywords": []})
    assert status == 400
    assert body["error"]["code"] == "invalid_request"


def test_missing_server_configuration_returns_500_without_secret_details():
    def broken_loader():
        raise ConfigError("missing required environment variable: GOOGLE_ADS_CLIENT_SECRET")

    status, _, body = handle_keyword_volume(
        "POST",
        {"Authorization": "Bearer api-key"},
        b'{"keywords":["i ching online"]}',
        settings=None,
        settings_loader=broken_loader,
        client_factory=lambda _settings: FakeClient(),
    )

    assert status == 500
    assert body == {
        "error": {
            "code": "server_configuration_error",
            "message": "server configuration is incomplete",
        }
    }


def test_upstream_error_and_timeout_map_to_502_and_504():
    error_client = FakeClient(error=GoogleAdsUpstreamError("Google Ads request failed", 400))
    timeout_client = FakeClient(error=UpstreamTimeout("timeout"))

    assert call(client=error_client)[0] == 502
    assert call(client=timeout_client)[0] == 504


def test_success_returns_normalized_agent_friendly_json():
    client = FakeClient(
        result={
            "results": [
                {
                    "text": "i ching online",
                    "keywordMetrics": {
                        "avgMonthlySearches": "22200",
                        "competition": "LOW",
                        "competitionIndex": "0",
                        "lowTopOfPageBidMicros": "13417500",
                        "highTopOfPageBidMicros": "130641729",
                        "monthlySearchVolumes": [
                            {
                                "year": "2026",
                                "month": "AUGUST",
                                "monthlySearches": "22200",
                            }
                        ],
                    },
                }
            ]
        }
    )

    status, headers, body = call(client=client)

    assert status == 200
    assert headers["Content-Type"] == "application/json; charset=utf-8"
    assert body["source"] == "google_ads"
    assert body["query"] == {
        "geo_target_constant": "2840",
        "language_constant": "1000",
        "network": "GOOGLE_SEARCH",
    }
    assert body["results"][0]["keyword"] == "i ching online"
    assert body["results"][0]["avg_monthly_searches"] == 22200
    assert body["results"][0]["competition_index"] == 0
