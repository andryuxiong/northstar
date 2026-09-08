from fastapi import APIRouter, Depends
from sqlalchemy import desc, func
from sqlalchemy.orm import Session
from urllib.parse import urlparse

from app.db import models
from app.db.session import get_db
from app.services.product_media import product_image_url
from app.services.workspace import get_default_workspace
from app.services.traffic import traffic_snapshot_payload
from app.utils.security import get_current_user
from app.workers.runner import recent_jobs


router = APIRouter()


@router.get("")
def local_library(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Return collected stores, products, source state, and current scan jobs."""
    workspace = get_default_workspace(db, user.id)
    store_rows = (
        db.query(models.Store, func.count(models.Product.id).label("product_count"))
        .outerjoin(models.Product, models.Product.store_id == models.Store.id)
        .filter(models.Store.workspace_id == workspace.id)
        .group_by(models.Store.id)
        .order_by(desc(models.Store.last_seen_at))
        .all()
    )
    latest_traffic_by_store: dict[int, models.TrafficSnapshot] = {}
    traffic_rows = (
        db.query(models.TrafficSnapshot)
        .filter(
            models.TrafficSnapshot.workspace_id == workspace.id,
            models.TrafficSnapshot.store_id.is_not(None),
        )
        .order_by(desc(models.TrafficSnapshot.fetched_at))
        .all()
    )
    for traffic in traffic_rows:
        if traffic.store_id not in latest_traffic_by_store:
            latest_traffic_by_store[traffic.store_id] = traffic
    product_rows = (
        db.query(models.Product)
        .filter(models.Product.workspace_id == workspace.id)
        .order_by(desc(models.Product.last_seen_at))
        .limit(200)
        .all()
    )
    product_count = (
        db.query(func.count(models.Product.id))
        .filter(models.Product.workspace_id == workspace.id)
        .scalar()
        or 0
    )

    collected_products = []
    for product in product_rows:
        snapshot = (
            db.query(models.ProductSnapshot)
            .filter(models.ProductSnapshot.product_id == product.id)
            .order_by(desc(models.ProductSnapshot.fetched_at))
            .first()
        )
        snapshot_count = (
            db.query(func.count(models.ProductSnapshot.id))
            .filter(models.ProductSnapshot.product_id == product.id)
            .scalar()
            or 0
        )
        oldest_snapshot = (
            db.query(models.ProductSnapshot)
            .filter(models.ProductSnapshot.product_id == product.id)
            .order_by(models.ProductSnapshot.fetched_at.asc())
            .first()
        )
        has_trend_history = bool(
            snapshot
            and oldest_snapshot
            and snapshot_count >= 2
            and (snapshot.fetched_at - oldest_snapshot.fetched_at).total_seconds() >= 86400
        )
        score = (
            db.query(models.Score)
            .filter(
                models.Score.entity_type == models.SignalEntityType.product,
                models.Score.entity_id == product.id,
                models.Score.score_type == models.ScoreType.momentum,
            )
            .order_by(desc(models.Score.computed_at))
            .first()
        )
        collected_products.append(
            {
                "id": product.id,
                "title": product.title,
                "canonical_url": product.canonical_url,
                "store_domain": product.store.domain if product.store else None,
                "currency": product.currency,
                "last_seen_at": product.last_seen_at,
                "price_min": snapshot.price_min if snapshot else None,
                "price_max": snapshot.price_max if snapshot else None,
                "available": snapshot.available if snapshot else None,
                "variant_count": snapshot.variant_count if snapshot else None,
                "snapshot_count": snapshot_count,
                "image_url": product_image_url(product.canonical_url, snapshot),
                "momentum_score": score.score_value if score and has_trend_history else None,
                "confidence": score.confidence if score and has_trend_history else None,
            }
        )

    sources = (
        db.query(models.SourceUrl)
        .filter(models.SourceUrl.workspace_id == workspace.id)
        .order_by(desc(models.SourceUrl.created_at))
        .limit(100)
        .all()
    )
    successful_source_urls = (
        db.query(models.SourceUrl.url)
        .filter(
            models.SourceUrl.workspace_id == workspace.id,
            models.SourceUrl.fetch_status == "fetched",
        )
        .all()
    )
    observed_domains = {
        (urlparse(url).hostname or "").lower().removeprefix("www.")
        for (url,) in successful_source_urls
    }
    observed_store_count = sum(
        1
        for store, count in store_rows
        if count > 0 or store.domain.lower().removeprefix("www.") in observed_domains
    )
    source_count = (
        db.query(func.count(models.SourceUrl.id))
        .filter(models.SourceUrl.workspace_id == workspace.id)
        .scalar()
        or 0
    )
    fetched_source_count = (
        db.query(func.count(models.SourceUrl.id))
        .filter(
            models.SourceUrl.workspace_id == workspace.id,
            models.SourceUrl.fetch_status == "fetched",
        )
        .scalar()
        or 0
    )
    jobs = recent_jobs()
    return {
        "summary": {
            "stores": len(store_rows),
            "observed_stores": observed_store_count,
            "submitted_stores": len(store_rows) - observed_store_count,
            "products": product_count,
            "sources": source_count,
            "fetched_sources": fetched_source_count,
            "active_jobs": sum(1 for job in recent_jobs(100) if job["status"] in {"queued", "running"}),
        },
        "stores": [
            {
                "id": store.id,
                "domain": store.domain,
                "platform": store.platform_guess.value,
                "last_seen_at": store.last_seen_at,
                "product_count": product_count,
                "observation_state": (
                    "observed"
                    if product_count > 0
                    or store.domain.lower().removeprefix("www.") in observed_domains
                    else "submitted"
                ),
                "traffic": (
                    traffic_snapshot_payload(latest_traffic_by_store[store.id], include_series=False)
                    if store.id in latest_traffic_by_store
                    else None
                ),
            }
            for store, product_count in store_rows
        ],
        "products": collected_products,
        "sources": [
            {
                "id": source.id,
                "url": source.url,
                "type": source.type.value,
                "fetch_status": source.fetch_status or "pending",
                "last_http_status": source.last_http_status,
                "created_at": source.created_at,
                "last_fetched_at": source.last_fetched_at,
            }
            for source in sources
        ],
        "jobs": jobs,
    }
