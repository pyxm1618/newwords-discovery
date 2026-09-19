# Google Trends BigQuery API Design

## Status

**Implemented and production-verified on 2026-09-19.**

The repair keeps the existing public route:

```text
POST /api/v1/trends
```

It does not add a second Trends endpoint, does not implement lifecycle classification, and does not change the Keyword Volume / Google Ads path.

Verified implementation revision:

```text
8b2096a49f3026fe61fdc2872cada82f9a2d0356
```

That revision reached Vercel Production `READY` and was then exercised against all four real Google Trends BigQuery table routes.

## Problem fixed

The original query reduced the selected partition to:

```text
term + MIN(rank)
```

and the BigQuery normalization layer emitted only:

```json
{"term": "...", "rank": 1}
```

Therefore Google-provided `week`, `score`, Rising `percent_gain`, and the rolling historical backfill were discarded by this repository.

The fix exposes those facts without adding a lifecycle opinion such as `true_new`, `seasonal`, `news_spike`, S/A/B, or opportunity score.

## Source tables and verified fields

The implementation uses the four fixed Google public tables:

| Market / kind | Table | Fields relevant to this endpoint |
| --- | --- | --- |
| US Top | `bigquery-public-data.google_trends.top_terms` | `refresh_date`, `week`, `dma_name`, `dma_id`, `term`, `score`, `rank` |
| US Rising | `bigquery-public-data.google_trends.top_rising_terms` | US Top fields + `percent_gain` |
| International Top | `bigquery-public-data.google_trends.international_top_terms` | `refresh_date`, `country_code`, `country_name`, `region_name`, `region_code`, `week`, `term`, `score`, `rank` |
| International Rising | `bigquery-public-data.google_trends.international_top_rising_terms` | International Top fields + `percent_gain` |

The fields used by the implementation were validated against the real production BigQuery source by successful queries for US Top, US Rising, GB Top, and GB Rising. A missing or incompatible field would have caused the corresponding query job to fail.

Observed data-grain facts on `refresh_date=2026-09-18`:

- US results contain DMA-level source rows; weekly `region_count` reached roughly 200 for returned terms.
- GB results contain region-level rows; the sampled latest weeks had `region_count=4`.
- The selected daily partition contained 261 weekly points per returned US term and 262 per returned GB term.
- Returned history spans roughly five years: US `2021-09-19 → 2026-09-13`; GB `2021-09-12 → 2026-09-13`.
- null scores occur naturally and are preserved.
- Rising returned real `percent_gain`; Top returned `percent_gain=null`.
- The implementation checks that repeated `rank` values are invariant per selected term, and that Rising `percent_gain` is invariant per selected term. All sampled production terms passed those checks.
- No sampled production route exposed a usable national/country row; all four route-level metadata values were `mean_across_available_regions`.

## Query design

Every query remains partition-safe:

```sql
WHERE refresh_date = @refresh_date
```

International requests additionally use:

```sql
AND country_code = @country_code
```

History is not constructed by scanning five years of `refresh_date` partitions. The selected daily partition already contains historical `week` rows.

The SQL shape is:

```text
base
  → candidate_terms
  → weekly_history
  → final long rows
```

### base

Reads one selected partition and the requested country where applicable.

### candidate_terms

Selects the requested Top/Rising terms and applies `LIMIT` here only.

Therefore:

```text
limit=5
→ at most 5 candidate terms
→ each term still receives its complete weekly history
```

### weekly_history

Groups at:

```text
term + week
```

For each weekly score:

1. if an explicit null-region national/country row exists, use that source level;
2. otherwise calculate `AVG(score)` across available DMA/region rows.

The response makes this explicit through:

```json
{
  "history": {
    "score_aggregation": "mean_across_available_regions"
  }
}
```

The API never silently describes an averaged regional score as an official national score.

`region_count` reports the number of non-null source scores contributing to that weekly point.

## History preservation rules

The endpoint returns the complete weekly curve available in the selected partition and orders it oldest to newest.

It does not:

- convert null to zero;
- delete real zero rows;
- delete declining weeks;
- keep only increasing weeks;
- keep only non-zero weeks;
- reduce history to current/max score;
- run separate 12-month and five-year queries.

