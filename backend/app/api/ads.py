from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import desc, or_
from sqlalchemy.orm import Session

from app.api.schemas import (
    AdMetricIn,
    AdMetricOut,
    AdAutopsyOut,
    AdOut,
    GetHookdExploreIn,
    MetaAdsSearchIngest,
    MetaAdsSearchOut,
)
from app.core.config import settings
from app.db.session import get_db
from app.db import models
from app.services.gethookd import GetHookdAPIError, search_gethookd_ads
from app.services.ad_metrics import build_ad_analytics, persist_ad_metrics
from app.services.integration_config import (
    IntegrationConfigError,
    get_gethookd_credential,
    get_meta_credential,
)
from app.services.meta_ads import (
    MetaAdsAPIError,
    effective_meta_fields,
    persist_meta_ads,
    search_ads_archive,
)
from app.utils.security import get_current_user
from app.services.workspace import get_default_workspace

router = APIRouter()


def _ad_or_404(db: Session, workspace_id: int, ad_id: int) -> models.Ad:
    ad = (
        db.query(models.Ad)
        .filter(models.Ad.workspace_id == workspace_id, models.Ad.id == ad_id)
        .first()
    )
    if not ad:
        raise HTTPException(status_code=404, detail="Ad not found")
    return ad


def _autopsy_product(product: models.Product, store: models.Store) -> dict:
    return {
        "id": product.id,
        "title": product.title,
        "canonical_url": product.canonical_url,
        "currency": product.currency,
        "store_id": store.id,
        "store_domain": store.domain,
    }


