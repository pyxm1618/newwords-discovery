---
name: finding-trending-keywords
description: Use when the user asks to find or analyze recent hot, rising, trending, emerging, or new keyword opportunities (for example “分析最近1周的热词”, “找今天美国的热词机会”, or “recent rising keywords”). Run the repository Trends discovery flow, research why terms are rising, filter for durable SEO opportunity, and check keyword volume only for retained candidates. Do not use for standalone keyword-volume, KD, allintitle, or SERP-competition requests.
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
- source: `kind=rising`
- window: latest **7 available** `refresh_date` partitions
- per-day candidate limit: `25`
- output language: match the user

For “today”, use the latest available partition. For “最近1周 / last week”, collect seven available partitions rather than assuming seven calendar dates all contain data.

## Workflow

### 1. Discover candidates

Call the production `/api/v1/trends` endpoint for each required `refresh_date`.

Preserve real evidence:

- `term`
- `rank`
- `percent_gain`
- rolling weekly `history`
- `history` metadata
- API `usage`

Never fabricate missing dates, scores, percent gains, or terms.

### 2. Merge the multi-day set

Deduplicate case/whitespace variants while preserving the original query text. Track at least:

- number of appearances
- first and last appearance in the requested window
- best rank
- maximum observed `percent_gain`
- latest available rolling history

Do not treat repeated appearances as separate opportunities.

### 3. Research why each term is rising

Use fresh web/search evidence to answer `why_now`.

Resolve what the term refers to and what users are trying to accomplish. If the entity or cause is ambiguous, say so; do not guess.

### 4. Apply the SEO opportunity filter

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

### 5. Check search volume only after filtering

Send `KEEP` terms to `/api/v1/keyword-volume`. Check a `WATCH` term only when volume would materially resolve the uncertainty.

Google Ads volume is context, not a hard gate. A genuinely new term may show low or zero historical volume because the metric lags emergence.

Do not substitute Ads competition for SEO difficulty.

### 6. Stop at this stage

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

1. scope: market, dates, source, raw count, unique count;
2. counts for `KEEP`, `WATCH`, and `DROP`;
3. each `KEEP` with:
   - term
   - opportunity type
   - why now
   - user need
   - why it can become an SEO asset
   - key Trends history evidence
   - Google Ads volume when available
   - evidence/citations;
4. `WATCH` items with the exact unresolved question;
5. `DROP` summarized by reason/category rather than flooding the user with every discarded term.

If a dropped event produced a verified derivative-demand candidate, show the derivative candidate separately and identify the parent event.

## Evidence discipline

- Real Trends/API values only.
- Fresh sources for `why_now`.
- No invented derivative queries.
- No hard-coded lifecycle thresholds unless the repository later adopts validated thresholds.
- If evidence is insufficient, prefer `WATCH` over a confident story.
