# Google Trends BigQuery API Design

## Goal

Add Google Trends public BigQuery data as the second production data-source API without changing the repository's API-layer architecture.

The API is a discovery source for daily Top and Rising terms. It does not emulate the arbitrary-keyword Google Trends web interface.

## Architecture rule

The repository remains a dedicated API layer.

- `api/v1/`: public Vercel HTTP entrypoints only.
- `api/lib/`: private implementation modules only.
- Each public API owns its endpoint orchestration; endpoint-specific orchestration must not be added to another API's endpoint module.
- True cross-API infrastructure may be shared: authentication, configuration parsing, HTTP response/header helpers.
- Data-source access stays isolated behind a transport/client boundary so tests do not require network access or credentials.
- Request validation/query shaping stays in the capability module, separate from the upstream transport.

For this API:

```text
api/v1/trends.py
        │
        ▼
api/lib/_trends_endpoint.py
        │
        ├── api/lib/_trends.py
        │      request validation + table/query selection
        │
        ├── api/lib/_google_bigquery.py
        │      BigQuery client + injectable transport boundary
        │
        ├── api/lib/_auth.py
        ├── api/lib/_config.py
        └── api/lib/_http.py
```

The first API keeps its existing `api/lib/_endpoint.py` module to avoid an unrelated rename; it remains keyword-volume-only.

## Public route

`POST /api/v1/trends`

Request fields:

- `kind`: `rising` or `top`, default `rising`
- `country_code`: two-letter ISO country code, default `US`
- `refresh_date`: `YYYY-MM-DD`, default UTC yesterday
- `limit`: 1–25, default 25

## Data-source routing

Fixed server-side table mapping:

- US top: `bigquery-public-data.google_trends.top_terms`
- US rising: `bigquery-public-data.google_trends.top_rising_terms`
- international top: `bigquery-public-data.google_trends.international_top_terms`
- international rising: `bigquery-public-data.google_trends.international_top_rising_terms`

User input never becomes a table identifier.

`refresh_date` and international `country_code` are query parameters.

## BigQuery transport boundary

`GoogleTrendsBigQueryClient` owns capability-level BigQuery behavior and receives an injectable transport.

Production uses a Google Cloud BigQuery transport. Tests inject a fake transport and assert SQL, parameters, billing cap, and normalized results without credentials or network calls.

## Shared infrastructure

Shared modules must remain data-source-neutral:

- `_auth.py`: Bearer authentication
- `_config.py`: environment parsing into endpoint-specific settings objects
- `_http.py`: generic JSON response/header/body helpers

They must not contain Trends SQL, Google Ads request logic, or endpoint-specific response contracts.

## Billing safety

Every BigQuery query sets `maximum_bytes_billed` from `BIGQUERY_MAX_BYTES_BILLED`.

Successful responses expose:

- `total_bytes_processed`
- `total_bytes_billed`
- `cache_hit`

## Testing

Tests are network-free and cover:

- request validation and table routing
- endpoint HTTP behavior
- BigQuery transport request shape
- environment configuration
- Vercel adapter loading
- architecture/layout boundaries
