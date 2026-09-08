"""Official Meta Ad Library API client and local persistence helpers.

This module intentionally uses only the documented Graph API.  It does not
scrape the Ad Library website and it does not invent reach, spend, or traffic
metrics that Meta did not return.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re
import time
from typing import Any, Iterable, Mapping, Optional, Sequence
from urllib.parse import parse_qsl, quote, urlencode, urlparse, urlsplit, urlunsplit

import httpx
from dateutil.parser import isoparse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import models


# These fields are available for ordinary commercial-ad searches and contain
# the useful public facts needed by the local library.  Fields such as spend,
# impressions, and demographics are deliberately not requested by default:
# Meta only exposes them for certain regulated/political ad categories.
DEFAULT_META_AD_FIELDS: tuple[str, ...] = (
    "id",
    "ad_creation_time",
    "ad_creative_bodies",
    "ad_creative_link_captions",
    "ad_creative_link_descriptions",
    "ad_creative_link_titles",
    "ad_delivery_start_time",
    "ad_delivery_stop_time",
    "ad_snapshot_url",
    "page_id",
    "page_name",
    "publisher_platforms",
)

MAX_META_AD_RESULTS = 500
META_PAGE_SIZE = 100


class MetaAdsAPIError(RuntimeError):
    """A safe, structured error returned by the official Meta Graph API."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "META_API_ERROR",
        http_status: int | None = None,
        provider_code: int | str | None = None,
        provider_subcode: int | str | None = None,
        provider_type: str | None = None,
        trace_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.http_status = http_status
        self.provider_code = provider_code
        self.provider_subcode = provider_subcode
        self.provider_type = provider_type
        self.trace_id = trace_id

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": str(self),
            "upstream_http_status": self.http_status,
            "provider_code": self.provider_code,
            "provider_subcode": self.provider_subcode,
            "provider_type": self.provider_type,
            "trace_id": self.trace_id,
        }


@dataclass(frozen=True)
class ParsedMetaAd:
    external_ad_id: str
    advertiser_name: str | None
    advertiser_id: str | None
    ad_text: str | None
    headline: str | None
    cta: str | None
    ad_creation_time: datetime | None
    delivery_start_time: datetime | None
    delivery_stop_time: datetime | None
    ad_snapshot_url: str | None
    publisher_platforms: list[str] | None
    creative_urls: list[str] | None
    landing_url: str | None


@dataclass
class MetaAdsPersistResult:
    records: list[models.Ad]
    inserted_count: int
    updated_count: int
    skipped_count: int


def effective_meta_fields(fields: str | Sequence[str] | None = None) -> list[str]:
    """Return the stable default field set plus any explicitly requested fields."""

    requested: list[str] = []
    if isinstance(fields, str):
        requested = [part.strip() for part in fields.split(",") if part.strip()]
    elif fields:
        requested = [str(part).strip() for part in fields if str(part).strip()]

    result: list[str] = []
    for field in (*DEFAULT_META_AD_FIELDS, *requested):
        if field not in result:
            result.append(field)
    return result


def _provider_error(response: httpx.Response, access_token: str) -> MetaAdsAPIError:
    error: Mapping[str, Any] = {}
    try:
        payload = response.json()
        if isinstance(payload, Mapping) and isinstance(payload.get("error"), Mapping):
            error = payload["error"]
    except (ValueError, TypeError):
        pass

    message = str(error.get("message") or "Meta Ad Library returned an error")
    # A proxy/provider message can contain the original request URL. Never let
    # the access token escape through a job error or API response.
    message = message.replace(access_token, "[redacted]")
    message = message.replace(quote(access_token, safe=""), "[redacted]")
    message = re.sub(r"(?i)(access_token=)[^&\s\"']+", r"\1[redacted]", message)[:500]
    return MetaAdsAPIError(
        message,
        http_status=response.status_code,
        provider_code=error.get("code"),
        provider_subcode=error.get("error_subcode"),
        provider_type=str(error.get("type")) if error.get("type") else None,
        trace_id=str(error.get("fbtrace_id")) if error.get("fbtrace_id") else None,
    )


