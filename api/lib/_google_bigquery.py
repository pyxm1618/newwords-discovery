from __future__ import annotations

from datetime import date
from typing import Any, Mapping, Protocol

from ._config import BigQuerySettings
from ._trends import TrendsRequest, build_trends_query


class BigQueryTimeout(RuntimeError):
    pass


class BigQueryServiceError(RuntimeError):
    pass


class BigQueryTransport(Protocol):
    def query(
        self,
        sql: str,
        *,
        parameters: Mapping[str, tuple[str, Any]],
        maximum_bytes_billed: int,
        timeout: int,
    ) -> dict[str, Any]: ...


def _optional_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class GoogleCloudBigQueryTransport:
    def __init__(self, settings: BigQuerySettings):
        self.settings = settings
        try:
            from google.api_core import exceptions as google_exceptions
            from google.cloud import bigquery
            from google.oauth2 import service_account
        except ImportError as exc:
            raise BigQueryServiceError("BigQuery runtime dependency is unavailable") from exc

        credentials = service_account.Credentials.from_service_account_info(
            settings.service_account_info,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        self._bigquery = bigquery
        self._google_exceptions = google_exceptions
        self._client = bigquery.Client(
            project=settings.project_id,
            credentials=credentials,
            location=settings.location,
        )

    def query(
        self,
        sql: str,
        *,
        parameters: Mapping[str, tuple[str, Any]],
        maximum_bytes_billed: int,
        timeout: int,
    ) -> dict[str, Any]:
        bigquery = self._bigquery
        query_parameters = []
        for name, (parameter_type, value) in parameters.items():
            if parameter_type == "DATE" and isinstance(value, str):
                value = date.fromisoformat(value)
            query_parameters.append(
                bigquery.ScalarQueryParameter(name, parameter_type, value)
            )

        job_config = bigquery.QueryJobConfig(query_parameters=query_parameters)
        job_config.maximum_bytes_billed = maximum_bytes_billed

        try:
            job = self._client.query(
                sql,
                job_config=job_config,
                location=self.settings.location,
            )
            rows = list(job.result(timeout=timeout))
        except (TimeoutError, self._google_exceptions.DeadlineExceeded) as exc:
            raise BigQueryTimeout("BigQuery request timed out") from exc
        except self._google_exceptions.GoogleAPICallError as exc:
            raise BigQueryServiceError("BigQuery request failed") from exc
        except Exception as exc:
            raise BigQueryServiceError("BigQuery request failed") from exc

        return {
            "rows": [
                {
                    "term": row["term"],
                    "rank": row["rank"],
                }
                for row in rows
            ],
            "usage": {
                "total_bytes_processed": _optional_int(
                    getattr(job, "total_bytes_processed", None)
                ),
                "total_bytes_billed": _optional_int(
                    getattr(job, "total_bytes_billed", None)
                ),
                "cache_hit": getattr(job, "cache_hit", None),
            },
        }


class GoogleTrendsBigQueryClient:
    def __init__(
        self,
        settings: BigQuerySettings,
        transport: BigQueryTransport | None = None,
    ):
        self.settings = settings
        self.transport = transport or GoogleCloudBigQueryTransport(settings)

    def fetch_terms(self, request: TrendsRequest) -> dict[str, Any]:
        parameters: dict[str, tuple[str, Any]] = {
            "refresh_date": ("DATE", request.refresh_date),
        }
        if request.country_code != "US":
            parameters["country_code"] = ("STRING", request.country_code)

        upstream = self.transport.query(
            build_trends_query(request),
            parameters=parameters,
            maximum_bytes_billed=self.settings.maximum_bytes_billed,
            timeout=25,
        )

        results: list[dict[str, Any]] = []
        for row in upstream.get("rows", []):
            results.append(
                {
                    "term": row.get("term"),
                    "rank": _optional_int(row.get("rank")),
                }
            )

        return {
            "results": results,
            "usage": upstream.get(
                "usage",
                {
                    "total_bytes_processed": None,
                    "total_bytes_billed": None,
                    "cache_hit": None,
                },
            ),
        }
