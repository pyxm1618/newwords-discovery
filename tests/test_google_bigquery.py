from datetime import date
from decimal import Decimal

import pytest

from api.lib._config import BigQuerySettings
from api.lib._google_bigquery import (
    BigQueryServiceError,
    GoogleTrendsBigQueryClient,
    _json_scalar,
)
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
    def __init__(self, rows=None):
        self.calls = []
        self.rows = rows if rows is not None else [
            {
                "term": "example term",
                "rank": 1,
                "percent_gain": 1250,
                "rank_value_count": 1,
                "percent_gain_value_count": 1,
                "week": "2021-09-19",
                "score": 0.0,
                "score_aggregation": "mean_across_available_regions",
                "region_count": 2,
            },
            {
                "term": "example term",
                "rank": 1,
                "percent_gain": 1250,
                "rank_value_count": 1,
                "percent_gain_value_count": 1,
                "week": "2021-09-26",
                "score": None,
                "score_aggregation": "mean_across_available_regions",
                "region_count": 0,
            },
            {
                "term": "example term",
                "rank": 1,
                "percent_gain": 1250,
                "rank_value_count": 1,
                "percent_gain_value_count": 1,
                "week": "2021-10-03",
                "score": 42.5,
                "score_aggregation": "mean_across_available_regions",
                "region_count": 2,
            },
            {
                "term": "second term",
                "rank": 2,
                "percent_gain": 800,
                "rank_value_count": 1,
                "percent_gain_value_count": 1,
                "week": "2021-09-19",
                "score": 10.0,
                "score_aggregation": "mean_across_available_regions",
                "region_count": 2,
            },
        ]

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
            "rows": self.rows,
            "usage": {
                "total_bytes_processed": 123456,
                "total_bytes_billed": 10_000_000,
                "cache_hit": False,
            },
        }


def test_client_groups_all_weekly_rows_without_dropping_zero_null_or_pullback_points():
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

    assert result["history"]["score_aggregation"] == "mean_across_available_regions"
    assert result["results"] == [
        {
            "term": "example term",
            "rank": 1,
            "percent_gain": 1250,
            "history": [
                {"week": "2021-09-19", "score": 0.0, "region_count": 2},
                {"week": "2021-09-26", "score": None, "region_count": 0},
                {"week": "2021-10-03", "score": 42.5, "region_count": 2},
            ],
        },
        {
            "term": "second term",
            "rank": 2,
            "percent_gain": 800,
            "history": [
                {"week": "2021-09-19", "score": 10.0, "region_count": 2},
            ],
        },
    ]
    assert result["usage"] == {
        "total_bytes_processed": 123456,
        "total_bytes_billed": 10_000_000,
        "cache_hit": False,
    }


def test_client_omits_country_parameter_for_us_top_and_returns_null_percent_gain():
    transport = FakeTransport(
        rows=[
            {
                "term": "top term",
                "rank": 1,
                "percent_gain": None,
                "rank_value_count": 1,
                "percent_gain_value_count": 0,
                "week": "2021-09-19",
                "score": 15.0,
                "score_aggregation": "mean_across_available_regions",
                "region_count": 210,
            },
            {
                "term": "top term",
                "rank": 1,
                "percent_gain": None,
                "rank_value_count": 1,
                "percent_gain_value_count": 0,
                "week": "2021-09-26",
                "score": 12.0,
                "score_aggregation": "mean_across_available_regions",
                "region_count": 210,
            },
        ]
    )
    client = GoogleTrendsBigQueryClient(settings(), transport=transport)
    request = TrendsRequest(
        kind="top",
        country_code="US",
        refresh_date="2026-09-18",
        limit=10,
    )

    result = client.fetch_terms(request)

    call = transport.calls[0]
    assert "bigquery-public-data.google_trends.top_terms" in call["sql"]
    assert "country_code = @country_code" not in call["sql"]
    assert call["parameters"] == {
        "refresh_date": ("DATE", "2026-09-18"),
    }
    assert result["results"][0]["percent_gain"] is None
    assert len(result["results"][0]["history"]) == 2


def test_client_orders_history_by_week_even_if_transport_rows_are_not_ordered():
    rows = [
        {
            "term": "term",
            "rank": 1,
            "percent_gain": 500,
            "rank_value_count": 1,
            "percent_gain_value_count": 1,
            "week": "2026-01-11",
            "score": 20.0,
            "score_aggregation": "official_country_row",
            "region_count": 1,
        },
        {
            "term": "term",
            "rank": 1,
            "percent_gain": 500,
            "rank_value_count": 1,
            "percent_gain_value_count": 1,
            "week": "2026-01-04",
            "score": 30.0,
            "score_aggregation": "official_country_row",
            "region_count": 1,
        },
    ]

    result = GoogleTrendsBigQueryClient(
        settings(), transport=FakeTransport(rows=rows)
    ).fetch_terms(
        TrendsRequest(
            kind="rising",
            country_code="US",
            refresh_date="2026-09-18",
            limit=1,
        )
    )

    assert result["history"]["score_aggregation"] == "official_country_row"
    assert [point["week"] for point in result["results"][0]["history"]] == [
        "2026-01-04",
        "2026-01-11",
    ]


def test_client_rejects_inconsistent_repeated_rank_or_percent_gain_values():
    inconsistent_rank = [
        {
            "term": "term",
            "rank": 1,
            "percent_gain": 500,
            "rank_value_count": 2,
            "percent_gain_value_count": 1,
            "week": "2026-01-04",
            "score": 30.0,
            "score_aggregation": "mean_across_available_regions",
            "region_count": 2,
        }
    ]
    client = GoogleTrendsBigQueryClient(
        settings(), transport=FakeTransport(rows=inconsistent_rank)
    )

    with pytest.raises(BigQueryServiceError):
        client.fetch_terms(
            TrendsRequest(
                kind="rising",
                country_code="US",
                refresh_date="2026-09-18",
                limit=1,
            )
        )


def test_transport_scalar_normalization_preserves_json_dates_numbers_and_nulls():
    assert _json_scalar(date(2026, 9, 18)) == "2026-09-18"
    assert _json_scalar(Decimal("12")) == 12
    assert _json_scalar(Decimal("12.5")) == 12.5
    assert _json_scalar(None) is None
