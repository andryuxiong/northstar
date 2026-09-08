from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import time
from typing import Any
from urllib.parse import quote, urlparse

import httpx

from app.core.config import settings
from app.utils.urls import normalize_public_url


class SimilarwebConfigurationError(RuntimeError):
    pass


@dataclass
class MetricResult:
    status: str
    value: float | int | None
    series: list[dict[str, Any]]
    last_updated: str | None = None
    message: str | None = None
    http_status: int | None = None
    provider_code: str | int | None = None
    retryable: bool = False

    @property
    def available(self) -> bool:
        return self.status == "success"

    def status_payload(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "available": self.available,
            "message": self.message,
            "http_status": self.http_status,
            "provider_code": self.provider_code,
            "retryable": self.retryable,
        }


def normalize_domain(value: str) -> str:
    normalized = normalize_public_url(value)
    hostname = urlparse(normalized).hostname
    if not hostname:
        raise ValueError("A public domain is required")
    hostname = hostname.lower().rstrip(".")
    if hostname.startswith("www."):
        hostname = hostname[4:]
    return hostname


def default_month() -> str:
    first_of_this_month = datetime.utcnow().date().replace(day=1)
    previous_month = first_of_this_month - timedelta(days=1)
    return previous_month.strftime("%Y-%m")


def _number(value: Any, *, integer: bool) -> float | int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return None
    if converted < 0:
        return None
    return int(converted) if integer else converted


def _series(payload: dict[str, Any], key: str, *, integer: bool) -> list[dict[str, Any]]:
    rows = payload.get(key)
    if not isinstance(rows, list):
        return []
    parsed: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        value = _number(row.get(key), integer=integer)
        date = row.get("date")
        if value is None or not isinstance(date, str):
            continue
        parsed.append({"date": date, key: value})
    return sorted(parsed, key=lambda item: item["date"])


def _provider_last_updated(payload: dict[str, Any]) -> str | None:
    meta = payload.get("meta")
    if isinstance(meta, dict):
        value = meta.get("last_updated")
        if isinstance(value, str):
            return value
    return None


def _error_details(response: httpx.Response, api_key: str) -> tuple[str | int | None, str | None]:
    code: str | int | None = None
    message: str | None = None
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if isinstance(payload, dict):
        for candidate in ("error_code", "code", "status"):
            if payload.get(candidate) is not None:
                code = payload[candidate]
                break
        error = payload.get("error")
        if isinstance(error, dict):
            code = error.get("code", code)
            raw_message = error.get("message")
            if isinstance(raw_message, str):
                message = raw_message
        elif isinstance(error, str):
            message = error
        if not message:
            for candidate in ("message", "detail", "description"):
                if isinstance(payload.get(candidate), str):
                    message = payload[candidate]
                    break
    elif isinstance(payload, str):
        message = payload
    if message:
        # Never echo a credential if a provider/proxy includes the request URL.
        message = message.replace(api_key, "[redacted]")[:500]
    return code, message


def _failure_result(response: httpx.Response, api_key: str) -> MetricResult:
    code, provider_message = _error_details(response, api_key)
    code_text = str(code) if code is not None else ""
    if response.status_code == 403:
        status = "access_or_credits"
        message = "The API key is invalid, inactive, out of credits, or this metric is not in the Similarweb plan."
    elif response.status_code == 429:
        status = "rate_limited"
        message = "Similarweb rate-limited the request. Try again later."
    elif response.status_code in {401, 404}:
        status = "data_not_found_or_unauthorized"
        message = "Similarweb returned no data for this domain, or the API key is not authorized."
    elif code_text == "101":
        status = "date_not_available"
        message = "The requested date range is outside this Similarweb plan's available history."
    elif code_text == "102":
        status = "granularity_not_available"
        message = "Monthly data is not available for this metric on the current Similarweb plan."
    elif code_text == "103":
        status = "country_not_available"
        message = "The selected country is not included in the current Similarweb plan."
    elif response.status_code >= 500:
        status = "provider_error"
        message = "Similarweb is temporarily unavailable."
    else:
        status = "request_rejected"
        message = "Similarweb rejected the metric request."
    if provider_message:
        message = f"{message} Provider detail: {provider_message}"
    return MetricResult(
        status=status,
        value=None,
        series=[],
        message=message,
        http_status=response.status_code,
        provider_code=code,
        retryable=response.status_code == 429 or response.status_code >= 500,
    )


