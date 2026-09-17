# API

## `POST /api/v1/keyword-volume`

Returns Google Ads Keyword Historical Metrics in normalized JSON.

### Authentication

```http
Authorization: Bearer <SEO_DATA_API_KEY>
Content-Type: application/json
```

### Request

Minimal request:

```json
{
  "keywords": ["i ching online", "i ching reading"]
}
```

Explicit Google Ads constants:

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
      "monthly_search_volumes": [
        {
          "year": 2026,
          "month": "AUGUST",
          "monthly_searches": 22200
        }
      ]
    }
  ]
}
```

Numbers shown above are an example of the schema, not a cached API response. The endpoint always requests current data from Google Ads. Missing Google metrics are returned as `null`, not `0`.

### Error response

```json
{
  "error": {
    "code": "invalid_request",
    "message": "keywords must be a non-empty array of strings"
  }
}
```

Status codes:

- `400` invalid JSON or request parameters
- `401` missing or invalid Bearer key
- `405` non-POST method
- `500` Vercel/server environment is incomplete
- `502` Google OAuth or Google Ads rejected/failed the upstream request
- `504` Google upstream timed out

Upstream response bodies and credentials are intentionally not returned.

### curl

```bash
curl -X POST 'https://<deployment>/api/v1/keyword-volume' \
  -H "Authorization: Bearer $SEO_DATA_API_KEY" \
  -H 'Content-Type: application/json' \
  --data '{"keywords":["i ching online","i ching reading","i ching coins"]}'
```

## Agent usage

Agents should treat this service as a data source. The Google OAuth client ID, client secret, refresh token, and customer ID remain server-side in Vercel. An agent only needs:

- endpoint URL
- `SEO_DATA_API_KEY`
- request keywords and optional Google Ads constants

The returned `competition` and `competition_index` are Google Ads advertising competition metrics, not SEO keyword difficulty.
