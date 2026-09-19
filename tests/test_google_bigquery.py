from api.lib._config import BigQuerySettings
from api.lib._google_bigquery import GoogleTrendsBigQueryClient
from api.lib._trends import TrendsRequest


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


class FakeTransport:
    def __init__(self):
        self.calls = []

    def query(self, sql, *, parameters, maximum_bytes_billed, timeout):
        self.calls.append(
            {
                "sql": sql,
                "parameters": parameters,
                "maximum_bytes_billed": maximum_bytes_billed,
                "timeout": timeout,
            }
        )
        return {
            "rows": [
                {"term": "example term", "rank": 1},
                {"term": "second term", "rank": "2"},
            ],
            "usage": {
                "total_bytes_processed": 123456,
                "total_bytes_billed": 10_000_000,
                "cache_hit": False,
            },
        }


def test_client_routes_international_request_through_transport_with_parameterized_query():
    transport = FakeTransport()
    client = GoogleTrendsBigQueryClient(settings(), transport=transport)
    request = TrendsRequest(
        kind="rising",
        country_code="GB",
        refresh_date="2026-09-18",
        limit=25,
    )

    result = client.fetch_terms(request)

    call = transport.calls[0]
    assert "international_top_rising_terms" in call["sql"]
    assert "country_code = @country_code" in call["sql"]
    assert call["parameters"] == {
        "refresh_date": ("DATE", "2026-09-18"),
        "country_code": ("STRING", "GB"),
    }
    assert call["maximum_bytes_billed"] == 1_000_000_000
    assert call["timeout"] == 25
    assert result["results"] == [
        {"term": "example term", "rank": 1},
        {"term": "second term", "rank": 2},
    ]


def test_client_omits_country_parameter_for_us_table():
    transport = FakeTransport()
    client = GoogleTrendsBigQueryClient(settings(), transport=transport)
    request = TrendsRequest(
        kind="top",
        country_code="US",
        refresh_date="2026-09-18",
        limit=10,
    )

    client.fetch_terms(request)

    call = transport.calls[0]
    assert "bigquery-public-data.google_trends.top_terms" in call["sql"]
    assert "country_code = @country_code" not in call["sql"]
    assert call["parameters"] == {
        "refresh_date": ("DATE", "2026-09-18"),
    }