class SimilarwebClient:
    """Small REST client for two paid Similarweb metrics.

    A one-month refresh normally requests two results/credits: global rank and
    worldwide visits. Similarweb ultimately controls entitlements and billing.
    """

    def __init__(self, api_key: str, *, client: httpx.Client | None = None):
        api_key = api_key.strip()
        if not api_key:
            raise SimilarwebConfigurationError("Configure a Similarweb REST API key first")
        self.api_key = api_key
        self._owns_client = client is None
        self.client = client or httpx.Client(timeout=30, follow_redirects=False)

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> SimilarwebClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _get_metric(
        self,
        *,
        domain: str,
        path: str,
        key: str,
        params: dict[str, Any],
        integer: bool,
    ) -> MetricResult:
        base_url = settings.similarweb_api_base_url.rstrip("/")
        url = f"{base_url}/v1/website/{quote(domain, safe='')}/{path}"
        request_params = {"api_key": self.api_key, "format": "json", **params}
        response = None
        last_error: httpx.RequestError | None = None
        for attempt in range(3):
            try:
                response = self.client.get(url, params=request_params)
                last_error = None
            except httpx.RequestError as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(0.5 * (2**attempt))
                    continue
                break
            if response.status_code != 429 and response.status_code < 500:
                break
            if attempt < 2:
                retry_after = response.headers.get("retry-after")
                try:
                    delay = min(5.0, max(0.0, float(retry_after))) if retry_after else 0.5 * (2**attempt)
                except ValueError:
                    delay = 0.5 * (2**attempt)
                time.sleep(delay)
        if response is None:
            return MetricResult(
                status="network_error",
                value=None,
                series=[],
                message=f"Could not reach Similarweb: {type(last_error).__name__ if last_error else 'network error'}",
                retryable=True,
            )
        if not response.is_success:
            return _failure_result(response, self.api_key)
        try:
            payload = response.json()
        except ValueError:
            return MetricResult(
                status="invalid_response",
                value=None,
                series=[],
                message="Similarweb returned a non-JSON response.",
                http_status=response.status_code,
            )
        if not isinstance(payload, dict):
            return MetricResult(
                status="invalid_response",
                value=None,
                series=[],
                message="Similarweb returned an unexpected response shape.",
                http_status=response.status_code,
            )
        values = _series(payload, key, integer=integer)
        if not values:
            return MetricResult(
                status="no_data",
                value=None,
                series=[],
                last_updated=_provider_last_updated(payload),
                message="Similarweb returned no values for this metric and period.",
                http_status=response.status_code,
            )
        return MetricResult(
            status="success",
            value=values[-1][key],
            series=values,
            last_updated=_provider_last_updated(payload),
            http_status=response.status_code,
        )

    def fetch(
        self,
        *,
        domain: str,
        start_date: str,
        end_date: str,
        country: str = "world",
        main_domain_only: bool = True,
    ) -> dict[str, Any]:
        domain = normalize_domain(domain)
        common = {
            "start_date": start_date,
            "end_date": end_date,
            "main_domain_only": str(main_domain_only).lower(),
        }
        rank = self._get_metric(
            domain=domain,
            path="global-rank/global-rank",
            key="global_rank",
            params=common,
            integer=True,
        )
        visits = self._get_metric(
            domain=domain,
            path="total-traffic-and-engagement/visits",
            key="visits",
            params={**common, "country": country, "granularity": "monthly"},
            integer=False,
        )
        successes = sum((rank.available, visits.available))
        fetch_status = "success" if successes == 2 else "partial" if successes == 1 else "unavailable"
        updated_candidates = [value for value in (rank.last_updated, visits.last_updated) if value]
        return {
            "domain": domain,
            "provider": "similarweb",
            "data_kind": "estimated",
            "fetch_status": fetch_status,
            "period_start": start_date,
            "period_end": end_date,
            "country": country,
            "granularity": "monthly",
            "main_domain_only": main_domain_only,
            "total_visits": visits.value,
            "global_rank": rank.value,
            "visits_series": visits.series,
            "global_rank_series": rank.series,
            "metric_status": {
                "total_visits": visits.status_payload(),
                "global_rank": rank.status_payload(),
            },
            "provider_last_updated": max(updated_candidates) if updated_candidates else None,
        }
