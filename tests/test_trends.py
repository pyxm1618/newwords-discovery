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


def test_us_and_international_requests_route_to_correct_public_tables():
    us = validate_trends_request(
        {"kind": "top", "country_code": "US", "refresh_date": "2026-09-18"}
    )
    gb = validate_trends_request(
        {"kind": "rising", "country_code": "GB", "refresh_date": "2026-09-18"}
    )

    assert trends_table_name(us).endswith(".top_terms")
    assert trends_table_name(gb).endswith(".international_top_rising_terms")

    us_sql = build_trends_query(us)
    gb_sql = build_trends_query(gb)

    assert "country_code = @country_code" not in us_sql
    assert "country_code = @country_code" in gb_sql
    assert "LIMIT 25" in us_sql
