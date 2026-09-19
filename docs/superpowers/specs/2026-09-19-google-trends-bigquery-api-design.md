# Google Trends BigQuery API Design

## Status

Implemented in the repository.

Repository implementation/build success and production data-path verification are separate states. A production GO for this route requires a READY Vercel deployment plus a real authenticated BigQuery smoke request with valid server-side credentials.

## Goal

Add Google Trends public BigQuery data as the second production data-source API without breaking the repository's API-layer architecture.

The API is a discovery source for daily Top and Rising terms. It does not emulate the arbitrary-keyword Google Trends web interface.

## Architecture

```text
api/v1/trends.py
        │
        ▼
api/lib/_trends_endpoint.py
        │
        ├── api/lib/_trends.py
        │      request validation + fixed table/query selection
        │
        ├── api/lib/_google_bigquery.py
        │      capability client
        │      + injectable BigQueryTransport
        │      + GoogleCloudBigQueryTransport
        │
        ├── api/lib/_auth.py
        ├── api/lib/_config.py
        └── api/lib/_http.py
```

Rules:

- `api/v1/trends.py` contains only Vercel/HTTP adaptation.
- Trends endpoint orchestration stays in `_trends_endpoint.py`.
- `_trends.py` owns request validation and query/table selection.
- `_google_bigquery.py` owns BigQuery access and result normalization at the transport boundary.
- shared modules remain data-source-neutral.
- Trends logic must not be added to Keyword Volume's `_endpoint.py`.
- tests must remain network-free.

These boundaries are enforced by `tests/test_api_layout.py`.

## Public route

```text
POST /api/v1/trends
```

Request fields:

- `kind`: `rising` or `top`; default `rising`
- `country_code`: two-letter ISO code; default `US`
- `refresh_date`: `YYYY-MM-DD`; default UTC yesterday
- `limit`: integer 1–25; default 25

## Fixed BigQuery routing

Server-side mapping:

- US top: `bigquery-public-data.google_trends.top_terms`
- US rising: `bigquery-public-data.google_trends.top_rising_terms`
- international top: `bigquery-public-data.google_trends.international_top_terms`
- international rising: `bigquery-public-data.google_trends.international_top_rising_terms`

User input never becomes a table identifier.

Parameters:

- `refresh_date`: BigQuery `DATE`
- non-US `country_code`: BigQuery `STRING`

## BigQuery transport boundary

`GoogleTrendsBigQueryClient` receives a `BigQueryTransport`.

Production implementation:

```text
GoogleTrendsBigQueryClient
        ↓
GoogleCloudBigQueryTransport
        ↓
google-cloud-bigquery
```

Tests inject a fake transport and assert:

- selected SQL/table
- query parameters
- `maximum_bytes_billed`
- timeout
- normalized rows
- usage metadata

No real GCP credentials or network calls are required by tests.

## Configuration

Required:

```text
SEO_DATA_API_KEY
GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON
```

Optional:

```text
GOOGLE_CLOUD_PROJECT
BIGQUERY_LOCATION=US
BIGQUERY_MAX_BYTES_BILLED=1000000000
```

If `GOOGLE_CLOUD_PROJECT` is absent, the service-account JSON's `project_id` is used.

The service account must be able to create BigQuery query jobs in the selected query project.

## Billing safety

Every production query sets `maximum_bytes_billed` from `BIGQUERY_MAX_BYTES_BILLED`.

Successful responses expose:

- `total_bytes_processed`
- `total_bytes_billed`
- `cache_hit`

Callers should persist these fields for cost/scan auditing.

## Error mapping

- `400`: invalid request
- `401`: invalid/missing API Bearer token
- `405`: non-POST
- `500`: server configuration incomplete
- `502`: BigQuery/Google upstream failure
- `504`: timeout

## Automated acceptance

CI must pass:

```bash
python -m pytest -q
python -m compileall -q api
python -m json.tool vercel.json >/dev/null
```

Coverage includes:

- validation/table routing
- endpoint HTTP behavior
- BigQuery transport request shape
- configuration parsing
- Vercel adapter loading
- architecture boundaries

## Production acceptance

Do not declare the Trends route fully production-verified from CI or a successful Vercel build alone.

Production acceptance requires all of the following:

1. current `main` deployment is READY in Vercel;
2. required BigQuery environment variables are present server-side;
3. a real authenticated `POST /api/v1/trends` returns actual Google Trends rows;
4. response includes `usage.total_bytes_processed`, `usage.total_bytes_billed`, and `usage.cache_hit`;
5. existing `/api/v1/keyword-volume` remains functional after deployment.

Until those checks pass, describe the route as **implemented and CI-validated**, not as fully production-verified.
