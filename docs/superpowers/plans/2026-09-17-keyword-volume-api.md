# Keyword Volume API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deployable private Vercel API that lets AI agents batch-query Google Ads keyword historical search volume without receiving Google OAuth credentials.

**Architecture:** A thin Vercel Python HTTP handler under `api/v1/` delegates authentication, validation, Google OAuth token exchange, Google Ads REST calls, and result normalization to focused modules under `src/newwords_api/`. No persistent database and no CLI are added.

**Tech Stack:** Python 3.12+, Python standard library HTTP client, Vercel Python Functions, pytest.

**Spec:** `docs/superpowers/specs/2026-09-17-keyword-volume-api-design.md`

## Global Constraints

- API-first service; no local CLI as the production interface.
- GitHub contains code only; Google credentials never enter the repository.
- Required Vercel secrets: `GOOGLE_ADS_CLIENT_ID`, `GOOGLE_ADS_CLIENT_SECRET`, `GOOGLE_ADS_REFRESH_TOKEN`, `GOOGLE_ADS_CUSTOMER_ID`, `SEO_DATA_API_KEY`.
- Default query scope: geo target `2840`, language `1000`, network `GOOGLE_SEARCH`.
- Default Google Ads API version: `v24`, overrideable with `GOOGLE_ADS_API_VERSION`.
- Missing Google metrics remain `null`, never silently become `0`.
- Do not log or return OAuth credentials, refresh tokens, access tokens, or API keys.
- Maximum 10,000 keywords per request.

---

### Task 1: Core request validation and normalization

**Files:**
- Create: `tests/test_keyword_volume.py`
- Create: `src/__init__.py`
- Create: `src/newwords_api/__init__.py`
- Create: `src/newwords_api/keyword_volume.py`

**Interfaces:**
- Produces: `validate_keyword_volume_request(payload: object) -> KeywordVolumeRequest`
- Produces: `normalize_google_results(data: dict) -> list[dict]`

- [ ] Write tests first for defaults, de-duplication, empty/invalid keywords, 10,000 keyword limit, network validation, and preservation of `None` values.
- [ ] Run `pytest tests/test_keyword_volume.py -q` and confirm failure because production module is missing.
- [ ] Implement immutable `KeywordVolumeRequest` plus validation and normalization.
- [ ] Re-run `pytest tests/test_keyword_volume.py -q` and confirm pass.

### Task 2: Secret-safe API authentication and configuration

**Files:**
- Create: `tests/test_auth.py`
- Create: `src/newwords_api/auth.py`
- Create: `src/newwords_api/config.py`

**Interfaces:**
- Produces: `is_authorized(authorization_header: str | None, expected_api_key: str) -> bool`
- Produces: `Settings.from_env() -> Settings`

- [ ] Write tests first for missing, malformed, incorrect, and correct Bearer tokens plus missing configuration.
- [ ] Run `pytest tests/test_auth.py -q` and confirm failure.
- [ ] Implement constant-time Bearer comparison and environment configuration parsing.
- [ ] Re-run `pytest tests/test_auth.py -q` and confirm pass.

### Task 3: Google OAuth and Ads transport

**Files:**
- Create: `tests/test_google_ads.py`
- Create: `src/newwords_api/google_ads.py`

**Interfaces:**
- Produces: `GoogleAdsClient(settings: Settings, transport: HttpTransport | None = None)`
- Produces: `GoogleAdsClient.generate_historical_metrics(request: KeywordVolumeRequest) -> dict`
- Produces: typed upstream exceptions without secret-bearing response bodies.

- [ ] Write failing tests using a fake transport for token exchange, Google Ads request shape, timeout mapping, and upstream error sanitization.
- [ ] Run `pytest tests/test_google_ads.py -q` and confirm failure.
- [ ] Implement standard-library HTTP transport, refresh-token exchange, Google Ads request, and sanitized exceptions.
- [ ] Re-run `pytest tests/test_google_ads.py -q` and confirm pass.

### Task 4: Vercel HTTP endpoint

**Files:**
- Create: `tests/test_endpoint.py`
- Create: `src/newwords_api/endpoint.py`
- Create: `api/v1/keyword-volume.py`

**Interfaces:**
- Produces: `handle_keyword_volume(method, headers, body, settings, client_factory) -> (status, headers, body)` for testable HTTP behavior.
- Vercel route: `POST /api/v1/keyword-volume`

- [ ] Write failing tests for 405, 401, 400, 500, 502/504, and successful structured response.
- [ ] Run `pytest tests/test_endpoint.py -q` and confirm failure.
- [ ] Implement pure endpoint orchestration and thin Vercel `BaseHTTPRequestHandler` adapter.
- [ ] Re-run `pytest tests/test_endpoint.py -q` and confirm pass.

### Task 5: Deployment and operator documentation

**Files:**
- Create: `README.md`
- Create: `docs/API.md`
- Create: `.gitignore`
- Create: `requirements.txt`
- Create: `pytest.ini`
- Create: `vercel.json`

**Interfaces:**
- Documents the public-to-agent API contract and Vercel environment variable setup.

- [ ] Add `.env*`, Python cache, Vercel local state, and test caches to `.gitignore`.
- [ ] Document Vercel deployment, required environment variables, Bearer authentication, curl examples, batch requests, response fields, and error codes.
- [ ] Keep runtime dependencies minimal; pytest is only a development/test dependency.
- [ ] Run `python -m pytest -q` and confirm all tests pass.
- [ ] Run `python -m compileall api src` and confirm syntax validity.