def search_ads_archive(
    *,
    access_token: str,
    ad_reached_countries: list[str],
    search_terms: Optional[str] = None,
    search_page_ids: Optional[list[str]] = None,
    ad_type: str = "ALL",
    ad_active_status: Optional[str] = None,
    ad_delivery_date_min: Optional[str] = None,
    ad_delivery_date_max: Optional[str] = None,
    fields: str | Sequence[str] | None = None,
    limit: int = 50,
    client: httpx.Client | None = None,
) -> list[dict[str, Any]]:
    """Fetch at most ``limit`` records from Meta's official ads_archive edge.

    Pagination uses Meta's cursor while rebuilding each request against the
    configured Graph host.  This avoids following arbitrary paging URLs and
    guarantees that a provider page cannot make the result exceed the caller's
    requested bound.
    """

    token = (access_token or "").strip()
    if not token:
        raise MetaAdsAPIError(
            "A Meta Ad Library access token has not been configured",
            code="META_NOT_CONFIGURED",
        )
    if not ad_reached_countries:
        raise ValueError("ad_reached_countries must contain at least one country code")

    requested_limit = max(1, min(int(limit), MAX_META_AD_RESULTS))
    base_url = f"https://graph.facebook.com/{settings.meta_graph_version}/ads_archive"
    params: dict[str, Any] = {
        "access_token": token,
        "ad_reached_countries": json.dumps(ad_reached_countries),
        "ad_type": ad_type,
        "fields": ",".join(effective_meta_fields(fields)),
    }
    if search_terms:
        params["search_terms"] = search_terms
    if search_page_ids:
        params["search_page_ids"] = json.dumps(search_page_ids)
    if ad_active_status:
        params["ad_active_status"] = ad_active_status
    if ad_delivery_date_min:
        params["ad_delivery_date_min"] = ad_delivery_date_min
    if ad_delivery_date_max:
        params["ad_delivery_date_max"] = ad_delivery_date_max

    ads: list[dict[str, Any]] = []
    after: str | None = None
    seen_cursors: set[str] = set()
    owns_client = client is None
    active_client = client or httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0))

    try:
        while len(ads) < requested_limit:
            remaining = requested_limit - len(ads)
            page_params = dict(params)
            page_params["limit"] = min(META_PAGE_SIZE, remaining)
            if after:
                page_params["after"] = after

            response = None
            last_error: httpx.RequestError | None = None
            for attempt in range(3):
                try:
                    response = active_client.get(base_url, params=page_params)
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
                raise MetaAdsAPIError(
                    f"Could not reach the Meta Ad Library API: {last_error.__class__.__name__ if last_error else 'network error'}",
                    code="META_NETWORK_ERROR",
                ) from last_error

            if not response.is_success:
                raise _provider_error(response, token)
            try:
                payload = response.json()
            except ValueError as exc:
                raise MetaAdsAPIError(
                    "Meta Ad Library returned an unreadable response",
                    code="META_INVALID_RESPONSE",
                    http_status=response.status_code,
                ) from exc
            if not isinstance(payload, Mapping) or not isinstance(payload.get("data", []), list):
                raise MetaAdsAPIError(
                    "Meta Ad Library returned an unexpected response shape",
                    code="META_INVALID_RESPONSE",
                    http_status=response.status_code,
                )

            data = [item for item in payload.get("data", []) if isinstance(item, dict)]
            ads.extend(data[:remaining])
            paging = payload.get("paging") if isinstance(payload.get("paging"), Mapping) else {}
            cursors = paging.get("cursors") if isinstance(paging.get("cursors"), Mapping) else {}
            next_after = cursors.get("after")
            if not data or not next_after:
                break
            next_after = str(next_after)
            if next_after in seen_cursors:
                break
            seen_cursors.add(next_after)
            after = next_after
    finally:
        if owns_client:
            active_client.close()

    return ads


def _strings(value: Any, keys: Sequence[str] = ("text", "title", "body", "value")) -> list[str]:
    """Safely flatten Meta fields returned as strings, lists, or old dict forms."""

    values: list[str] = []
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned:
            values.append(cleaned)
    elif isinstance(value, Mapping):
        matched = False
        for key in keys:
            if key in value:
                matched = True
                values.extend(_strings(value.get(key), keys))
        if not matched:
            for nested in value.values():
                if isinstance(nested, (str, list, tuple, dict)):
                    values.extend(_strings(nested, keys))
    elif isinstance(value, (list, tuple)):
        for item in value:
            values.extend(_strings(item, keys))

    unique: list[str] = []
    for item in values:
        if item not in unique:
            unique.append(item)
    return unique


def _valid_http_url(value: str | None) -> str | None:
    if not value:
        return None
    candidate = value.strip()
    parsed = urlparse(candidate)
    if parsed.scheme in {"http", "https"} and parsed.hostname:
        # Meta may place caller credentials in provider URLs. Remove known
        # Graph secrets from every URL before it reaches storage or an API
        # response, not only from the snapshot field.
        split = urlsplit(candidate)
        safe_query = urlencode(
            [
                (key, item)
                for key, item in parse_qsl(split.query, keep_blank_values=True)
                if key.lower() not in {"access_token", "appsecret_proof"}
            ],
            doseq=True,
        )
        return urlunsplit((split.scheme, split.netloc, split.path, safe_query, split.fragment))
    return None


def _urls(value: Any) -> list[str]:
    candidates = _strings(
        value,
        keys=("website_url", "url", "link", "href", "src", "image_url", "video_url"),
    )
    result: list[str] = []
    for candidate in candidates:
        url = _valid_http_url(candidate)
        if url and url not in result:
            result.append(url)
    return result


def _datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = isoparse(str(value))
    except (TypeError, ValueError, OverflowError):
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _publisher_platforms(value: Any) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("["):
            try:
                value = json.loads(stripped)
            except ValueError:
                value = stripped
    platforms = _strings(value, keys=("platform", "name", "value"))
    normalized: list[str] = []
    for platform in platforms:
        item = platform.strip().lower()
        if item and item not in normalized:
            normalized.append(item)
    return normalized


