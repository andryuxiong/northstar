from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import models
from app.db.session import get_db
from app.services.product_economics import calculate_product_economics
from app.services.workspace import get_default_workspace
from app.utils.security import get_current_user


router = APIRouter()


class ProductComparisonOut(BaseModel):
    product_id: int
    title: str
    canonical_url: str
    store_id: int
    store_domain: str
    platform: str
    currency: str | None
    price_low: float | None
    price_high: float | None
    available: bool | None
    variant_count: int | None
    image_count: int
    first_observed_at: datetime
    last_observed_at: datetime
    observation_days: int
    related_ad_count: int
    evidence_count: int
    evidence_types: list[str]
    economics: dict | None
    unavailable: list[str]


class ProductComparisonResponse(BaseModel):
    generated_at: datetime
    known_corpus: dict
    products: list[ProductComparisonOut]
    data_notice: str


def _parse_ids(raw: str) -> list[int]:
    try:
        ids = list(dict.fromkeys(int(part.strip()) for part in raw.split(",") if part.strip()))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="ids must be comma-separated integers") from exc
    if len(ids) < 2 or len(ids) > 5 or any(value <= 0 for value in ids):
        raise HTTPException(status_code=422, detail="Compare between 2 and 5 positive product IDs")
    return ids


@router.get("/products", response_model=ProductComparisonResponse)
def compare_products(
    ids: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    workspace = get_default_workspace(db, user.id)
    product_ids = _parse_ids(ids)
    products = db.query(models.Product).filter(
        models.Product.workspace_id == workspace.id,
        models.Product.id.in_(product_ids),
    ).all()
    if len(products) != len(product_ids):
        raise HTTPException(status_code=404, detail="One or more products were not found in this workspace")
    by_id = {product.id: product for product in products}
    rows = []
    for product_id in product_ids:
        product = by_id[product_id]
        store = db.query(models.Store).filter(
            models.Store.workspace_id == workspace.id,
            models.Store.id == product.store_id,
        ).one()
        snapshot = db.query(models.ProductSnapshot).filter(
            models.ProductSnapshot.product_id == product.id,
        ).order_by(models.ProductSnapshot.fetched_at.desc(), models.ProductSnapshot.id.desc()).first()
        related_ad_count = (
            db.query(func.count(func.distinct(models.Ad.id)))
            .join(models.AdLandingEdge, models.AdLandingEdge.ad_id == models.Ad.id)
            .join(models.LandingProductEdge, models.LandingProductEdge.landing_url_id == models.AdLandingEdge.url_id)
            .filter(
                models.Ad.workspace_id == workspace.id,
                models.LandingProductEdge.product_id == product.id,
            )
            .scalar()
            or 0
        )
        evidence = db.query(models.EvidenceRecord).filter(
            models.EvidenceRecord.workspace_id == workspace.id,
            models.EvidenceRecord.product_id == product.id,
        ).all()
        scenario = db.query(models.ProductEconomicsScenario).filter(
            models.ProductEconomicsScenario.workspace_id == workspace.id,
            models.ProductEconomicsScenario.product_id == product.id,
            models.ProductEconomicsScenario.is_active.is_(True),
        ).order_by(models.ProductEconomicsScenario.updated_at.desc(), models.ProductEconomicsScenario.id.desc()).first()
        economics = None
        if scenario:
            calculation = calculate_product_economics(scenario.__dict__)
            economics = {
                "scenario_id": scenario.id,
                "scenario_name": scenario.name,
                "revision": scenario.revision,
                "currency": scenario.currency,
                "status": calculation["status"],
                "label": calculation["label"],
                "break_even_cpa_low": calculation["break_even_cpa_low"],
                "break_even_cpa_high": calculation["break_even_cpa_high"],
                "target_cpa_low": calculation["target_cpa_low"],
                "target_cpa_high": calculation["target_cpa_high"],
                "target_roas_low": calculation["target_roas_low"],
                "target_roas_high": calculation["target_roas_high"],
                "input_source": "user_entered",
            }
        first_observed = product.created_at
        last_observed = product.last_seen_at
        rows.append(
            {
                "product_id": product.id,
                "title": product.title,
                "canonical_url": product.canonical_url,
                "store_id": store.id,
                "store_domain": store.domain,
                "platform": store.platform_guess.value,
                "currency": product.currency,
                "price_low": snapshot.price_min if snapshot else None,
                "price_high": snapshot.price_max if snapshot else None,
                "available": snapshot.available if snapshot else None,
                "variant_count": snapshot.variant_count if snapshot else None,
                "image_count": len(snapshot.images_json or []) if snapshot else 0,
                "first_observed_at": first_observed,
                "last_observed_at": last_observed,
                "observation_days": max(0, (last_observed.date() - first_observed.date()).days),
                "related_ad_count": related_ad_count,
                "evidence_count": len(evidence),
                "evidence_types": sorted({row.evidence_type for row in evidence}),
                "economics": economics,
                "unavailable": [
                    label for label, missing in (
                        ("verified sales", True),
                        ("supplier match", True),
                        ("review velocity", not any(row.evidence_type.startswith("review") for row in evidence)),
                        ("test economics", economics is None),
                    ) if missing
                ],
            }
        )
    return {
        "generated_at": datetime.utcnow(),
        "known_corpus": {
            "product_count": db.query(models.Product).filter(models.Product.workspace_id == workspace.id).count(),
            "store_count": db.query(models.Store).filter(models.Store.workspace_id == workspace.id).count(),
            "selected_product_count": len(rows),
        },
        "products": rows,
        "data_notice": (
            "This comparison covers selected products in the private Northstar corpus. "
            "Observation age is not product age, related ads are collected links rather than worldwide coverage, "
            "and user-entered economics are not supplier or performance evidence."
        ),
    }
