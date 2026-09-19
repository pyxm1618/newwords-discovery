import pytest

from api.lib._trends import (
    TrendsRequestValidationError,
    build_trends_query,
    trends_table_name,
    validate_trends_request,
)


def test_trends_request_normalizes_inputs():
    request = validate_trends_request(
        {
            "kind": " Rising ",
            "country_code": "gb",
            "refresh_date": "2026-09-18",
            "limit": 10,
        }
    )

    assert request.kind == "rising"
    assert request.country_code == "GB"
    assert request.refresh_date == "2026-09-18"
    assert request.limit == 10


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"kind": "unknown"},
        {"country_code": "USA"},
        {"refresh_date": "18-09-2026"},
        {"limit": 0},
        {"limit": 26},
        {"limit": "25"},
    ],
)
def test_trends_request_rejects_invalid_inputs(payload):
    with pytest.raises(TrendsRequestValidationError):
        validate_trends_request(payload)


@pytest.mark.parametrize(
    ("kind", "country_code", "expected_table"),
    [
        ("top", "US", "bigquery-public-data.google_trends.top_terms"),
        ("rising", "US", "bigquery-public-data.google_trends.top_rising_terms"),
        ("top", "GB", "bigquery-public-data.google_trends.international_top_terms"),
        (
            "rising",
            "GB",
            "bigquery-public-data.google_trends.international_top_rising_terms",
        ),
    ],
)
def test_all_trends_modes_route_to_the_expected_public_table(
    kind, country_code, expected_table
):
    request = validate_trends_request(
        {
            "kind": kind,
            "country_code": country_code,
            "refresh_date": "2026-09-18",
            "limit": 5,
        }
    )

    assert trends_table_name(request) == expected_table


def test_us_rising_query_keeps_one_partition_and_limits_terms_not_history_rows():
    request = validate_trends_request(
        {
            "kind": "rising",
            "country_code": "US",
            "refresh_date": "2026-09-18",
            "limit": 5,
        }
    )

    sql = build_trends_query(request)

    assert "bigquery-public-data.google_trends.top_rising_terms" in sql
    assert "WHERE refresh_date = @refresh_date" in sql
    assert "country_code = @country_code" not in sql
    assert "dma_id AS region_key" in sql
    assert "percent_gain AS percent_gain" in sql
    assert "candidate_terms AS" in sql
    assert "weekly_history AS" in sql
    assert "GROUP BY base.term, base.week" in sql
    assert sql.count("LIMIT 5") == 1
    assert "ORDER BY candidate.rank ASC, candidate.term ASC, history.week ASC" in sql


def test_international_top_query_keeps_country_filter_and_does_not_require_percent_gain():
    request = validate_trends_request(
        {
            "kind": "top",
            "country_code": "GB",
            "refresh_date": "2026-09-18",
            "limit": 3,
        }
    )

    sql = build_trends_query(request)

    assert "bigquery-public-data.google_trends.international_top_terms" in sql
    assert "WHERE refresh_date = @refresh_date" in sql
    assert "AND country_code = @country_code" in sql
    assert "region_code AS region_key" in sql
    assert "CAST(NULL AS INT64) AS percent_gain" in sql
    assert sql.count("LIMIT 3") == 1


def test_query_preserves_null_and_zero_scores_and_aggregates_only_at_term_week_grain():
    request = validate_trends_request(
        {
            "kind": "rising",
            "country_code": "GB",
            "refresh_date": "2026-09-18",
            "limit": 2,
        }
    )

    sql = build_trends_query(request)

    assert "AVG(base.score)" in sql
    assert "COUNT(base.score)" in sql
    assert "COALESCE(base.score, 0)" not in sql
    assert "base.score != 0" not in sql
    assert "base.score > 0" not in sql
    assert "GROUP BY base.term, base.week" in sql
