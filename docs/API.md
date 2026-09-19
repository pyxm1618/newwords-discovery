# API

All endpoints use:

```http
Authorization: Bearer <API_KEY>
Content-Type: application/json
```

Server-side, Vercel stores the expected Bearer secret as:

```text
SEO_DATA_API_KEY
```

Calling Agents should store the same value once in their secure runtime as `NEWWORDS_DISCOVERY_API_KEY`.

---

## `POST /api/v1/keyword-volume`

Canonical production URL:

```text
https://newwords-discovery.vercel.app/api/v1/keyword-volume
```

Returns Google Ads Keyword Historical Metrics in normalized JSON.

### Request

Minimal request:

```json
{
  "keywords": ["i ching online", "i ching reading"]
}
```

Explicit scope:

```json
{
  "keywords": ["i ching online", "i ching reading"],
  "geo_target_constant": "2840",
  "language_constant": "1000",
  "network": "GOOGLE_SEARCH"
}
```

Rules:

- `keywords` is required and must contain 1–10,000 non-empty strings.
- duplicate keywords are removed while preserving first-seen order.
- `geo_target_constant` defaults to `2840`.
- `language_constant` defaults to `1000`.
- `network` defaults to `GOOGLE_SEARCH` and also accepts `GOOGLE_SEARCH_AND_PARTNERS`.

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

The numbers above show the response schema; the endpoint requests current Google Ads data.

`competition` and `competition_index` are advertising competition metrics, not SEO Keyword Difficulty.

---

## `POST /api/v1/trends`

Canonical production URL:

```text
https://newwords-discovery.vercel.app/api/v1/trends
```

Returns daily Top or Rising search terms from Google's public Google Trends dataset in BigQuery.

This API is intended for candidate discovery. It does not accept an arbitrary keyword and return its Google Trends curve.

### Request

Minimal request:

```json
{
  "kind": "rising",
  "country_code": "US"
}
```

Explicit request:

```json
{
  "kind": "rising",
  "country_code": "GB",
  "refresh_date": "2026-09-18",
  "limit": 25
}
```

Rules:

- `kind` is `rising` or `top`; default is `rising`.
- `country_code` is a two-letter ISO country code; default is `US`.
- `refresh_date` is `YYYY-MM-DD`; default is yesterday in UTC.
- `limit` is 1–25; default is 25.
- `US` is routed to the US Google Trends tables.
- other country codes are routed to the international Google Trends tables.
- table names are selected from fixed server-side constants; user input is never interpolated as a table name.
- `refresh_date` and `country_code` are BigQuery query parameters.
- every query is constrained by `BIGQUERY_MAX_BYTES_BILLED`.

The endpoint groups the historical rows in each daily partition by `term` and returns the daily term/rank candidate list rather than returning the full five-year backfill embedded in that partition.

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

`usage` is returned so discovery jobs can track real BigQuery scan/billing behavior instead of estimating it from request counts.

### BigQuery server configuration

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

`GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON` must contain the complete service-account JSON as one Vercel secret value.

If `GOOGLE_CLOUD_PROJECT` is omitted, the service-account JSON's `project_id` is used.

The service account must have permission to create BigQuery query jobs in the query project. The queried Google Trends tables themselves are public.

### curl

```bash
curl -X POST 'https://newwords-discovery.vercel.app/api/v1/trends' \
  -H "Authorization: Bearer $NEWWORDS_DISCOVERY_API_KEY" \
  -H 'Content-Type: application/json' \
  --data '{"kind":"rising","country_code":"GB","refresh_date":"2026-09-18"}'
```

---

## Shared error responses

```json
{
  "error": {
    "code": "invalid_request",
    "message": "..."
  }
}
```

Status codes:

- `400` invalid JSON or request parameters
- `401` missing or invalid Bearer key
- `405` non-POST method
- `500` server environment is incomplete
- `502` Google upstream request failed
- `504` Google upstream timed out

Raw Google error bodies and credentials are intentionally not returned.
