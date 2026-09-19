# Keyword Volume API Design

## Status

**Implemented and production-verified on 2026-09-19.**

A real authenticated production regression smoke returned HTTP `200` from `POST /api/v1/keyword-volume` with `source=google_ads`. The dated acceptance request for `i ching online` returned `avg_monthly_searches=22200` and `competition=LOW`.

Verified production revision: `c2911ffbb52a6d28b2c31db7e57ec8ac1fad537c`.

The smoke snapshot is evidence of the live data path, not a promise that upstream metrics will remain numerically unchanged.

This document defines the first API capability in `newwords-discovery`. The repository later gained additional sibling APIs, so this file describes the Keyword Volume capability and its final module boundaries rather than the entire repository tree.

## Goal

Provide a private HTTP API that returns Google Ads Keyword Historical Metrics for one or many keywords without exposing Google OAuth credentials to calling agents.

Public route:

```text
POST /api/v1/keyword-volume
```

## Repository architecture

The repository is the API layer. Runtime code lives under `api/`; there is no `src/` application layer.

Keyword Volume's current path is:

```text
api/v1/keyword-volume.py
        │
        ▼
api/lib/_endpoint.py
        │
        ├── api/lib/_keyword_volume.py
        │      request validation + result normalization
        │
        ├── api/lib/_google_ads.py
        │      OAuth + Google Ads client/transport boundary
        │
        ├── api/lib/_auth.py
        ├── api/lib/_config.py
        └── api/lib/_http.py
```

`api/lib/_endpoint.py` is a historical filename and belongs only to Keyword Volume. It is **not** the shared endpoint module for future APIs.

Future APIs are sibling routes under `api/v1/` and receive their own orchestration modules under `api/lib/`.

The shared architecture rules are maintained in the repository README and enforced by `tests/test_api_layout.py`.

## API contract

### Authentication

Every request includes:

```http
Authorization: Bearer <SEO_DATA_API_KEY>
```

The server compares the token using constant-time comparison. Missing or invalid credentials return `401`.

### Request

```json
{
  "keywords": ["i ching online", "i ching reading"],
  "geo_target_constant": "2840",
  "language_constant": "1000",
  "network": "GOOGLE_SEARCH"
}
```

Defaults:

- `geo_target_constant`: `2840` (United States)
- `language_constant`: `1000` (English)
- `network`: `GOOGLE_SEARCH`

`keywords` is required, contains 1–10,000 non-empty strings, and is de-duplicated while preserving first-seen order.

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
      "monthly_search_volumes": []
    }
  ]
}
```

Missing Google metrics remain JSON `null`; they are not silently converted to zero.

## Google Ads integration

The client:

1. exchanges the stored refresh token for an OAuth access token;
2. calls Google Ads `generateKeywordHistoricalMetrics`;
3. sends keywords, geo target, language, and network;
4. normalizes the Google response into the stable API response contract.

Default Google Ads API version is `v24`, overrideable with `GOOGLE_ADS_API_VERSION`.

Google Ads access is isolated behind a client/transport boundary so tests do not require real network calls or credentials.

## Environment variables

Required:

```text
GOOGLE_ADS_CLIENT_ID
GOOGLE_ADS_CLIENT_SECRET
GOOGLE_ADS_REFRESH_TOKEN
GOOGLE_ADS_CUSTOMER_ID
SEO_DATA_API_KEY
```

Optional:

```text
GOOGLE_ADS_API_VERSION=v24
```

No credential value belongs in GitHub.

## Error contract

- `400`: malformed JSON or invalid request parameters.
- `401`: missing/invalid Bearer token.
- `405`: non-POST request.
- `500`: server configuration incomplete.
- `502`: Google OAuth/Ads upstream failure.
- `504`: upstream timeout.

Errors use the shared JSON shape:

```json
{
  "error": {
    "code": "invalid_request",
    "message": "..."
  }
}
```

## Testing

Tests are network-free and cover:

- authentication
- configuration parsing
- request defaults and validation
- keyword de-duplication and limit
- result normalization
- Google Ads transport behavior
- endpoint status/error mapping
- Vercel adapter loading
- repository architecture boundaries

## Scope boundary

Keyword Volume provides search-volume validation for known candidates. It does not perform Google Trends discovery, SEO KD, allintitle/KGR, Semrush, Similarweb, or general workflow orchestration.