def _build_ad_autopsy(db: Session, workspace_id: int, ad: models.Ad) -> dict:
    edges = (
        db.query(models.AdLandingEdge, models.SourceUrl)
        .join(models.SourceUrl, models.SourceUrl.id == models.AdLandingEdge.url_id)
        .filter(
            models.AdLandingEdge.ad_id == ad.id,
            models.SourceUrl.workspace_id == workspace_id,
        )
        .order_by(models.AdLandingEdge.id.asc())
        .all()
    )
    landing_pages = []
    products_by_id: dict[int, dict] = {}
    landing_ids: list[int] = []
    for _, source in edges:
        landing_ids.append(source.id)
        snapshot = (
            db.query(models.LandingPageSnapshot)
            .filter(models.LandingPageSnapshot.url_id == source.id)
            .order_by(models.LandingPageSnapshot.fetched_at.desc())
            .first()
        )
        product_rows = (
            db.query(models.Product, models.Store)
            .join(models.LandingProductEdge, models.LandingProductEdge.product_id == models.Product.id)
            .join(models.Store, models.Store.id == models.Product.store_id)
            .filter(
                models.LandingProductEdge.landing_url_id == source.id,
                models.Product.workspace_id == workspace_id,
                models.Store.workspace_id == workspace_id,
            )
            .order_by(models.Product.id.asc())
            .all()
        )
        linked_products = []
        for product, store in product_rows:
            item = _autopsy_product(product, store)
            products_by_id[product.id] = item
            linked_products.append(item)
        landing_pages.append(
            {
                "source_url_id": source.id,
                "url": source.url,
                "fetch_status": source.fetch_status,
                "last_http_status": source.last_http_status,
                "last_fetched_at": source.last_fetched_at,
                "final_url": snapshot.final_url if snapshot else None,
                "snapshot_fetched_at": snapshot.fetched_at if snapshot else None,
                "products": linked_products,
            }
        )

    landing_domain = None
    if ad.landing_url:
        landing_domain = (urlparse(ad.landing_url).hostname or "").lower().removeprefix("www.")
    store = None
    if products_by_id:
        first_product = next(iter(products_by_id.values()))
        store = db.query(models.Store).filter(models.Store.id == first_product["store_id"]).first()
    elif landing_domain:
        store = (
            db.query(models.Store)
            .filter(models.Store.workspace_id == workspace_id, models.Store.domain == landing_domain)
            .first()
        )

    related: dict[int, dict] = {}
    candidates = db.query(models.Ad).filter(models.Ad.workspace_id == workspace_id, models.Ad.id != ad.id)
    if landing_ids:
        for other in (
            candidates.join(models.AdLandingEdge, models.AdLandingEdge.ad_id == models.Ad.id)
            .filter(models.AdLandingEdge.url_id.in_(landing_ids))
            .all()
        ):
            related.setdefault(other.id, {"ad": other, "reasons": []})["reasons"].append("shared landing record")
    if products_by_id:
        for other in (
            candidates.join(models.AdLandingEdge, models.AdLandingEdge.ad_id == models.Ad.id)
            .join(
                models.LandingProductEdge,
                models.LandingProductEdge.landing_url_id == models.AdLandingEdge.url_id,
            )
            .filter(models.LandingProductEdge.product_id.in_(list(products_by_id)))
            .distinct()
            .all()
        ):
            related.setdefault(other.id, {"ad": other, "reasons": []})["reasons"].append(
                "same resolved product"
            )
    for other in candidates.limit(500).all():
        reasons = related.setdefault(other.id, {"ad": other, "reasons": []})["reasons"]
        if (
            ad.provider_record_id
            and other.data_provider == ad.data_provider
            and other.provider_record_id == ad.provider_record_id
        ):
            reasons.append("same provider record")
        if (
            ad.external_ad_id
            and other.platform == ad.platform
            and other.external_ad_id == ad.external_ad_id
        ):
            reasons.append("same platform ad ID")
        if ad.advertiser_id and other.advertiser_id == ad.advertiser_id:
            reasons.append("same advertiser")
        elif ad.advertiser_name and other.advertiser_name and other.advertiser_name.casefold() == ad.advertiser_name.casefold():
            reasons.append("same advertiser name")
        if landing_domain and other.landing_url:
            other_domain = (urlparse(other.landing_url).hostname or "").lower().removeprefix("www.")
            if other_domain == landing_domain:
                reasons.append("same landing domain")
    related_rows = [item for item in related.values() if item["reasons"]]
    for item in related_rows:
        item["reasons"] = list(dict.fromkeys(item["reasons"]))
    related_rows.sort(key=lambda item: item["ad"].last_seen_at, reverse=True)

    analytics = build_ad_analytics(db, ad)
    analytics["metrics"] = [
        AdMetricOut.model_validate(row).model_dump(mode="json") for row in analytics["metrics"]
    ]
    has_collected_landing = any(item["snapshot_fetched_at"] for item in landing_pages)
    if products_by_id:
        conclusion = {
            "status": "investigate",
            "label": "Product path resolved",
            "explanation": "Northstar connected this ad to at least one collected product through stored landing evidence.",
            "next_step": "Open the product or store report and validate demand, offer, and traffic evidence.",
        }
    elif has_collected_landing or analytics["metrics"]:
        conclusion = {
            "status": "weak_evidence",
            "label": "Evidence saved, product unresolved",
            "explanation": "The ad has collected evidence, but Northstar has not resolved a product from its landing path.",
            "next_step": "Investigate or rescan the landing page, then review any product association candidates.",
        }
    else:
        conclusion = {
            "status": "insufficient_data",
            "label": "Landing evidence not collected",
            "explanation": "The saved ad does not yet have enough collected landing or product evidence for an investigation conclusion.",
            "next_step": "Investigate the public landing URL to collect the store and product path.",
        }

    return {
        "ad": ad,
        "analytics": analytics,
        "creative_analysis": {
            "asset_count": len(ad.creative_urls_json or []),
            "media_state": "available" if ad.creative_urls_json else "not_saved",
            "transcript_status": "not_collected",
            "ocr_status": "not_collected",
            "notice": (
                "Northstar has not transcribed audio or extracted on-screen text from this creative. "
                "Saved media availability alone is not creative-performance evidence."
            ),
        },
        "landing_pages": landing_pages,
        "store": (
            {
                "id": store.id,
                "domain": store.domain,
                "platform": store.platform_guess.value,
                "last_seen_at": store.last_seen_at,
            }
            if store
            else None
        ),
        "products": list(products_by_id.values()),
        "related_ads": related_rows[:20],
        "conclusion": conclusion,
    }


