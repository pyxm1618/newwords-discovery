---
name: finding-trending-keywords
description: Use when the user asks to find or analyze recent hot, rising, trending, emerging, or new keyword opportunities. Discover candidates with the Newwords Discovery MCP tools, research why terms are rising, filter for durable SEO opportunity, and check keyword volume only for retained candidates.
---

# Finding Trending Keywords

## Goal

Find search-demand opportunities that can become durable SEO assets, not a report of whatever is hottest today.

Two rules control the workflow:

1. An event itself is not the opportunity. A new search need created by the event may be.
2. Do not narrow by industry. Judge whether the demand can be served by a durable page, tool, database, guide, template, product, or other SEO asset.

Read references/seo-opportunity-filter.md before classifying candidates.

## Defaults

Unless the user overrides them:

- market: US
- source: kind=rising
- window: latest 7 available refresh-date partitions
- per-day candidate limit: 25
- output language: match the user

When the user asks for a different window, use that many available partitions. For example, 最近3天 means the latest three partitions that return data, not blindly three calendar dates.

## Workflow

### 1. Discover candidates

Call the MCP tool get_trending_keywords once per required refresh date.

Start from the latest likely date and step backward until the requested number of non-empty partitions has been collected. Do not count an empty or missing partition as an available day.

Preserve real evidence:

- term
- rank
- percent_gain
- rolling weekly history
- history metadata
- API usage
- actual refresh_date

Never fabricate missing dates, scores, percent gains, terms, or search volume.

### 2. Merge the multi-day set

Deduplicate case and whitespace variants while preserving the original query text. Track at least:

- number of appearances
- first and last appearance in the requested window
- best rank
- maximum observed percent_gain
- latest available rolling history

Do not treat repeated appearances as separate opportunities.

### 3. Research why each term is rising

Use fresh web or search evidence to answer why_now.

Resolve what the term refers to and what users are trying to accomplish. If the entity or cause is ambiguous, say so; do not guess.

### 4. Apply the SEO opportunity filter

Use references/seo-opportunity-filter.md.

Classify each raw term as KEEP, WATCH, or DROP.

A KEEP must also have one opportunity type: TRUE_NEW, RESURGENCE, or EVENT_DERIVED.

A raw news, event, celebrity, sports, film, promotion, or company-incident term is normally DROP. Before discarding the whole lead, check whether the event has produced an actual, evidence-backed derivative user task or query. Do not invent derivative keywords because they sound plausible.

### 5. Check search volume only after filtering

Send KEEP terms to the MCP tool get_keyword_volume. Check a WATCH term only when volume would materially resolve the uncertainty.

Google Ads volume is context, not a hard gate. A genuinely new term may show low or zero historical volume because the metric lags emergence.

Do not substitute Ads competition for SEO difficulty.

### 6. Stop at this stage

This workflow does not perform KD scoring, allintitle, SERP supply analysis, backlink analysis, or final project selection.

## Output contract

Lead with the filtered opportunities, not the raw hot-word dump.

Report:

1. scope: market, actual dates, source, raw count, unique count;
2. counts for KEEP, WATCH, and DROP;
3. each KEEP with term, opportunity type, why now, user need, asset thesis, Trends lifecycle evidence, Google Ads volume when available, and citations;
4. WATCH items with the exact unresolved question;
5. DROP summarized by reason or category.

If a dropped event produced a verified derivative-demand candidate, show the derivative candidate separately and identify the parent event.

## Evidence discipline

- Real MCP and API values only.
- Fresh sources for why_now.
- No invented derivative queries.
- No hard-coded lifecycle thresholds unless the repository later adopts validated thresholds.
- If evidence is insufficient, prefer WATCH over a confident story.
- If either MCP tool fails, report the failure. Do not silently replace it with a different data source and present the result as if the MCP workflow ran.