Downstream agents can slice the latest ~52 weeks from the same returned history when they need a 12-month view.

## Response contract

Request compatibility remains unchanged:

```json
{
  "kind": "rising",
  "country_code": "US",
  "refresh_date": "2026-09-18",
  "limit": 5
}
```

Successful responses retain `source`, `query`, `usage`, and `results`, and add history metadata plus per-term history:

```json
{
  "source": "google_trends_bigquery",
  "query": {
    "kind": "rising",
    "country_code": "US",
    "refresh_date": "2026-09-18",
    "limit": 5
  },
  "history": {
    "window": "rolling_5_years",
    "granularity": "week",
    "score_aggregation": "mean_across_available_regions"
  },
  "usage": {
    "total_bytes_processed": 79252802,
    "total_bytes_billed": 79691776,
    "cache_hit": false
  },
  "results": [
    {
      "term": "barcelona vs racing santander",
      "rank": 1,
      "percent_gain": 2900,
      "history": [
        {
          "week": "2021-09-19",
          "score": null,
          "region_count": 0
        }
      ]
    }
  ]
}
```

The example above is a real dated production acceptance sample, not fixture data or a product guarantee.

## Billing safety

`BIGQUERY_MAX_BYTES_BILLED` remains enforced by every query.

For the same `US / rising / 2026-09-18 / limit=5` request:

| Version | Bytes processed | Bytes billed | Cache |
| --- | ---: | ---: | --- |
| Previous candidate-only query | 44,779,770 | 45,088,768 | false |
| Rolling-history query | 79,252,802 | 79,691,776 | false |

The repaired query is about `1.77×` the previous scan, not an orders-of-magnitude five-year partition scan.

## Automated verification

The PR CI passed:

```bash
python -m pytest -q
python -m compileall -q api
python -m json.tool vercel.json >/dev/null
```

Coverage includes:

- all four table routes;
- one-partition filtering;
- international country filtering;
- term limit versus history length;
- multi-week ordering;
- null and real zero preservation;
- pullback preservation;
- regional aggregation;
- Rising `percent_gain`;
- Top `percent_gain=null`;
- rank/gain consistency checks;
- BigQuery date/number/null JSON normalization;
- usage metadata;
- HTTP/error behavior.

## Production acceptance

Real authenticated canonical-production smoke, `refresh_date=2026-09-18`:

| Case | Results | Points / term | Earliest | Latest | Processed | Billed | Cache |
| --- | ---: | ---: | --- | --- | ---: | ---: | --- |
| US Rising, limit 5 | 5 | 261 | 2021-09-19 | 2026-09-13 | 79,252,802 | 79,691,776 | false |
| US Top, limit 3 | 3 | 261 | 2021-09-19 | 2026-09-13 | 74,652,288 | 75,497,472 | false |
| GB Rising, limit 3 | 3 | 262 | 2021-09-12 | 2026-09-13 | 440,327,130 | 440,401,920 | false |
| GB Top, limit 3 | 3 | 262 | 2021-09-12 | 2026-09-13 | 354,454,222 | 355,467,264 | false |

All four returned HTTP 200 and `source=google_trends_bigquery`.

### Manual real-term check

A real US Rising result was checked end-to-end:

```text
refresh_date: 2026-09-18
term: barcelona vs racing santander
rank: 1
percent_gain: 2900
history points: 261
earliest: 2021-09-19 → score null
middle sample: 2024-03-17 → score 46.0
latest: 2026-09-13 → score 77.66494845360823
```

This demonstrates that the API is returning historical `week` rows from the same selected partition rather than merely adding an empty `history` field.

## Keyword Volume isolation

The final implementation diff does not modify:

```text
api/v1/keyword-volume.py
api/lib/_endpoint.py
api/lib/_keyword_volume.py
api/lib/_google_ads.py
```

No `GOOGLE_ADS_*` environment variable or Google Ads request logic changed.

## Final decision

**GO.**

The existing Trends route now exposes the historical facts required for downstream lifecycle analysis while keeping request compatibility, partition safety, billing caps, usage metadata, and Keyword Volume isolation intact.
