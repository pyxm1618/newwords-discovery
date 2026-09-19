# API

Canonical domain:

```text
https://newwords-discovery.vercel.app
```

All routes use:

```http
Authorization: Bearer <API_KEY>
Content-Type: application/json
```

Vercel stores the expected Bearer secret as:

```text
SEO_DATA_API_KEY
```

Calling agents should store the same value as `NEWWORDS_DISCOVERY_API_KEY`.

The contracts below describe implemented routes. A route is only production-verified after its current Vercel deployment is READY and an authenticated smoke request reaches the real upstream successfully. Build success alone does not prove upstream credentials or permissions.

## Production acceptance record — 2026-09-19

Current production status: **verified**.

The production deployment for `main` revision `c2911ffbb52a6d28b2c31db7e57ec8ac1fad537c` reached Vercel `READY`, then both upstream paths were called with a valid Bearer token.

### Trends smoke

Request:

```json
{
  "kind": "rising",
  "country_code": "US",
  "refresh_date": "2026-09-18",
  "limit": 5
}
```

Observed production result:

```text
HTTP 200
source = google_trends_bigquery
total_bytes_processed = 44779770
total_bytes_billed = 45088768
cache_hit = false
results_count = 5
```

The response contained real Google Trends rows, proving the full path:

```text
Vercel → service-account credential → Google authentication
→ BigQuery query job → public Google Trends dataset → API response
```

### Keyword Volume regression smoke

Observed production result:

```text
HTTP 200
source = google_ads
keyword = i ching online
avg_monthly_searches = 22200
competition = LOW
```

These values are a dated acceptance snapshot, not hard-coded product guarantees. Upstream data can change on later calls.

A future deployment or credential rotation requires a new authenticated smoke before the new state is called production-verified.

---

## `POST /api/v1/keyword-volume`

Returns normalized Google Ads Keyword Historical Metrics.

### Request

Minimal:

```json
{
  "keywords": ["i ching online", "i ching reading"]
}
```

Explicit:

```json
{
  "keywords": ["i ching online", "i ching reading"],
  "geo_target_constant": "2840",
  "language_constant": "1000",
  "network": "GOOGLE_SEARCH"
}
```

Rules:

- `keywords`: required, 1–10,000 non-empty strings.
- duplicates are removed while preserving first-seen order.
- `geo_target_constant`: default `2840` (United States).
- `language_constant`: default `1000` (English).
- `network`: default `GOOGLE_SEARCH`; also accepts `GOOGLE_SEARCH_AND_PARTNERS`.

### Success response

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

The numbers above illustrate the response shape. The endpoint requests current Google Ads data at call time.

`competition` and `competition_index` are advertising competition metrics, not SEO Keyword Difficulty.

### Server configuration

Required:

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

---

## `POST /api/v1/trends`

Returns daily Top or Rising terms from Google's public Google Trends dataset in BigQuery.

This route is for candidate discovery. It does not accept an arbitrary keyword and return a Google Trends time-series curve.

### Request

Minimal:

```json
{
  "kind": "rising",
  "country_code": "US"
}
```

Explicit:

```json
{
  "kind": "rising",
  "country_code": "GB",
  "refresh_date": "2026-09-18",
  "limit": 25
}
```

Rules:

- `kind`: `rising` or `top`; default `rising`.
- `country_code`: two-letter ISO code; default `US`.
- `refresh_date`: `YYYY-MM-DD`; default UTC yesterday.
- `limit`: integer 1–25; default 25.
- US requests use the fixed US table set.
- non-US requests use the fixed international table set and parameterize `country_code`.
- table identifiers come only from server-side constants; user input is never interpolated as a table name.
- `refresh_date` and international `country_code` are BigQuery query parameters.
- every query is constrained by `BIGQUERY_MAX_BYTES_BILLED`.

The query groups rows by `term` for the selected `refresh_date` and returns the daily term/rank candidate list.

### Success response

```json
{
  "source": "google_trends_bigquery",
  "query": {
    "kind": "rising",
    "country_code": "GB",
    "refresh_date": "2026-09-18",
    "limit": 25
  },
  "usage": {
    "total_bytes_processed": 123456,
    "total_bytes_billed": 10000000,
    "cache_hit": false
  },
  "results": [
    {
      "term": "example rising term",
      "rank": 1
    }
  ]
}
```

`usage` is part of the contract so callers can record actual BigQuery scan/billing behavior.

### Server configuration

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

`GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON` is the complete service-account JSON stored as one server-side secret.

If `GOOGLE_CLOUD_PROJECT` is omitted, the service-account JSON's `project_id` is used.

The service account must be permitted to create BigQuery query jobs in the query project. The production service account uses the `BigQuery Job User` role for this capability. The Google Trends source tables are public, but the query job still needs a project and valid credentials.

Credential handling:

- store the complete JSON only in Vercel as `GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON`;
- do not commit or paste the service-account JSON into documentation, source, issues, prompts, or chat;
- delete the downloaded local JSON after production verification;
- keep the corresponding Google Cloud key active while Vercel uses it;
- restoring an organization policy that blocks *new* service-account key creation does not revoke an existing key.

### curl

```bash
curl -X POST 'https://newwords-discovery.vercel.app/api/v1/trends' \
  -H "Authorization: Bearer $NEWWORDS_DISCOVERY_API_KEY" \
  -H 'Content-Type: application/json' \
  --data '{"kind":"rising","country_code":"GB","refresh_date":"2026-09-18"}'
```

---

## Error contract

Errors use:

```json
{
  "error": {
    "code": "invalid_request",
    "message": "..."
  }
}
```

Status codes:

- `400`: invalid JSON or request parameters.
- `401`: missing or invalid Bearer key.
- `405`: non-POST method.
- `500`: required server configuration is incomplete.
- `502`: upstream Google service failed.
- `504`: upstream request timed out.

Raw credentials, OAuth tokens, service-account material, and raw secret-bearing upstream bodies must never be returned.
