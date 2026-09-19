# newwords-discovery

Private API layer for AI-driven new-word and SEO discovery workflows.

This repository is deliberately an **API-layer service**, not a monolithic SEO application. Public Vercel routes live under `api/v1/`; private implementation lives under `api/lib/`. There is no separate `src/` application layer.

## Architecture contract

Current runtime layout:

```text
api/
├── v1/
│   ├── keyword-volume.py      # thin public Vercel adapter
│   └── trends.py              # thin public Vercel adapter
└── lib/
    ├── _auth.py               # shared Bearer authentication
    ├── _config.py             # shared env parsing; endpoint-specific settings
    ├── _http.py               # shared HTTP/JSON helpers
    │
    ├── _endpoint.py           # keyword-volume orchestration only (legacy name)
    ├── _keyword_volume.py     # keyword-volume validation/normalization
    ├── _google_ads.py         # Google Ads client + transport boundary
    │
    ├── _trends_endpoint.py    # Trends orchestration only
    ├── _trends.py             # Trends validation/query/table selection
    └── _google_bigquery.py    # BigQuery client + transport boundary
```

The architecture rules for every additional API are:

1. Add the public route as a sibling under `api/v1/`.
2. Keep `api/v1/<route>.py` thin: Vercel/HTTP adaptation only.
3. Give each API its own private orchestration module under `api/lib/`; do not add a new API to another API's endpoint module.
4. Share only genuinely cross-API infrastructure: authentication, configuration parsing, generic HTTP helpers, and other source-neutral utilities.
5. Keep request validation/query shaping separate from upstream service access.
6. Put every external service behind an injectable client/transport boundary so tests remain network-free.
7. Prefix private helper modules with `_` so Vercel does not expose them as standalone Functions.
8. Do not add a parallel `src/` application layer.
9. Do not treat `api/lib/_endpoint.py` as a global endpoint registry. Its name is historical; it belongs to Keyword Volume only.
10. Add or update architecture tests whenever a new API is introduced so cross-API coupling fails CI rather than becoming convention drift.

The current architecture is enforced by `tests/test_api_layout.py`.

## Public APIs

Canonical domain:

```text
https://newwords-discovery.vercel.app
```

Routes:

```text
POST /api/v1/keyword-volume
POST /api/v1/trends
```

Both use the same private Bearer key:

```http
Authorization: Bearer <API_KEY>
```

The canonical domain is the API contract.

## Production status

**Production-verified on 2026-09-19.**

Both public routes were authenticated-smoke-tested against the canonical production domain after the current `main` deployment reached Vercel `READY`:

- `POST /api/v1/trends` → HTTP `200`, `source=google_trends_bigquery`, with real Google Trends BigQuery rows and usage metadata.
- `POST /api/v1/keyword-volume` → HTTP `200`, `source=google_ads`, with real Google Ads historical metrics.
- The verified production code revision was `c2911ffbb52a6d28b2c31db7e57ec8ac1fad537c`.
- Trends acceptance request: `kind=rising`, `country_code=US`, `refresh_date=2026-09-18`, `limit=5`.
- That Trends request reported `44,779,770` bytes processed, `45,088,768` bytes billed, and `cache_hit=false`.

Future deployments still require a fresh authenticated smoke before a new revision is described as production-verified.

See `docs/API.md` for request/response contracts and the acceptance record, and `docs/AGENT_USAGE.md` for agent calling rules.

## Keyword Volume

`POST /api/v1/keyword-volume` returns Google Ads Keyword Historical Metrics.

Default scope:

- geo target: `2840` (United States)
- language: `1000` (English)
- network: `GOOGLE_SEARCH`

Server-side configuration:

```text
SEO_DATA_API_KEY
GOOGLE_ADS_CLIENT_ID
GOOGLE_ADS_CLIENT_SECRET
GOOGLE_ADS_REFRESH_TOKEN
GOOGLE_ADS_CUSTOMER_ID
```

Optional:

```text
GOOGLE_ADS_API_VERSION=v24
```

## Google Trends BigQuery

`POST /api/v1/trends` exposes Google Trends public BigQuery data for discovery workflows.

Supported capability:

- `kind=rising`: daily Top Rising terms
- `kind=top`: daily Top terms
- two-letter country code
- explicit `refresh_date`
- `limit` from 1–25
- BigQuery usage metadata:
  - `total_bytes_processed`
  - `total_bytes_billed`
  - `cache_hit`

This is a daily candidate-discovery API. It is **not** an arbitrary-keyword Google Trends time-series API.

Server-side configuration:

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

`BIGQUERY_MAX_BYTES_BILLED` is a hard per-query billing guard. The default is 1,000,000,000 bytes.

## Secret model

Calling agents receive only the service URL and shared API key. They do not receive Google Ads OAuth credentials or the BigQuery service-account JSON.

Recommended caller variable:

```text
NEWWORDS_DISCOVERY_API_KEY
```

Its value must equal Vercel's `SEO_DATA_API_KEY`.

Never commit credentials, API keys, OAuth tokens, or service-account JSON.

For the BigQuery service account:

- keep the complete service-account JSON only in the server-side Vercel secret `GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON`;
- after a successful production smoke, the downloaded local JSON file should be deleted;
- do not delete the corresponding Google Cloud service-account key while Vercel still uses that credential;
- the runtime identity needs permission to create BigQuery jobs in the query project (currently satisfied with `BigQuery Job User`);
- if service-account key creation was temporarily enabled by overriding an organization policy, restore the inherited restriction after the required key has been created. Restoring the creation restriction does not revoke an already-created key.

## Design documents

- `docs/superpowers/specs/2026-09-17-keyword-volume-api-design.md`: Keyword Volume design, updated to the final repository layout.
- `docs/superpowers/plans/2026-09-17-keyword-volume-api.md`: completed implementation record; not a template for new APIs.
- `docs/superpowers/specs/2026-09-19-google-trends-bigquery-api-design.md`: Trends/BigQuery design and acceptance boundary.

## Development

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m pytest -q
python3 -m compileall -q api
python3 -m json.tool vercel.json >/dev/null
```

Tests must not require real Google credentials or network access.
