# newwords-discovery

Private API layer for AI-driven new-word and SEO discovery workflows.

The repository is deliberately API-first. Public Vercel endpoints and their shared runtime implementation both live under `api/`, so future data-source APIs can be added without mixing them into unrelated application layers.

## Repository layout

```text
api/
├── v1/
│   └── keyword-volume.py      # public HTTP endpoint
└── lib/
    ├── __init__.py
    ├── _auth.py               # private shared helper
    ├── _config.py
    ├── _endpoint.py
    ├── _google_ads.py
    └── _keyword_volume.py
```

Shared helper modules use a leading underscore so Vercel does not turn them into standalone Functions. New public APIs should be added under `api/v1/` and may reuse code from `api/lib/`.

## Endpoint

```text
POST /api/v1/keyword-volume
```

Default query scope:

- geo target: `2840` (United States)
- language: `1000` (English)
- network: `GOOGLE_SEARCH`

See [`docs/API.md`](docs/API.md) for the full request/response contract.

## Vercel environment variables

Set these in the Vercel project. Do not commit their values to GitHub.

```text
GOOGLE_ADS_CLIENT_ID
GOOGLE_ADS_CLIENT_SECRET
GOOGLE_ADS_REFRESH_TOKEN
GOOGLE_ADS_CUSTOMER_ID
SEO_DATA_API_KEY
```

Optional:

```text
GOOGLE_ADS_API_VERSION=v24
```

Generate a strong private API key locally, for example:

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
```

Use the same `SEO_DATA_API_KEY` in Vercel and in the calling agent's secret store.

## Deploy

1. Import this GitHub repository into Vercel.
2. Keep the repository root as the Vercel project root.
3. Add the environment variables above for Production (and Preview only if needed).
4. Deploy.
5. Call `POST https://<deployment>/api/v1/keyword-volume` with the Bearer key.

The Python function uses only the standard library. Vercel recognizes Python files under `api/` that export a `BaseHTTPRequestHandler` subclass named `handler`.

## Development

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m pytest
python3 -m compileall api
```

No Google credentials are required for the automated test suite; upstream HTTP is replaced with fakes at the transport boundary.
