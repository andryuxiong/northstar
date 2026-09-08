"""Small, credential-safe adapter for GetHookd's documented public Explore API."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings


class GetHookdAPIError(RuntimeError):
    def __init__(self, message: str, *, http_status: int | None = None, code: str = "GETHOOKD_ERROR"):
        super().__init__(message)
        self.message = message
        self.http_status = http_status
        self.code = code

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "upstream_http_status": self.http_status}


def _clean_message(value: object, token: str) -> str:
    message = str(value or "GetHookd request failed")
    if token:
        message = message.replace(token, "[redacted]")
    return message[:500]


def _first_text(*values: object) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _normalize_media(value: object) -> tuple[list[str], str | None, str]:
    urls: list[str] = []
    thumbnail: str | None = None
    creative_type = "unknown"
    if not isinstance(value, list):
        return urls, thumbnail, creative_type
    for item in value:
        if not isinstance(item, dict):
            continue
        media_type = str(item.get("type") or "").lower()
        if creative_type == "unknown" and media_type in {"image", "video", "carousel"}:
            creative_type = media_type
        url = _first_text(item.get("url"), item.get("media_url"), item.get("src"))
        if url and url not in urls:
            urls.append(url)
        item_thumbnail = _first_text(item.get("thumbnail_url"), item.get("thumbnail"))
        if item_thumbnail and thumbnail is None:
            thumbnail = item_thumbnail
    return urls, thumbnail, creative_type


def normalize_gethookd_ad(row: dict[str, Any]) -> dict[str, Any]:
    brand = row.get("brand") if isinstance(row.get("brand"), dict) else {}
    media_urls, thumbnail_url, media_type = _normalize_media(row.get("media"))
    display_format = str(row.get("display_format") or "").lower()
    creative_type = media_type
    if creative_type == "unknown":
        if "video" in display_format:
            creative_type = "video"
        elif "image" in display_format:
            creative_type = "image"
        elif "carousel" in display_format:
            creative_type = "carousel"
    active_value = row.get("active_in_library")
    is_active = active_value is True or active_value == 1 or str(active_value).lower() in {"true", "active"}
    score = row.get("performance_score")
    try:
        score = float(score) if score is not None else None
    except (TypeError, ValueError):
        score = None
    days_active = row.get("days_active")
    try:
        days_active = int(days_active) if days_active is not None else None
    except (TypeError, ValueError):
        days_active = None
    platform = row.get("platform")
    if isinstance(platform, list):
        platforms = [str(item).strip().lower() for item in platform if str(item).strip()]
    else:
        platforms = [part.strip().lower() for part in str(platform or "").split(",") if part.strip()]
    return {
        "provider": "gethookd",
        "source": "gethookd_public_api",
        "provider_ad_id": str(row.get("id")) if row.get("id") is not None else None,
        "external_ad_id": _first_text(row.get("external_id")),
        "platforms": platforms,
        "advertiser_name": _first_text(brand.get("name"), row.get("advertiser_name")),
        "advertiser_id": _first_text(brand.get("external_id"), row.get("advertiser_id")),
        "advertiser_logo_url": _first_text(brand.get("logo_url")),
        "headline": _first_text(row.get("title"), row.get("headline")),
        "ad_text": _first_text(row.get("body"), row.get("ad_text")),
        "cta": _first_text(row.get("cta_text"), row.get("cta_type")),
        "creative_type": creative_type,
        "creative_urls": media_urls,
        "thumbnail_url": thumbnail_url,
        "landing_url": _first_text(row.get("landing_page"), row.get("landing_url")),
        "provider_url": _first_text(row.get("share_url")),
        "delivery_start_time": row.get("start_date"),
        "delivery_stop_time": row.get("end_date"),
        "days_active": days_active,
        "is_active": is_active,
        "provider_score": score,
        "provider_classification": _first_text(row.get("performance_score_title")),
        "used_count": row.get("used_count"),
    }


def search_gethookd_ads(
    *,
    api_token: str,
    query: str,
    limit: int = 20,
    page: int = 1,
    platform: str | None = None,
    status: str | None = None,
    ad_format: str | None = None,
    minimum_days_active: int | None = None,
    sort_column: str = "days_active",
    sort_direction: str = "desc",
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "query": query,
        "page": page,
        "per_page": limit,
        "sort_column": sort_column,
        "sort_direction": sort_direction,
    }
    if platform:
        params["platform"] = platform
    if status:
        params["status"] = status
    if ad_format:
        params["ad-format"] = ad_format
    if minimum_days_active is not None:
        params["run-time"] = minimum_days_active

    owns_client = client is None
    active_client = client or httpx.Client(base_url=settings.gethookd_api_base_url, timeout=25.0)
    try:
        response = active_client.get(
            f"{settings.gethookd_api_base_url.rstrip('/')}/explore",
            params=params,
            headers={"Authorization": f"Bearer {api_token}", "Accept": "application/json"},
        )
    except httpx.RequestError as exc:
        raise GetHookdAPIError("Could not reach GetHookd", code="GETHOOKD_NETWORK_ERROR") from exc
    finally:
        if owns_client:
            active_client.close()

    try:
        payload = response.json()
    except ValueError:
        payload = {}
    if response.status_code >= 400:
        message = payload.get("message") if isinstance(payload, dict) else None
        codes = {
            401: "GETHOOKD_AUTH_ERROR",
            402: "GETHOOKD_CREDITS_EXHAUSTED",
            403: "GETHOOKD_SCOPE_ERROR",
            429: "GETHOOKD_RATE_LIMITED",
        }
        raise GetHookdAPIError(
            _clean_message(message or f"GetHookd returned HTTP {response.status_code}", api_token),
            http_status=response.status_code,
            code=codes.get(response.status_code, "GETHOOKD_UPSTREAM_ERROR"),
        )
    if not isinstance(payload, dict) or payload.get("errors") is True:
        message = payload.get("message") if isinstance(payload, dict) else None
        raise GetHookdAPIError(_clean_message(message, api_token))
    rows = payload.get("data")
    if not isinstance(rows, list):
        rows = []
    normalized = [normalize_gethookd_ad(row) for row in rows if isinstance(row, dict)]
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    return {
        "provider": "gethookd",
        "source": "gethookd_public_api",
        "status": "completed",
        "query": query,
        "result_count": meta.get("result_count", len(normalized)),
        "used_credits": payload.get("used_credits"),
        "remaining_credits": payload.get("remaining_credits"),
        "ads": normalized,
        "data_notice": (
            "Provider scores, classifications, duration, and activity are research signals; "
            "they do not establish competitor spend, conversions, ROAS, or profit."
        ),
    }