def parse_meta_ad(raw: Mapping[str, Any]) -> ParsedMetaAd | None:
    external_id = str(raw.get("id") or "").strip()
    if not external_id:
        return None

    bodies = _strings(raw.get("ad_creative_bodies"))
    titles = _strings(raw.get("ad_creative_link_titles"))
    calls_to_action = _strings(
        raw.get("ad_creative_link_call_to_actions"),
        keys=("type", "text", "value"),
    )
    landing_urls = _urls(raw.get("ad_creative_link_urls"))
    creative_urls: list[str] = []
    for field in ("ad_creative_image_urls", "ad_creative_video_urls", "creative_urls"):
        for url in _urls(raw.get(field)):
            if url not in creative_urls:
                creative_urls.append(url)

    page_name = str(raw.get("page_name") or "").strip() or None
    page_id = str(raw.get("page_id") or "").strip() or None
    provider_snapshot_url = _valid_http_url(str(raw.get("ad_snapshot_url") or "").strip())
    # Graph snapshot URLs can embed the caller's access token. Store a stable,
    # public Ad Library permalink instead; never persist or return that token.
    snapshot_url = (
        f"https://www.facebook.com/ads/library/?id={quote(external_id, safe='')}"
        if provider_snapshot_url
        else None
    )
    return ParsedMetaAd(
        external_ad_id=external_id,
        advertiser_name=page_name,
        advertiser_id=page_id,
        ad_text="\n\n".join(bodies) or None,
        headline=titles[0] if titles else None,
        cta=calls_to_action[0] if calls_to_action else None,
        ad_creation_time=_datetime(raw.get("ad_creation_time")),
        delivery_start_time=_datetime(raw.get("ad_delivery_start_time")),
        delivery_stop_time=_datetime(raw.get("ad_delivery_stop_time")),
        ad_snapshot_url=snapshot_url,
        publisher_platforms=_publisher_platforms(raw.get("publisher_platforms")),
        creative_urls=creative_urls or None,
        landing_url=landing_urls[0] if landing_urls else None,
    )


def _set_when_present(record: models.Ad, attribute: str, value: Any) -> None:
    if value is not None:
        setattr(record, attribute, value)


def persist_meta_ads(
    db: Session,
    *,
    workspace_id: int,
    raw_ads: Iterable[Mapping[str, Any]],
    observed_at: datetime | None = None,
) -> MetaAdsPersistResult:
    """Upsert Meta records by workspace/platform/external ID."""

    observed_at = observed_at or datetime.utcnow()
    parsed_by_id: dict[str, ParsedMetaAd] = {}
    skipped_count = 0
    for raw in raw_ads:
        parsed = parse_meta_ad(raw)
        if parsed is None:
            skipped_count += 1
            continue
        parsed_by_id[parsed.external_ad_id] = parsed

    external_ids = list(parsed_by_id)
    existing_rows = []
    if external_ids:
        existing_rows = (
            db.query(models.Ad)
            .filter(
                models.Ad.workspace_id == workspace_id,
                models.Ad.platform == models.AdPlatform.meta,
                models.Ad.external_ad_id.in_(external_ids),
            )
            .all()
        )
    existing_by_id = {row.external_ad_id: row for row in existing_rows}

    records: list[models.Ad] = []
    inserted_count = 0
    updated_count = 0
    for external_id, parsed in parsed_by_id.items():
        record = existing_by_id.get(external_id)
        if record is None:
            record = models.Ad(
                workspace_id=workspace_id,
                external_ad_id=external_id,
                data_provider="meta_ad_library",
                source_type="official_provider_api",
                provider_record_id=external_id,
                platform=models.AdPlatform.meta,
                first_seen_at=observed_at,
                last_seen_at=observed_at,
                creative_type=models.CreativeType.unknown,
            )
            db.add(record)
            inserted_count += 1
        else:
            record.last_seen_at = observed_at
            updated_count += 1

        record.data_provider = "meta_ad_library"
        record.source_type = "official_provider_api"
        record.provider_record_id = external_id

        _set_when_present(record, "advertiser_name", parsed.advertiser_name)
        _set_when_present(record, "advertiser_id", parsed.advertiser_id)
        _set_when_present(record, "ad_text", parsed.ad_text)
        _set_when_present(record, "headline", parsed.headline)
        _set_when_present(record, "cta", parsed.cta)
        _set_when_present(record, "ad_creation_time", parsed.ad_creation_time)
        _set_when_present(record, "delivery_start_time", parsed.delivery_start_time)
        _set_when_present(record, "delivery_stop_time", parsed.delivery_stop_time)
        _set_when_present(record, "ad_snapshot_url", parsed.ad_snapshot_url)
        _set_when_present(record, "source_url", parsed.ad_snapshot_url)
        _set_when_present(record, "publisher_platforms_json", parsed.publisher_platforms)
        _set_when_present(record, "creative_urls_json", parsed.creative_urls)
        _set_when_present(record, "landing_url", parsed.landing_url)
        records.append(record)

    db.commit()
    for record in records:
        db.refresh(record)
    return MetaAdsPersistResult(
        records=records,
        inserted_count=inserted_count,
        updated_count=updated_count,
        skipped_count=skipped_count,
    )
