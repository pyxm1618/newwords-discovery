---
name: finding-trending-keywords
description: Use when the user asks to find or analyze recent hot, rising, trending, emerging, or new keyword opportunities (for example “分析最近1周的热词”, “找今天美国的热词机会”, “最近4小时有什么新词”, or “recent rising keywords”). Use Trending Now RPC for real-time discovery, BigQuery daily Trends for lifecycle validation/backfill, research why terms are rising, filter for durable SEO opportunity, and check keyword volume only for retained candidates. Do not use for standalone keyword-volume, KD, allintitle, or SERP-competition requests.
---

# Finding Trending Keywords

## Goal

Find **search-demand opportunities that can become durable SEO assets**, not a report of whatever is hottest today.

Two rules control the workflow:

1. **An event itself is not the opportunity. A new search need created by the event may be.**
2. **Do not narrow by industry.** AI and games are examples, not preferred categories. Judge whether the demand can be served by a durable page, tool, database, guide, template, product, or other SEO asset.

Read `docs/AGENT_USAGE.md` for API calling rules and `references/seo-opportunity-filter.md` for the opportunity methodology before classifying candidates.

## Defaults

Unless the user overrides them:

- market: `US`
- real-time discovery source: Google Trending Now RPC, latest `4` hours
- real-time candidate limit: `50`
- daily validation source: BigQuery `kind=rising`
- historical window when requested: latest available daily `refresh_date` partitions
- daily candidate limit: `25`
- output language: match the user

For “现在 / today / latest / 最近4小时”, use Trending Now RPC first. For “最近N天”, collect the requested number of available BigQuery daily partitions; the current 4-hour pool may be added as a separate current snapshot but must never be presented as one of those daily partitions.

## Workflow

### 1. Discover the current pool

For real-time requests, call `/api/v1/trending-now` once for each requested country.

Default request:

```json
{
  "country_code": "US",
  "hours": 4,
  "limit": 50,
  "hl": "en"
}
```

Supported `hours`: `4`, `24`, `48`, `168`.

Preserve real evidence:

- `query`
- `search_volume`
- `increase_percentage`
- `started_at` / `ended_at`
- `active`
- `trend_breakdown`
- `category_ids`
- `observed_at`
- exact country and window

The real-time source is the Google Trending Now web RPC. It is not BigQuery, Google Ads, Google Trends API Alpha, or RSS. There is no silent fallback.

**Do not probe backward when a country has no real-time data.** One country + one requested window is one discovery call. If it returns no rows or an upstream error, report that country as unavailable for that query and move on. Do not start scanning older BigQuery dates just to prove absence.

### 2. Add daily lifecycle evidence when needed

Use `/api/v1/trends` with `kind=rising` for daily discovery/backfill and rolling weekly history.

For a historical request such as “最近15天”, collect the requested number of available daily partitions. Do not keep scanning far backward after repeated empty partitions. If the requested market is unsupported or repeatedly empty, report that limitation instead of burning BigQuery scan quota.

Preserve:

- `term`
- `rank`
- `percent_gain`
- rolling weekly `history`
- history metadata
- API `usage`
- actual `refresh_date`

Never fabricate missing dates, scores, percent gains, terms, or search volume.

### 3. Merge and deduplicate

Deduplicate case/whitespace variants while preserving original query text. Track source and evidence separately:

- real-time appearance and 4h/24h/48h/168h window
- daily appearance count
- first and last daily appearance
- best rank
- maximum observed `percent_gain`
- latest rolling history

Do not treat repeated appearances as separate opportunities.

### 4. Research why each term is rising

Use fresh web/search evidence to answer `why_now`.

Resolve what the term refers to and what users are trying to accomplish. If the entity or cause is ambiguous, say so; do not guess.

### 5. Apply the SEO opportunity filter

Use `references/seo-opportunity-filter.md`.

Classify each raw term as:

- `KEEP`
- `WATCH`
- `DROP`

A `KEEP` must also have one opportunity type:

- `TRUE_NEW`
- `RESURGENCE`
- `EVENT_DERIVED`

A raw news/event/celebrity/sports/film/promotion/company incident term is normally `DROP`. Before discarding the whole lead, check whether the event has produced an **actual, evidence-backed derivative user task or query**. Do not invent derivative keywords because they sound plausible.

### 6. Check search volume only after filtering

Send `KEEP` terms to `/api/v1/keyword-volume`. Check a `WATCH` term only when volume would materially resolve the uncertainty.

Google Ads volume is context, not a hard gate. A genuinely new term may show low or zero historical volume because the metric lags emergence.

Do not substitute Ads competition for SEO difficulty.

### 7. Stop at this stage

This skill does **not** perform:

- KD scoring
- `allintitle`
- SERP supply/competition analysis
- backlink analysis
- final project selection

Those belong to later stages.

## Output contract

Lead with the filtered opportunities, not the raw hot-word dump.

Report:

1. scope: market, exact real-time window and/or daily dates, source, raw count, unique count;
2. counts for `KEEP`, `WATCH`, and `DROP`;
3. each `KEEP` with term, opportunity type, why now, user need, why it can become an SEO asset, key Trends evidence, Google Ads volume when available, and citations;
4. `WATCH` items with the exact unresolved question;
5. `DROP` summarized by reason/category rather than flooding the user with every discarded term.

If a dropped event produced a verified derivative-demand candidate, show the derivative candidate separately and identify the parent event.

## Evidence discipline

- Real API values only.
- Fresh sources for `why_now`.
- No invented derivative queries.
- No hard-coded lifecycle thresholds unless the repository later adopts validated thresholds.
- If evidence is insufficient, prefer `WATCH` over a confident story.
- If the Trending Now RPC fails, report the failure. Do not silently replace it with RSS or another data source and present that output as RPC data.
