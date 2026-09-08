from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
from sqlalchemy.orm import Session

from app.api.schemas import AdIngest, AdOut, MetaAdsSearchIngest, StoreIngest, UrlIngest
from app.db.session import get_db
from app.db import models
from app.utils.security import get_current_user
from app.services.classifier import classify_url, extract_domain
from app.services.ad_metrics import persist_ad_metrics
from app.services.integration_config import IntegrationConfigError, get_meta_credential
from app.services.workspace import get_default_workspace
from app.workers.tasks import fetch_url_task, crawl_store_sitemap_task, meta_ads_search_task
from app.workers.runner import enqueue, get_job

router = APIRouter()


@router.post("/url")
def ingest_url(payload: UrlIngest, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    ws = get_default_workspace(db, user.id)
    url_type = classify_url(payload.url)

    existing = (
        db.query(models.SourceUrl)
        .filter(models.SourceUrl.workspace_id == ws.id, models.SourceUrl.url == payload.url)
        .first()
    )
    if existing:
        existing.fetch_status = "queued"
        db.commit()
        if existing.type == models.SourceUrlType.store:
            domain = extract_domain(existing.url)
            store = db.query(models.Store).filter(models.Store.workspace_id == ws.id, models.Store.domain == domain).first()
            if not store:
                store = models.Store(workspace_id=ws.id, domain=domain, platform_guess=models.PlatformGuess.unknown)
                db.add(store)
                db.commit()
                db.refresh(store)
            job_id = enqueue(crawl_store_sitemap_task, store.id, label=f"Rescan store {domain}")
        else:
            job_id = enqueue(fetch_url_task, existing.id, label=f"Rescan {existing.url}")
        return {
            "id": existing.id,
            "store_id": store.id if existing.type == models.SourceUrlType.store else None,
            "type": existing.type,
            "job_id": job_id,
            "status": "queued",
        }

    source = models.SourceUrl(workspace_id=ws.id, url=payload.url, type=url_type, fetch_status="queued")
    db.add(source)
    db.commit()
    db.refresh(source)

    if url_type == models.SourceUrlType.store:
        domain = extract_domain(payload.url)
        store = db.query(models.Store).filter(models.Store.workspace_id == ws.id, models.Store.domain == domain).first()
        if not store:
            store = models.Store(workspace_id=ws.id, domain=domain, platform_guess=models.PlatformGuess.unknown)
            db.add(store)
            db.commit()
            db.refresh(store)
        job_id = enqueue(crawl_store_sitemap_task, store.id, label=f"Scan store {domain}")
    else:
        job_id = enqueue(fetch_url_task, source.id, label=f"Scan {payload.url}")

    return {
        "id": source.id,
        "store_id": store.id if url_type == models.SourceUrlType.store else None,
        "type": source.type,
        "job_id": job_id,
        "status": "queued",
    }


@router.post("/ad", response_model=AdOut)
def ingest_ad(payload: AdIngest, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    ws = get_default_workspace(db, user.id)
    ad = None
    if payload.source_url:
        ad = (
            db.query(models.Ad)
            .filter(
                models.Ad.workspace_id == ws.id,
                models.Ad.data_provider == "northstar_manual",
                models.Ad.source_url == payload.source_url,
            )
            .order_by(models.Ad.id.asc())
            .first()
        )
    capture_metadata = payload.capture_metadata.model_dump(mode="json") if payload.capture_metadata else None
    if ad:
        ad.platform = models.AdPlatform(payload.platform)
        ad.source_type = "browser_extension_capture" if capture_metadata else ad.source_type
        ad.provider_metadata_json = {"capture": capture_metadata} if capture_metadata else ad.provider_metadata_json
        ad.advertiser_name = payload.advertiser_name or ad.advertiser_name
        ad.ad_text = payload.ad_text or ad.ad_text
        ad.headline = payload.headline or ad.headline
        ad.cta = payload.cta or ad.cta
        ad.creative_type = models.CreativeType(payload.creative_type) if payload.creative_type != "unknown" else ad.creative_type
        ad.creative_urls_json = payload.creative_urls or ad.creative_urls_json
        ad.landing_url = payload.landing_url or ad.landing_url
        ad.last_seen_at = datetime.utcnow()
    else:
        ad = models.Ad(
            workspace_id=ws.id,
            platform=models.AdPlatform(payload.platform),
            data_provider="northstar_manual",
            source_type="browser_extension_capture" if capture_metadata else "manual_public_import",
            source_url=payload.source_url,
            provider_metadata_json={"capture": capture_metadata} if capture_metadata else None,
            advertiser_name=payload.advertiser_name,
            ad_text=payload.ad_text,
            headline=payload.headline,
            cta=payload.cta,
            creative_type=models.CreativeType(payload.creative_type),
            creative_urls_json=payload.creative_urls,
            landing_url=payload.landing_url,
        )
        db.add(ad)
    db.commit()
    db.refresh(ad)

    if payload.metrics:
        persist_ad_metrics(db, ad=ad, metrics=payload.metrics)
        db.commit()

    if payload.landing_url:
        source = (
            db.query(models.SourceUrl)
            .filter(models.SourceUrl.workspace_id == ws.id, models.SourceUrl.url == payload.landing_url)
            .first()
        )
        if not source:
            source = models.SourceUrl(
                workspace_id=ws.id,
                url=payload.landing_url,
                type=models.SourceUrlType.landing_page,
            )
            db.add(source)
            db.commit()
            db.refresh(source)
        edge = (
            db.query(models.AdLandingEdge)
            .filter(models.AdLandingEdge.ad_id == ad.id, models.AdLandingEdge.url_id == source.id)
            .first()
        )
        if not edge:
            db.add(models.AdLandingEdge(ad_id=ad.id, url_id=source.id))
            db.commit()
        enqueue(fetch_url_task, source.id, label=f"Scan ad landing {payload.landing_url}")

    return ad


@router.post("/meta-ads-search")
def ingest_meta_ads_search(payload: MetaAdsSearchIngest, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    ws = get_default_workspace(db, user.id)
    try:
        access_token, _ = get_meta_credential()
    except IntegrationConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if not access_token:
        raise HTTPException(status_code=409, detail="Configure a Meta Ad Library access token first")
    job_id = enqueue(meta_ads_search_task, ws.id, payload.model_dump(), label="Search Meta Ad Library")
    return {
        "provider": "meta_ad_library",
        "source": "official_meta_graph_api",
        "configured": True,
        "status": "queued",
        "queued": True,
        "job_id": job_id,
    }


@router.post("/store")
def ingest_store(payload: StoreIngest, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    ws = get_default_workspace(db, user.id)
    store = db.query(models.Store).filter(models.Store.workspace_id == ws.id, models.Store.domain == payload.domain).first()
    if not store:
        store = models.Store(workspace_id=ws.id, domain=payload.domain, platform_guess=models.PlatformGuess.unknown)
        db.add(store)
        db.commit()
        db.refresh(store)
    job_id = enqueue(crawl_store_sitemap_task, store.id, label=f"Scan store {payload.domain}")
    return {"id": store.id, "job_id": job_id, "status": "queued"}


@router.get("/jobs/{job_id}")
def ingest_job(job_id: str, user: models.User = Depends(get_current_user)):
    job = get_job(job_id)
    return job or {"id": job_id, "status": "unknown"}
