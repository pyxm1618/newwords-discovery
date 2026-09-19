from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Mapping


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    client_id: str
    client_secret: str
    refresh_token: str
    customer_id: str
    api_key: str
    api_version: str = "v24"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        source = env if env is not None else os.environ
        required = [
            "GOOGLE_ADS_CLIENT_ID",
            "GOOGLE_ADS_CLIENT_SECRET",
            "GOOGLE_ADS_REFRESH_TOKEN",
            "GOOGLE_ADS_CUSTOMER_ID",
            "SEO_DATA_API_KEY",
        ]
        values: dict[str, str] = {}
        for name in required:
            value = source.get(name, "").strip()
            if not value:
                raise ConfigError(f"missing required environment variable: {name}")
            values[name] = value

        customer_id = values["GOOGLE_ADS_CUSTOMER_ID"].replace("-", "")
        if not customer_id.isdigit():
            raise ConfigError("GOOGLE_ADS_CUSTOMER_ID must contain digits only")

        api_version = source.get("GOOGLE_ADS_API_VERSION", "v24").strip() or "v24"
        if not re.fullmatch(r"v\d+", api_version):
            raise ConfigError("GOOGLE_ADS_API_VERSION must look like v24")

        return cls(
            client_id=values["GOOGLE_ADS_CLIENT_ID"],
            client_secret=values["GOOGLE_ADS_CLIENT_SECRET"],
            refresh_token=values["GOOGLE_ADS_REFRESH_TOKEN"],
            customer_id=customer_id,
            api_key=values["SEO_DATA_API_KEY"],
            api_version=api_version,
        )


@dataclass(frozen=True)
class BigQuerySettings:
    project_id: str
    service_account_info: dict[str, Any]
    api_key: str
    location: str = "US"
    maximum_bytes_billed: int = 1_000_000_000

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "BigQuerySettings":
        source = env if env is not None else os.environ

        api_key = source.get("SEO_DATA_API_KEY", "").strip()
        if not api_key:
            raise ConfigError("missing required environment variable: SEO_DATA_API_KEY")

        raw_credentials = source.get("GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON", "").strip()
        if not raw_credentials:
            raise ConfigError(
                "missing required environment variable: GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON"
            )
        try:
            service_account_info = json.loads(raw_credentials)
        except json.JSONDecodeError as exc:
            raise ConfigError("GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON must be valid JSON") from exc
        if not isinstance(service_account_info, dict):
            raise ConfigError("GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON must be a JSON object")

        required_fields = ("client_email", "private_key", "token_uri")
        if service_account_info.get("type") != "service_account" or any(
            not service_account_info.get(field) for field in required_fields
        ):
            raise ConfigError("GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON is incomplete")

        project_id = source.get("GOOGLE_CLOUD_PROJECT", "").strip()
        if not project_id:
            project_id = str(service_account_info.get("project_id", "")).strip()
        if not project_id:
            raise ConfigError(
                "GOOGLE_CLOUD_PROJECT or service-account project_id is required"
            )

        location = source.get("BIGQUERY_LOCATION", "US").strip() or "US"

        raw_maximum = source.get(
            "BIGQUERY_MAX_BYTES_BILLED", "1000000000"
        ).strip()
        try:
            maximum_bytes_billed = int(raw_maximum)
        except ValueError as exc:
            raise ConfigError("BIGQUERY_MAX_BYTES_BILLED must be a positive integer") from exc
        if maximum_bytes_billed <= 0:
            raise ConfigError("BIGQUERY_MAX_BYTES_BILLED must be a positive integer")

        return cls(
            project_id=project_id,
            service_account_info=service_account_info,
            api_key=api_key,
            location=location,
            maximum_bytes_billed=maximum_bytes_billed,
        )
