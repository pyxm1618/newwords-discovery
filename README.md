# newwords-discovery

Private API layer for AI-driven new-word and SEO discovery workflows.

The repository is API-first. Public Vercel endpoints and their shared runtime implementation live under `api/`, so multiple SEO data sources can share one authentication layer without mixing credentials or business logic.

## Repository layout

```text
api/
├── v1/
│   ├── keyword-volume.py      # Google Ads historical search volume
│   └── trends.py              # Google Trends public dataset via BigQuery
└── lib/
    ├── _auth.py
    ├── _config.py
    ├── _endpoint.py
    ├── _google_ads.py
    ├── _google_bigquery.py
    ├── _keyword_volume.py
    └── _trends.py
```

## Production APIs

Canonical production domain:

```text
https://newwords-discovery.vercel.app
```

Endpoints:

```text
POST /api/v1/keyword-volume
POST /api/v1/trends
```

Both endpoints use the same private Bearer key:

```http
Authorization: Bearer <API_KEY>
```

See [`docs/API.md`](docs/API.md) for the full contracts and [`docs/AGENT_USAGE.md`](docs/AGENT_USAGE.md) for AI/Agent calling rules.

## Keyword Volume

`POST /api/v1/keyword-volume` returns Google Ads Keyword Historical Metrics.

Default scope:

- geo target: `2840` (United States)
- language: `1000` (English)
- network: `GOOGLE_SEARCH`

## Google Trends BigQuery

`POST /api/v1/trends` exposes Google's public Google Trends BigQuery dataset as a stable private API for discovery workflows.

It supports:

- `kind=rising`: daily Top Rising search terms
- `kind=top`: daily Top search terms
- ISO two-letter country selection
- explicit `refresh_date`
- up to 25 terms, matching the public dataset's daily Top 25 model
- BigQuery usage metadata in every successful response:
  - `total_bytes_processed`
  - `total_bytes_billed`
  - `cache_hit`

This endpoint is for discovering current candidate terms. It is not an arbitrary-keyword Google Trends time-series API.

The public dataset uses separate US and international tables; the service routes `country_code=US` to the US tables and other country codes to the international tables.

## Secret model

Shared API authentication:

```text
SEO_DATA_API_KEY
```

Google Ads endpoint:

```text
GOOGLE_ADS_CLIENT_ID
GOOGLE_ADS_CLIENT_SECRET
GOOGLE_ADS_REFRESH_TOKEN
GOOGLE_ADS_CUSTOMER_ID
```

Optional:

```text
GOOGLE_ADS_API_VERSION=v24
```

BigQuery Trends endpoint:

```text
GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON
```

Optional BigQuery settings:

```text
GOOGLE_CLOUD_PROJECT=<query project id>
BIGQUERY_LOCATION=US
BIGQUERY_MAX_BYTES_BILLED=1000000000
```

If `GOOGLE_CLOUD_PROJECT` is omitted, the service-account JSON's `project_id` is used.

`BIGQUERY_MAX_BYTES_BILLED` is a hard per-query billing guard. The default is 1,000,000,000 bytes.

The service account must be able to create BigQuery query jobs in the query project. Do not commit the service-account JSON or any API key to GitHub.

Calling Agents should store the shared API key once in their own secure runtime as:

```text
NEWWORDS_DISCOVERY_API_KEY
```

The value must equal Vercel's `SEO_DATA_API_KEY`.

## Deploy

1. Import this GitHub repository into Vercel.
2. Keep the repository root as the Vercel project root.
3. Add only the environment variables required by the endpoint(s) you want enabled.
4. Deploy.
5. Call the canonical production endpoint with `Authorization: Bearer <caller secret>`.

The Google Ads endpoint does not require BigQuery credentials. The Trends endpoint does not require Google Ads credentials.

## Development

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m pytest
python3 -m compileall api
```

Automated tests use fakes at the external-service boundary and do not require real Google credentials.