@router.post("/gethookd/search")
def search_gethookd(
    payload: GetHookdExploreIn,
    _: models.User = Depends(get_current_user),
):
    """Search GetHookd live without persisting rows lacking provider provenance."""
    try:
        api_token, _ = get_gethookd_credential()
    except IntegrationConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if not api_token:
        raise HTTPException(status_code=409, detail="Configure a GetHookd public API token first")
    try:
        return search_gethookd_ads(
            api_token=api_token,
            query=payload.query,
            limit=payload.limit,
            page=payload.page,
            platform=payload.platform,
            status=payload.status,
            ad_format=payload.ad_format,
            minimum_days_active=payload.minimum_days_active,
            sort_column=payload.sort_column,
            sort_direction=payload.sort_direction,
        )
    except GetHookdAPIError as exc:
        status_code = 429 if exc.http_status == 429 else 502
        if exc.http_status in {401, 402, 403}:
            status_code = exc.http_status
        raise HTTPException(status_code=status_code, detail=exc.as_dict()) from exc


@router.get("", response_model=list[AdOut])
def list_ads(
    query: Optional[str] = None,
    platform: Optional[str] = None,
    provider: Optional[str] = None,
    official_only: bool = False,
    sort: Optional[str] = "newest",
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    ws = get_default_workspace(db, user.id)
    q = db.query(models.Ad).filter(models.Ad.workspace_id == ws.id)

    if platform:
        q = q.filter(models.Ad.platform == models.AdPlatform(platform))

    if provider:
        q = q.filter(models.Ad.data_provider == provider.strip())

    if official_only:
        q = q.filter(
            models.Ad.data_provider == "meta_ad_library",
            models.Ad.source_type == "official_provider_api",
        )

    if query:
        term = f"%{query.strip()}%"
        q = q.filter(
            or_(
                models.Ad.ad_text.ilike(term),
                models.Ad.headline.ilike(term),
                models.Ad.advertiser_name.ilike(term),
                models.Ad.landing_url.ilike(term),
            )
        )

    if sort == "longevity":
        q = q.order_by(desc(models.Ad.last_seen_at))
    else:
        q = q.order_by(desc(models.Ad.first_seen_at))

    return q.limit(200).all()


@router.get("/facets")
def ad_library_facets(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Return local metric/geography facets without any provider request."""
    workspace = get_default_workspace(db, user.id)
    ads = db.query(models.Ad).filter(models.Ad.workspace_id == workspace.id).all()
    ad_ids = [ad.id for ad in ads]
    metrics = db.query(models.AdMetricObservation).filter(
        models.AdMetricObservation.workspace_id == workspace.id,
        models.AdMetricObservation.ad_id.in_(ad_ids),
    ).all() if ad_ids else []
    metric_keys_by_ad: dict[str, list[str]] = {}
    geographies_by_ad: dict[str, list[str]] = {}
    for metric in metrics:
        key = str(metric.ad_id)
        metric_keys_by_ad.setdefault(key, []).append(metric.metric_key)
        if metric.geography:
            geographies_by_ad.setdefault(key, []).append(metric.geography)
    metric_keys_by_ad = {key: sorted(set(values)) for key, values in metric_keys_by_ad.items()}
    geographies_by_ad = {key: sorted(set(values)) for key, values in geographies_by_ad.items()}
    return {
        "metric_keys": sorted({metric.metric_key for metric in metrics}),
        "geographies": sorted({metric.geography for metric in metrics if metric.geography}),
        "metric_keys_by_ad": metric_keys_by_ad,
        "geographies_by_ad": geographies_by_ad,
        "data_notice": "Local saved-observation facets only; loading them does not call Meta, GetHookd, or another provider.",
    }


def _search_response(
    *,
    payload: MetaAdsSearchIngest,
    configured: bool,
    status: str,
    fetched_count: int = 0,
    inserted_count: int = 0,
    updated_count: int = 0,
    skipped_count: int = 0,
    ads: list[models.Ad] | None = None,
    error: dict | None = None,
) -> MetaAdsSearchOut:
    return MetaAdsSearchOut(
        configured=configured,
        status=status,
        graph_version=settings.meta_graph_version,
        requested_limit=payload.limit,
        fetched_count=fetched_count,
        inserted_count=inserted_count,
        updated_count=updated_count,
        skipped_count=skipped_count,
        effective_fields=effective_meta_fields(payload.fields),
        ads=ads or [],
        error=error,
    )


@router.post("/meta/search", response_model=MetaAdsSearchOut)
def search_meta_ads(
    payload: MetaAdsSearchIngest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Search Meta's official API synchronously and upsert returned public ads."""
    workspace = get_default_workspace(db, user.id)
    try:
        access_token, _ = get_meta_credential()
    except IntegrationConfigError as exc:
        response = _search_response(
            payload=payload,
            configured=False,
            status="error",
            error={"code": "META_CONFIG_ERROR", "message": str(exc)},
        )
        return JSONResponse(status_code=500, content=response.model_dump(mode="json"))

    if not access_token:
        response = _search_response(
            payload=payload,
            configured=False,
            status="not_configured",
            error={
                "code": "META_NOT_CONFIGURED",
                "message": "Configure a Meta Ad Library access token first",
            },
        )
        return JSONResponse(status_code=409, content=response.model_dump(mode="json"))

    try:
        raw_ads = search_ads_archive(
            access_token=access_token,
            ad_reached_countries=payload.ad_reached_countries,
            search_terms=payload.search_terms,
            search_page_ids=payload.search_page_ids,
            ad_type=payload.ad_type,
            ad_active_status=payload.ad_active_status,
            ad_delivery_date_min=payload.ad_delivery_date_min,
            ad_delivery_date_max=payload.ad_delivery_date_max,
            fields=payload.fields,
            limit=payload.limit,
        )
        persisted = persist_meta_ads(
            db,
            workspace_id=workspace.id,
            raw_ads=raw_ads,
        )
    except MetaAdsAPIError as exc:
        response = _search_response(
            payload=payload,
            configured=True,
            status="error",
            error=exc.as_dict(),
        )
        return JSONResponse(status_code=502, content=response.model_dump(mode="json"))

    return _search_response(
        payload=payload,
        configured=True,
        status="completed",
        fetched_count=len(raw_ads),
        inserted_count=persisted.inserted_count,
        updated_count=persisted.updated_count,
        skipped_count=persisted.skipped_count,
        ads=persisted.records,
    )


@router.get("/{ad_id}/metrics", response_model=list[AdMetricOut])
def list_ad_metrics(
    ad_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    workspace = get_default_workspace(db, user.id)
    _ad_or_404(db, workspace.id, ad_id)
    return (
        db.query(models.AdMetricObservation)
        .filter(
            models.AdMetricObservation.workspace_id == workspace.id,
            models.AdMetricObservation.ad_id == ad_id,
        )
        .order_by(models.AdMetricObservation.observed_at.desc())
        .all()
    )


@router.post("/{ad_id}/metrics", response_model=AdMetricOut)
def add_ad_metric(
    ad_id: int,
    payload: AdMetricIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    workspace = get_default_workspace(db, user.id)
    ad = _ad_or_404(db, workspace.id, ad_id)
    record = persist_ad_metrics(db, ad=ad, metrics=[payload])[0]
    db.commit()
    db.refresh(record)
    return record


@router.get("/{ad_id}/analytics")
def ad_analytics(
    ad_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    workspace = get_default_workspace(db, user.id)
    ad = _ad_or_404(db, workspace.id, ad_id)
    analytics = build_ad_analytics(db, ad)
    analytics["metrics"] = [
        AdMetricOut.model_validate(row).model_dump(mode="json")
        for row in analytics["metrics"]
    ]
    return analytics


@router.get("/{ad_id}/autopsy", response_model=AdAutopsyOut)
def ad_autopsy(
    ad_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    workspace = get_default_workspace(db, user.id)
    ad = _ad_or_404(db, workspace.id, ad_id)
    return _build_ad_autopsy(db, workspace.id, ad)


@router.get("/{ad_id}", response_model=AdOut)
def get_ad(ad_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    ws = get_default_workspace(db, user.id)
    return _ad_or_404(db, ws.id, ad_id)
