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

## Production API

Canonical production endpoint:

```text
POST https://newwords-discovery.vercel.app/api/v1/keyword-volume
```

Agents should use this stable production domain, not random deployment URLs.

Default query scope:

- geo target: `2840` (United States)
- language: `1000` (English)
- network: `GOOGLE_SEARCH`

See [`docs/API.md`](docs/API.md) for the full request/response contract and [`docs/AGENT_USAGE.md`](docs/AGENT_USAGE.md) for the exact AI/Agent calling rules.

## Secret model

Google credentials remain server-side in Vercel:

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

`SEO_DATA_API_KEY` is the server-side verification secret. The calling Agent must also have the same secret available in its own secure runtime, but it should be stored there once rather than pasted into prompts or supplied on every request.

Recommended caller-side variable name:

```text
NEWWORDS_DISCOVERY_API_KEY
```

The value of `NEWWORDS_DISCOVERY_API_KEY` must equal Vercel's `SEO_DATA_API_KEY`.

Never commit either value to GitHub and never put the literal secret in README, Agent.md, Skills, scripts, prompts, or chat messages.

Generate/rotate a strong private API key locally, for example:

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
```

## Deploy

1. Import this GitHub repository into Vercel.
2. Keep the repository root as the Vercel project root.
3. Add the server environment variables above for Production (and Preview only if needed).
4. Deploy.
5. Call the canonical production endpoint with `Authorization: Bearer <caller secret>`.

The Python function uses only the standard library. Vercel recognizes Python files under `api/` that export a `BaseHTTPRequestHandler` subclass named `handler`.

## Development

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m pytest
python3 -m compileall api
```

No Google credentials are required for the automated test suite; upstream HTTP is replaced with fakes at the transport boundary.
