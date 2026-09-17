from __future__ import annotations

import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Mapping, Protocol

from ._config import Settings
from ._keyword_volume import KeywordVolumeRequest

TOKEN_URL = "https://oauth2.googleapis.com/token"


class UpstreamTimeout(RuntimeError):
    pass


class UpstreamServiceError(RuntimeError):
    def __init__(self, message: str, upstream_status: int | None = None):
        super().__init__(message)
        self.upstream_status = upstream_status


class GoogleOAuthError(UpstreamServiceError):
    pass


class GoogleAdsUpstreamError(UpstreamServiceError):
    pass


class UpstreamNetworkError(UpstreamServiceError):
    pass


class HttpTransport(Protocol):
    def post_form(
        self,
        url: str,
        *,
        data: Mapping[str, str],
        headers: Mapping[str, str] | None = None,
        timeout: int = 15,
    ) -> tuple[int, dict[str, Any]]: ...

    def post_json(
        self,
        url: str,
        *,
        json_body: Mapping[str, Any],
        headers: Mapping[str, str] | None = None,
        timeout: int = 30,
    ) -> tuple[int, dict[str, Any]]: ...


class UrllibTransport:
    def _request(
        self,
        url: str,
        *,
        body: bytes,
        headers: Mapping[str, str],
        timeout: int,
    ) -> tuple[int, dict[str, Any]]:
        request = urllib.request.Request(
            url,
            data=body,
            headers=dict(headers),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = response.read()
                return response.status, self._decode_json(payload)
        except urllib.error.HTTPError as exc:
            return exc.code, self._decode_json(exc.read())
        except (TimeoutError, socket.timeout) as exc:
            raise UpstreamTimeout("upstream request timed out") from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                raise UpstreamTimeout("upstream request timed out") from exc
            raise UpstreamNetworkError("upstream network request failed") from exc

    @staticmethod
    def _decode_json(payload: bytes) -> dict[str, Any]:
        if not payload:
            return {}
        try:
            data = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def post_form(
        self,
        url: str,
        *,
        data: Mapping[str, str],
        headers: Mapping[str, str] | None = None,
        timeout: int = 15,
    ) -> tuple[int, dict[str, Any]]:
        request_headers = {"Content-Type": "application/x-www-form-urlencoded"}
        request_headers.update(headers or {})
        body = urllib.parse.urlencode(data).encode("utf-8")
        return self._request(url, body=body, headers=request_headers, timeout=timeout)

    def post_json(
        self,
        url: str,
        *,
        json_body: Mapping[str, Any],
        headers: Mapping[str, str] | None = None,
        timeout: int = 30,
    ) -> tuple[int, dict[str, Any]]:
        request_headers = {"Content-Type": "application/json"}
        request_headers.update(headers or {})
        body = json.dumps(json_body, separators=(",", ":")).encode("utf-8")
        return self._request(url, body=body, headers=request_headers, timeout=timeout)


class GoogleAdsClient:
    def __init__(self, settings: Settings, transport: HttpTransport | None = None):
        self.settings = settings
        self.transport = transport or UrllibTransport()

    def _access_token(self) -> str:
        status, payload = self.transport.post_form(
            TOKEN_URL,
            data={
                "client_id": self.settings.client_id,
                "client_secret": self.settings.client_secret,
                "refresh_token": self.settings.refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=15,
        )
        access_token = payload.get("access_token") if isinstance(payload, dict) else None
        if not (200 <= status < 300) or not isinstance(access_token, str) or not access_token:
            raise GoogleOAuthError("Google OAuth token exchange failed", status)
        return access_token

    def generate_historical_metrics(self, request: KeywordVolumeRequest) -> dict[str, Any]:
        access_token = self._access_token()
        url = (
            f"https://googleads.googleapis.com/{self.settings.api_version}/customers/"
            f"{self.settings.customer_id}:generateKeywordHistoricalMetrics"
        )
        body = {
            "keywords": list(request.keywords),
            "geoTargetConstants": [f"geoTargetConstants/{request.geo_target_constant}"],
            "language": f"languageConstants/{request.language_constant}",
            "keywordPlanNetwork": request.network,
        }
        status, payload = self.transport.post_json(
            url,
            json_body=body,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30,
        )
        if not 200 <= status < 300:
            raise GoogleAdsUpstreamError("Google Ads request failed", status)
        if not isinstance(payload, dict):
            raise GoogleAdsUpstreamError("Google Ads returned an invalid response", status)
        return payload
