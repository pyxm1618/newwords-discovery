from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

JSON_HEADERS = {"Content-Type": "application/json; charset=utf-8"}


def error_response(status: int, code: str, message: str):
    return status, dict(JSON_HEADERS), {"error": {"code": code, "message": message}}


def get_header(headers: Mapping[str, str], name: str) -> str | None:
    target = name.lower()
    for key, value in headers.items():
        if key.lower() == target:
            return value
    return None


def parse_json_body(body: bytes) -> Any:
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("request body must be valid JSON") from exc
