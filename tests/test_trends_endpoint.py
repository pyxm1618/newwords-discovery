import json

from api.lib._config import BigQuerySettings, ConfigError
from api.lib._google_bigquery import BigQueryServiceError, BigQueryTimeout
from api.lib._trends_endpoint import handle_trends


def settings():
    return BigQuerySettings(
        project_id="kinetic-genre-508803-t8",
        service_account_info={
            "type": "service_account",
            "project_id": "kinetic-genre-508803-t8",
            "client_email": "test@example.iam.gserviceaccount.com",
            "private_key": "not-a-real-key",
            "token_uri": "https://oauth2.googleapis.com/token",
        },
        api_key="api-key",
        location="US",
        maximum_bytes_billed=1_000_000_000,
    )


class FakeClient:
    def __init__(self, result=None, error=None):
        self.result = result or {
            "results": [],
            "usage": {
                "total_bytes_processed": 0,
                "total_bytes_billed": 0,
                "cache_hit": False,
            },
        }
        self.error = error
        self.requests = []

    def fetch_terms(self, request):
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
    payload = payload if payload is not None else {
        "kind": "rising",
        "country_code": "GB",
        "refresh_date": "2026-09-18",
    }
    return handle_trends(
        method,
        {"Authorization": auth} if auth is not None else {},
        json.dumps(payload).encode("utf-8"),
        settings=settings_value or settings(),
        settings_loader=settings_loader,
        client_factory=lambda _settings: client,
    )


def test_non_post_and_bad_auth_are_rejected():
    assert call(method="GET")[0] == 405
    assert call(auth=None)[0] == 401
    assert call(auth="Bearer wrong")[0] == 401


def test_invalid_request_returns_400():
    status, _, body = call(payload={"country_code": "GBR"})
    assert status == 400
    assert body["error"]["code"] == "invalid_request"


def test_missing_server_configuration_returns_500_without_secret_details():
    def broken_loader():
        raise ConfigError("bad secret")

    status, _, body = handle_trends(
        "POST",
        {"Authorization": "Bearer api-key"},
        b'{"country_code":"GB"}',
        settings=None,
        settings_loader=broken_loader,
        client_factory=lambda _settings: FakeClient(),
    )

    assert status == 500
    assert body["error"]["code"] == "server_configuration_error"
    assert "secret" not in body["error"]["message"]


def test_upstream_error_and_timeout_map_to_502_and_504():
    assert call(client=FakeClient(error=BigQueryServiceError("failed")))[0] == 502
    assert call(client=FakeClient(error=BigQueryTimeout("timeout")))[0] == 504


def test_success_returns_terms_and_usage_metrics():
    client = FakeClient(
        result={
            "results": [
                {"term": "example rising term", "rank": 1},
                {"term": "another term", "rank": 2},
            ],
            "usage": {
                "total_bytes_processed": 123456,
                "total_bytes_billed": 10_000_000,
                "cache_hit": False,
            },
        }
    )

    status, headers, body = call(client=client)

    assert status == 200
    assert headers["Content-Type"] == "application/json; charset=utf-8"
    assert body["source"] == "google_trends_bigquery"
    assert body["query"] == {
        "kind": "rising",
        "country_code": "GB",
        "refresh_date": "2026-09-18",
        "limit": 25,
    }
    assert body["results"][0] == {"term": "example rising term", "rank": 1}
    assert body["usage"]["total_bytes_processed"] == 123456
    assert body["usage"]["total_bytes_billed"] == 10_000_000
