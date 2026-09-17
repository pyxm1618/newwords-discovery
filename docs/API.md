# API

## `POST /api/v1/keyword-volume`

Canonical production URL:

```text
https://newwords-discovery.vercel.app/api/v1/keyword-volume
```

Returns Google Ads Keyword Historical Metrics in normalized JSON.

### Authentication

```http
Authorization: Bearer <API_KEY>
Content-Type: application/json
```

Server-side, Vercel stores the expected secret as:

```text
SEO_DATA_API_KEY
```

Calling Agents should store the same value once in their own secure runtime. Recommended caller-side variable name:

```text
NEWWORDS_DISCOVERY_API_KEY
```

The Agent must not ask the user to paste the API key on every request. It should read the configured caller-side secret automatically. The literal key must not be committed, logged, printed, or written into prompts/Skill/Agent.md files.

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
- `language_target_constant` is not used; use `language_constant`.
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

Numbers shown above are an example of the schema, not a cached API response. The endpoint requests current data from Google Ads. Missing Google metrics are returned as `null`, not `0`.

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

Assuming the calling environment already contains `NEWWORDS_DISCOVERY_API_KEY`:

```bash
curl -X POST 'https://newwords-discovery.vercel.app/api/v1/keyword-volume' \
  -H "Authorization: Bearer $NEWWORDS_DISCOVERY_API_KEY" \
  -H 'Content-Type: application/json' \
  --data '{"keywords":["i ching online","i ching reading","i ching coins"]}'
```

## Agent usage

Agents should treat this service as a private data source.

The Agent needs only:

- fixed endpoint URL: `https://newwords-discovery.vercel.app/api/v1/keyword-volume`
- caller-side secret variable: `NEWWORDS_DISCOVERY_API_KEY`
- request keywords and optional Google Ads constants

The Agent does **not** need these Google credentials:

```text
GOOGLE_ADS_CLIENT_ID
GOOGLE_ADS_CLIENT_SECRET
GOOGLE_ADS_REFRESH_TOKEN
GOOGLE_ADS_CUSTOMER_ID
```

Those remain only in Vercel.

If `NEWWORDS_DISCOVERY_API_KEY` is not configured, the Agent should report that its local/caller secret is missing. It should not ask the user to paste the secret into the conversation.

See [`AGENT_USAGE.md`](AGENT_USAGE.md) for the complete calling and secret-handling rules.

The returned `competition` and `competition_index` are Google Ads advertising competition metrics, not SEO keyword difficulty.
