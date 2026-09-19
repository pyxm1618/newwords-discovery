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

Current production Trends status: **verified with rolling history**.

Implementation revision `8b2096a49f3026fe61fdc2872cada82f9a2d0356` reached Vercel Production `READY`, then the canonical production endpoint was called with the existing Bearer secret against all four Google Trends table routes for `refresh_date=2026-09-18`.

### Google Trends four-route smoke

| Case | Results | History points / term | Earliest week | Latest week | Bytes processed | Bytes billed | Cache |
| --- | ---: | ---: | --- | --- | ---: | ---: | --- |
| US rising, limit 5 | 5 | 261 | 2021-09-19 | 2026-09-13 | 79,252,802 | 79,691,776 | false |
| US top, limit 3 | 3 | 261 | 2021-09-19 | 2026-09-13 | 74,652,288 | 75,497,472 | false |
| GB rising, limit 3 | 3 | 262 | 2021-09-12 | 2026-09-13 | 440,327,130 | 440,401,920 | false |
| GB top, limit 3 | 3 | 262 | 2021-09-12 | 2026-09-13 | 354,454,222 | 355,467,264 | false |

All four returned:

```text
HTTP 200
source = google_trends_bigquery
history.window = rolling_5_years
history.granularity = week
history.score_aggregation = mean_across_available_regions
```

The live rows proved that the selected daily partition contains hundreds of distinct historical `week` rows per term. The smoke also observed real null scores, real regional contribution counts, Rising `percent_gain`, and Top `percent_gain=null`.

One manually inspected Rising term was:

```text
refresh_date = 2026-09-18
term = barcelona vs racing santander
rank = 1
percent_gain = 2900
history_points = 261
earliest = 2021-09-19, score = null
middle sample = 2024-03-17, score = 46.0
latest = 2026-09-13, score = 77.66494845360823
```

This confirms that `history` is the same selected partition's historical backfill rather than a separately scanned sequence of old `refresh_date` partitions.

### Cost comparison for the same US Rising request

The earlier candidate-only production request for `US/rising/2026-09-18/limit=5` processed `44,779,770` bytes and billed `45,088,768` bytes.

The rolling-history implementation processed `79,252,802` bytes and billed `79,691,776` bytes for the same request shape: about `1.77×` the previous scan, not a multi-year partition scan. `BIGQUERY_MAX_BYTES_BILLED` remains enforced.

### Keyword Volume isolation

The Trends repair did not modify:

```text
api/v1/keyword-volume.py
api/lib/_endpoint.py
api/lib/_keyword_volume.py
api/lib/_google_ads.py
```

The existing Keyword Volume contract and Google Ads implementation remain unchanged.

These values are dated acceptance snapshots, not hard-coded product guarantees. Upstream data can change on later calls.

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

Returns daily Top or Rising candidate terms from Google's public Google Trends dataset in BigQuery, together with the rolling weekly historical backfill that Google stores in the same `refresh_date` partition.

This route is for candidate discovery and lifecycle evidence. It does not accept an arbitrary keyword.

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
- `limit` restricts candidate terms only; it never truncates a term's weekly history.
- US requests use the fixed US table set.
- non-US requests use the fixed international table set and parameterize `country_code`.
- every query reads exactly one `refresh_date` partition. It does not scan older partitions to construct history.
- Google already stores the rolling historical weekly rows inside that selected partition.
- every query is constrained by `BIGQUERY_MAX_BYTES_BILLED`.

### History semantics

For each candidate term, `history` is ordered by `week` ascending and retains the complete weekly rows made available by Google for that selected partition.

The API does not:

- convert missing/null scores to zero;
- remove real `score=0` rows;
- remove pullback weeks;
- keep only rising weeks;
- collapse the history to a current/maximum score.

Google's source data is geographic: US rows are DMA-grained and international rows are region-grained. For a given `term + week`:

1. if the source provides an explicit null-region national/country row, that row is preferred;
2. otherwise the API returns `AVG(score)` across available region/DMA scores and labels the response `score_aggregation=mean_across_available_regions`.

`region_count` is the count of non-null source scores contributing to that weekly score. It is metadata, not a search-volume metric.

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
  "history": {
    "window": "rolling_5_years",
    "granularity": "week",
    "score_aggregation": "mean_across_available_regions"
  },
  "usage": {
    "total_bytes_processed": 123456,
    "total_bytes_billed": 10000000,
    "cache_hit": false
  },
  "results": [
    {
      "term": "example rising term",
      "rank": 1,
      "percent_gain": 1250,
      "history": [
        {
          "week": "2021-09-19",
          "score": 0,
          "region_count": 10
        },
        {
          "week": "2021-09-26",
          "score": 18.5,
          "region_count": 10
        }
      ]
    }
  ]
}
```

The numeric values above illustrate response shape only. Production acceptance records use actual observed values.

For `kind=rising`, `percent_gain` is Google's source field. For `kind=top`, `percent_gain` is `null` so the response shape remains stable.

`rank` is candidate metadata, not a historical trend value; it is not repeated inside each weekly point.

`usage` remains part of the contract so callers can record actual BigQuery scan/billing behavior.

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

The service account must be permitted to create BigQuery query jobs in the query project. The Google Trends source tables are public, but the query job still needs a project and valid credentials.

Credential handling:

- store the complete JSON only in Vercel as `GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON`;
- do not commit or paste the service-account JSON into documentation, source, issues, prompts, or chat;
- keep the corresponding Google Cloud key active while Vercel uses it.

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
