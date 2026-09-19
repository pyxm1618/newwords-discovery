# Keyword Volume API Implementation Record

**Status:** Completed.

This file is retained as the implementation record for the first `newwords-discovery` API. It is **not** the template for future APIs.

The original draft used a parallel application layer. The final repository architecture intentionally removed that layer. All runtime implementation now lives under `api/`, with public Vercel routes in `api/v1/` and private modules in `api/lib/`.

**Spec:** `docs/superpowers/specs/2026-09-17-keyword-volume-api-design.md`

## Final architecture

```text
api/v1/keyword-volume.py
        │
        ▼
api/lib/_endpoint.py
        │
        ├── _keyword_volume.py
        ├── _google_ads.py
        ├── _auth.py
        ├── _config.py
        └── _http.py
```

The shared multi-API architecture rules are documented in the repository README.

## Completed work

### 1. Request validation and normalization

Final files:

- `api/lib/_keyword_volume.py`
- `tests/test_keyword_volume.py`

Implemented:

- [x] default geo/language/network
- [x] keyword de-duplication while preserving order
- [x] invalid/empty keyword rejection
- [x] 10,000 keyword maximum
- [x] Google metric normalization
- [x] missing values preserved as `null`

### 2. Authentication and configuration

Final files:

- `api/lib/_auth.py`
- `api/lib/_config.py`
- `tests/test_auth.py`

Implemented:

- [x] Bearer authentication
- [x] constant-time token comparison
- [x] environment parsing
- [x] secret-safe configuration errors

### 3. Google OAuth and Ads transport

Final files:

- `api/lib/_google_ads.py`
- `tests/test_google_ads.py`

Implemented:

- [x] refresh-token exchange
- [x] Google Ads historical metrics request
- [x] injectable/fakeable transport boundary
- [x] timeout mapping
- [x] upstream error sanitization

### 4. Endpoint orchestration and Vercel route

Final files:

- `api/lib/_endpoint.py`
- `api/v1/keyword-volume.py`
- `tests/test_endpoint.py`
- `tests/test_vercel_adapter.py`

Implemented:

- [x] thin Vercel adapter
- [x] testable endpoint orchestration
- [x] 400 / 401 / 405 / 500 / 502 / 504 mappings
- [x] structured success response

`api/lib/_endpoint.py` remains Keyword Volume-only. New APIs must not add their orchestration to this module.

### 5. Repository/deployment support

Final files include:

- `README.md`
- `docs/API.md`
- `docs/AGENT_USAGE.md`
- `.gitignore`
- `requirements.txt`
- `requirements-dev.txt`
- `pytest.ini`
- `vercel.json`
- `.github/workflows/test.yml`

Implemented:

- [x] Vercel-compatible route layout
- [x] secrets excluded from source control
- [x] automated pytest run
- [x] `compileall api`
- [x] `vercel.json` JSON validation

## Current validation command

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m pytest -q
python3 -m compileall -q api
python3 -m json.tool vercel.json >/dev/null
```

Do not reintroduce `src/` when extending this repository. Follow the README architecture contract and add each future API as a sibling route plus isolated private orchestration.
