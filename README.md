# newwords-discovery

Private API layer for AI-driven new-word and SEO discovery workflows.

The repository is API-first. Public Vercel routes live under `api/v1/`; private implementation stays under `api/lib/`.

## Architecture

```text
api/
├── v1/
│   ├── keyword-volume.py      # thin public Vercel adapter
│   └── trends.py              # thin public Vercel adapter
└── lib/
    ├── _auth.py               # shared authentication
    ├── _config.py             # shared environment/config parsing
    ├── _http.py               # shared HTTP response/header/body helpers
    │
    ├── _endpoint.py           # keyword-volume orchestration (legacy v1 name)
    ├── _keyword_volume.py     # keyword-volume validation/normalization
    ├── _google_ads.py         # Google Ads upstream transport/client
    │
    ├── _trends_endpoint.py    # Trends API orchestration
    ├── _trends.py             # Trends validation/query/table selection
    └── _google_bigquery.py    # BigQuery upstream transport/client
```

Architecture rules for additional APIs:

1. Add each public API as a sibling route under `api/v1/`.
2. Keep the public route thin: HTTP/Vercel adaptation only.
3. Keep endpoint-specific orchestration in its own private module; do not add a new API's orchestration to an existing API's endpoint module.
4. Share only genuinely cross-API infrastructure such as authentication, configuration parsing, and generic HTTP helpers.
5. Keep request validation/query shaping separate from upstream data-source access.
6. Put external service access behind an injectable transport/client boundary so automated tests remain network-free.
7. Private helper filenames under `api/lib/` start with `_` so Vercel does not expose them as standalone Functions.
8. Do not introduce a separate `src/` application layer.

The original Keyword Volume design is documented in
[`docs/superpowers/specs/2026-09-17-keyword-volume-api-design.md`](docs/superpowers/specs/2026-09-17-keyword-volume-api-design.md).
The Trends architecture is documented in
[`docs/superpowers/specs/2026-09-19-google-trends-bigquery-api-design.md`](docs/superpowers/specs/2026-09-19-google-trends-bigquery-api-design.md).

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

Automated tests use fakes at external-service boundaries and do not require real Google credentials.
