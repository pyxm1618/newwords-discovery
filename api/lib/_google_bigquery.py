from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
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


def _json_scalar(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    return value


def _optional_int(value: Any) -> int | None:
    value = _json_scalar(value)
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_number(value: Any) -> int | float | None:
    value = _json_scalar(value)
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    try:
        parsed = Decimal(str(value))
    except Exception:
        return None
    if parsed == parsed.to_integral_value():
        return int(parsed)
    return float(parsed)


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
                    key: _json_scalar(value)
                    for key, value in row.items()
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

        grouped: dict[str, dict[str, Any]] = {}
        aggregation_modes: set[str] = set()

        for row in upstream.get("rows", []):
            term_value = row.get("term")
            if term_value is None:
                continue
            term = str(term_value)

            rank_value_count = _optional_int(row.get("rank_value_count"))
            if rank_value_count is not None and rank_value_count > 1:
                raise BigQueryServiceError(
                    "BigQuery returned inconsistent rank values for one term"
                )

            percent_gain_value_count = _optional_int(
                row.get("percent_gain_value_count")
            )
            if (
                request.kind == "rising"
                and percent_gain_value_count is not None
                and percent_gain_value_count > 1
            ):
                raise BigQueryServiceError(
                    "BigQuery returned inconsistent percent_gain values for one term"
                )

            item = grouped.get(term)
            if item is None:
                item = {
                    "term": term,
                    "rank": _optional_int(row.get("rank")),
                    "percent_gain": _optional_number(row.get("percent_gain")),
                    "history": [],
                }
                grouped[term] = item
            else:
                row_rank = _optional_int(row.get("rank"))
                if item["rank"] != row_rank:
                    raise BigQueryServiceError(
                        "BigQuery returned inconsistent rank values for one term"
                    )
                row_percent_gain = _optional_number(row.get("percent_gain"))
                if item["percent_gain"] != row_percent_gain:
                    raise BigQueryServiceError(
                        "BigQuery returned inconsistent percent_gain values for one term"
                    )

            week = _json_scalar(row.get("week"))
            score = _optional_number(row.get("score"))
            region_count = _optional_int(row.get("region_count"))
            item["history"].append(
                {
                    "week": week,
                    "score": score,
                    "region_count": region_count,
                }
            )

            aggregation = row.get("score_aggregation")
            if aggregation:
                aggregation_modes.add(str(aggregation))

        results = list(grouped.values())
        for item in results:
            item["history"].sort(
                key=lambda point: (
                    point["week"] is None,
                    point["week"] or "",
                )
            )

        results.sort(
            key=lambda item: (
                item["rank"] is None,
                item["rank"] if item["rank"] is not None else 0,
                item["term"],
            )
        )

        if not aggregation_modes:
            score_aggregation = None
        elif len(aggregation_modes) == 1:
            score_aggregation = next(iter(aggregation_modes))
        else:
            score_aggregation = "varies_by_week"

        return {
            "history": {
                "score_aggregation": score_aggregation,
            },
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
