from __future__ import annotations

from typing import Any

from ._config import BigQuerySettings
from ._trends import TrendsRequest, build_trends_query


class BigQueryTimeout(RuntimeError):
    pass


class BigQueryServiceError(RuntimeError):
    pass


def _optional_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class GoogleTrendsBigQueryClient:
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

    def fetch_terms(self, request: TrendsRequest) -> dict[str, Any]:
        bigquery = self._bigquery
        parameters = [
            bigquery.ScalarQueryParameter("refresh_date", "DATE", request.refresh_date),
        ]
        if request.country_code != "US":
            parameters.append(
                bigquery.ScalarQueryParameter(
                    "country_code", "STRING", request.country_code
                )
            )

        job_config = bigquery.QueryJobConfig(query_parameters=parameters)
        job_config.maximum_bytes_billed = self.settings.maximum_bytes_billed

        try:
            job = self._client.query(
                build_trends_query(request),
                job_config=job_config,
                location=self.settings.location,
            )
            rows = list(job.result(timeout=25))
        except (TimeoutError, self._google_exceptions.DeadlineExceeded) as exc:
            raise BigQueryTimeout("BigQuery request timed out") from exc
        except self._google_exceptions.GoogleAPICallError as exc:
            raise BigQueryServiceError("BigQuery request failed") from exc
        except Exception as exc:
            raise BigQueryServiceError("BigQuery request failed") from exc

        results: list[dict[str, Any]] = []
        for row in rows:
            results.append(
                {
                    "term": row["term"],
                    "rank": _optional_int(row["rank"]),
                }
            )

        return {
            "results": results,
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
