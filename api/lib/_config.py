from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Mapping


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
