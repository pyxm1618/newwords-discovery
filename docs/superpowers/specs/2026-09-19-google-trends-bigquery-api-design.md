# Google Trends BigQuery API Design

## Status

**Implemented and production-verified on 2026-09-19.**

The current production acceptance was performed against Vercel after the `main` deployment reached `READY`. An authenticated request reached the real BigQuery upstream and returned HTTP `200`, real Google Trends rows, and usage metadata.

Verified production revision: `c2911ffbb52a6d28b2c31db7e57ec8ac1fad537c`.

Acceptance snapshot:

```text
kind=rising
country_code=US
refresh_date=2026-09-18
limit=5
HTTP 200
source=google_trends_bigquery
total_bytes_processed=44779770
total_bytes_billed=45088768
cache_hit=false
results_count=5
```

Repository implementation/build success and production data-path verification remain separate states. Any future deployment or credential/permission change requires a fresh authenticated smoke before that new state is called production-verified.

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

The service account must be able to create BigQuery query jobs in the selected query project. The verified production configuration uses the `BigQuery Job User` role.

The service-account JSON is stored only in Vercel as `GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON`. A downloaded local JSON file is not a required runtime artifact and should be deleted after production verification. The Google Cloud key represented by that JSON must remain active while Vercel uses it.

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

Acceptance criteria:

- [x] current `main` deployment reached READY in Vercel;
- [x] required BigQuery environment variables are present server-side;
- [x] real authenticated `POST /api/v1/trends` returned HTTP `200` and actual Google Trends rows;
- [x] response included `usage.total_bytes_processed`, `usage.total_bytes_billed`, and `usage.cache_hit`;
- [x] existing `/api/v1/keyword-volume` remained functional and returned HTTP `200`.

**Acceptance completed: 2026-09-19.**

The verified Trends call processed `44,779,770` bytes and billed `45,088,768` bytes with `cache_hit=false`. The simultaneous Keyword Volume regression call returned live Google Ads data. This closes the original production-verification gap for the current revision.
