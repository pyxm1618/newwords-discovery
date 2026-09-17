import pytest

from api.lib._config import Settings
from api.lib._google_ads import (
    GoogleAdsClient,
    GoogleAdsUpstreamError,
    GoogleOAuthError,
    UpstreamTimeout,
)
from api.lib._keyword_volume import KeywordVolumeRequest


class FakeTransport:
    def __init__(self, responses=None, timeout_on=None):
        self.responses = list(responses or [])
        self.timeout_on = timeout_on
        self.calls = []

    def post_form(self, url, *, data, headers=None, timeout=15):
        self.calls.append(("form", url, data, headers or {}, timeout))
        if self.timeout_on == "form":
            raise UpstreamTimeout("timeout")
        return self.responses.pop(0)

    def post_json(self, url, *, json_body, headers=None, timeout=30):
        self.calls.append(("json", url, json_body, headers or {}, timeout))
        if self.timeout_on == "json":
            raise UpstreamTimeout("timeout")
        return self.responses.pop(0)


def settings():
    return Settings(
        client_id="client-id",
        client_secret="client-secret",
        refresh_token="refresh-token",
        customer_id="1367654543",
        api_key="private-api-key",
        api_version="v24",
    )


def request():
    return KeywordVolumeRequest(
        keywords=("i ching online", "i ching reading"),
        geo_target_constant="2840",
        language_constant="1000",
        network="GOOGLE_SEARCH",
    )


def test_client_exchanges_refresh_token_and_calls_google_ads_with_verified_request_shape():
    transport = FakeTransport(
        responses=[
            (200, {"access_token": "access-token"}),
            (200, {"results": [{"text": "i ching online"}]}),
        ]
    )
    client = GoogleAdsClient(settings(), transport=transport)

    result = client.generate_historical_metrics(request())

    assert result == {"results": [{"text": "i ching online"}]}
    assert transport.calls[0][0:2] == ("form", "https://oauth2.googleapis.com/token")
    assert transport.calls[0][2] == {
        "client_id": "client-id",
        "client_secret": "client-secret",
        "refresh_token": "refresh-token",
        "grant_type": "refresh_token",
    }
    assert transport.calls[1][1] == (
        "https://googleads.googleapis.com/v24/customers/"
        "1367654543:generateKeywordHistoricalMetrics"
    )
    assert transport.calls[1][2] == {
        "keywords": ["i ching online", "i ching reading"],
        "geoTargetConstants": ["geoTargetConstants/2840"],
        "language": "languageConstants/1000",
        "keywordPlanNetwork": "GOOGLE_SEARCH",
    }
    assert transport.calls[1][3]["Authorization"] == "Bearer access-token"


def test_oauth_failure_is_sanitized():
    transport = FakeTransport(
        responses=[(400, {"error": "invalid_grant", "secret": "do-not-leak"})]
    )
    client = GoogleAdsClient(settings(), transport=transport)

    with pytest.raises(GoogleOAuthError) as exc:
        client.generate_historical_metrics(request())

    assert "do-not-leak" not in str(exc.value)
    assert exc.value.upstream_status == 400


def test_google_ads_failure_is_sanitized():
    transport = FakeTransport(
        responses=[
            (200, {"access_token": "access-token"}),
            (400, {"error": {"message": "raw upstream details", "token": "do-not-leak"}}),
        ]
    )
    client = GoogleAdsClient(settings(), transport=transport)

    with pytest.raises(GoogleAdsUpstreamError) as exc:
        client.generate_historical_metrics(request())

    assert "do-not-leak" not in str(exc.value)
    assert "raw upstream details" not in str(exc.value)
    assert exc.value.upstream_status == 400


def test_transport_timeout_is_propagated_as_timeout():
    client = GoogleAdsClient(settings(), transport=FakeTransport(timeout_on="form"))

    with pytest.raises(UpstreamTimeout):
        client.generate_historical_metrics(request())
