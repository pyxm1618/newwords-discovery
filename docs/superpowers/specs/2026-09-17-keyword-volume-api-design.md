# Keyword Volume API Design

## Goal

Build `newwords-discovery` as a dedicated API-layer service for AI agents. The first production capability is a private HTTP API that returns Google Ads Keyword Historical Metrics for one or many keywords. Agents must not need Google OAuth details.

## Scope

Version 1 exposes one endpoint:

- `POST /api/v1/keyword-volume`

The endpoint accepts one or more keywords, defaults to the verified Google Ads scope (United States, English, Google Search), exchanges the stored refresh token for an access token, calls Google Ads `generateKeywordHistoricalMetrics`, and returns normalized JSON.

Out of scope for v1: keyword discovery logic, Google Trends, Semrush, Similarweb/domain traffic, databases, user accounts, UI, and custom rate-limit infrastructure. Future data-source APIs are added as sibling endpoints under `api/v1/`.

## Architecture

This repository is the API layer. All runtime code lives under the top-level `api/` directory; there is no separate `src/` application layer.

```text
newwords-discovery/
├── api/
│   ├── __init__.py
│   ├── v1/
│   │   └── keyword-volume.py
│   └── lib/
│       ├── __init__.py
│       ├── _auth.py
│       ├── _config.py
│       ├── _endpoint.py
│       ├── _google_ads.py
│       └── _keyword_volume.py
├── tests/
├── docs/
├── requirements.txt
├── pytest.ini
├── vercel.json
├── .gitignore
└── README.md
```

`api/v1/` contains public Vercel HTTP entrypoints. `api/lib/` contains private shared implementation. Helper module filenames begin with `_` so Vercel does not turn utility modules into standalone Functions. This keeps the public routing layer obvious while allowing many future APIs to share auth, configuration, transports, and normalization code.

## API contract

### Authentication

Every request must include:

```http
Authorization: Bearer <SEO_DATA_API_KEY>
```

The server compares the supplied token with `SEO_DATA_API_KEY` using constant-time comparison. Missing or invalid credentials return `401` and never expose stored secrets.

### Request

```json
{
  "keywords": ["i ching online", "i ching reading"],
  "geo_target_constant": "2840",
  "language_constant": "1000",
  "network": "GOOGLE_SEARCH"
}
```

Defaults when omitted:

- `geo_target_constant`: `2840` (United States)
- `language_constant`: `1000` (English)
- `network`: `GOOGLE_SEARCH`

`keywords` is required, must be a JSON array of non-empty strings, duplicates are de-duplicated while preserving order, and at most 10,000 keywords are accepted.

### Response

```json
{
  "source": "google_ads",
  "query": {
    "geo_target_constant": "2840",
    "language_constant": "1000",
    "network": "GOOGLE_SEARCH"
  },
  "results": [
    {
      "keyword": "i ching online",
      "avg_monthly_searches": 22200,
      "competition": "LOW",
      "competition_index": 0,
      "low_top_of_page_bid_micros": 13417500,
      "high_top_of_page_bid_micros": 130641729,
      "monthly_search_volumes": [
        {"year": 2026, "month": "AUGUST", "monthly_searches": 22200}
      ]
    }
  ]
}
```

Google missing values are returned as JSON `null`, never silently converted to `0`.

## Google Ads integration

The service uses the REST flow already verified manually:

1. `POST https://oauth2.googleapis.com/token` with client ID, client secret, refresh token, and `grant_type=refresh_token`.
2. Use the returned access token to call `POST https://googleads.googleapis.com/{version}/customers/{customer_id}:generateKeywordHistoricalMetrics`.
3. Send `keywords`, `geoTargetConstants`, `language`, and `keywordPlanNetwork`.

Default API version is `v24`, because that exact version and request shape were manually verified successfully on 2026-09-17. `GOOGLE_ADS_API_VERSION` may override it without a code change.

The service does not log OAuth tokens or secrets. Upstream errors are translated into structured API errors; raw Google response bodies are not returned when they may contain sensitive implementation details.

## Environment variables

Required on Vercel:

- `GOOGLE_ADS_CLIENT_ID`
- `GOOGLE_ADS_CLIENT_SECRET`
- `GOOGLE_ADS_REFRESH_TOKEN`
- `GOOGLE_ADS_CUSTOMER_ID`
- `SEO_DATA_API_KEY`

Optional:

- `GOOGLE_ADS_API_VERSION` (default `v24`)

No credential value is committed to GitHub. `.env*` files are ignored.

## Error handling

- `400`: malformed JSON, missing/invalid keywords, invalid network, keyword count > 10,000
- `401`: missing/invalid Bearer token
- `405`: non-POST request
- `500`: required server configuration missing
- `502`: Google OAuth or Google Ads upstream failure
- `504`: upstream timeout

Errors use a stable JSON shape:

```json
{
  "error": {
    "code": "invalid_request",
    "message": "keywords must be a non-empty array of strings"
  }
}
```

## Testing

Tests are network-free. OAuth and Google Ads HTTP calls are replaced with fakes at the transport boundary. Tests cover authentication, request validation, default scope, de-duplication, result normalization, upstream failures, secret-safe errors, Vercel adapter loading, and the API-only repository layout.

## Deployment

Vercel deploys public Python Functions under `api/v1/`. Production secrets are configured only in Vercel Environment Variables. AI agents receive only the service URL and `SEO_DATA_API_KEY`; they do not receive Google OAuth credentials.
