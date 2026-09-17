from __future__ import annotations

import hmac


def is_authorized(authorization_header: str | None, expected_api_key: str) -> bool:
    if not authorization_header or not expected_api_key:
        return False
    scheme, sep, token = authorization_header.partition(" ")
    if not sep or scheme.lower() != "bearer" or not token:
        return False
    return hmac.compare_digest(token, expected_api_key)
