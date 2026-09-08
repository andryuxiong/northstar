from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.ads import _build_ad_autopsy
from app.api.investigations import _item_or_404, _response as investigation_response
from app.db import models
from app.db.session import get_db
from app.services.intelligence.report import build_store_report
from app.services.product_economics import calculate_product_economics
from app.services.workspace import get_default_workspace
from app.utils.security import get_current_user


router = APIRouter()
DOSSIER_VERSION = "research-dossier-v1"


def _product_dossier(db: Session, workspace_id: int, product_id: int) -> dict:
    product = db.query(models.Product).filter(
        models.Product.workspace_id == workspace_id,
        models.Product.id == product_id,
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    store = db.query(models.Store).filter(
        models.Store.workspace_id == workspace_id,
        models.Store.id == product.store_id,
    ).one()
    snapshots = db.query(models.ProductSnapshot).filter(
        models.ProductSnapshot.product_id == product.id,
    ).order_by(models.ProductSnapshot.fetched_at.desc()).limit(25).all()
    evidence = db.query(models.EvidenceRecord).filter(
        models.EvidenceRecord.workspace_id == workspace_id,
        models.EvidenceRecord.product_id == product.id,
    ).order_by(models.EvidenceRecord.observed_at.desc()).all()
    scenarios = db.query(models.ProductEconomicsScenario).filter(
        models.ProductEconomicsScenario.workspace_id == workspace_id,
        models.ProductEconomicsScenario.product_id == product.id,
        models.ProductEconomicsScenario.is_active.is_(True),
    ).order_by(models.ProductEconomicsScenario.updated_at.desc()).all()
    related_ads = (
        db.query(models.Ad)
        .join(models.AdLandingEdge, models.AdLandingEdge.ad_id == models.Ad.id)
        .join(models.LandingProductEdge, models.LandingProductEdge.landing_url_id == models.AdLandingEdge.url_id)
        .filter(models.Ad.workspace_id == workspace_id, models.LandingProductEdge.product_id == product.id)
        .distinct()
        .all()
    )
    return {
        "product": {
            "id": product.id,
            "title": product.title,
            "canonical_url": product.canonical_url,
            "currency": product.currency,
            "first_observed_at": product.created_at,
            "last_observed_at": product.last_seen_at,
        },
        "store": {"id": store.id, "domain": store.domain, "platform": store.platform_guess.value},
        "recent_snapshots": [
            {
                "fetched_at": row.fetched_at,
                "price_low": row.price_min,
                "price_high": row.price_max,
                "available": row.available,
                "variant_count": row.variant_count,
                "image_count": len(row.images_json or []),
            }
            for row in snapshots
        ],
        "economics_scenarios": [
            {
                "id": row.id,
                "name": row.name,
                "revision": row.revision,
                "input_source": row.input_source,
                "currency": row.currency,
                "assumptions": {
                    key: getattr(row, key)
                    for key in (
                        "selling_price", "product_cost_low", "product_cost_high",
                        "shipping_cost_low", "shipping_cost_high", "fulfillment_cost_low",
                        "fulfillment_cost_high", "other_variable_cost_low",
                        "other_variable_cost_high", "payment_fee_rate", "payment_fee_fixed",
                        "refund_allowance_rate", "target_profit_margin",
                    )
                },
                "calculation": calculate_product_economics(row.__dict__),
                "notes": row.notes,
                "updated_at": row.updated_at,
            }
            for row in scenarios
        ],
        "related_collected_ads": [
            {
                "id": row.id,
                "platform": row.platform.value,
                "advertiser_name": row.advertiser_name,
                "headline": row.headline,
                "data_provider": row.data_provider,
                "source_type": row.source_type,
                "first_observed_at": row.first_seen_at,
                "last_observed_at": row.last_seen_at,
            }
            for row in related_ads
        ],
        "evidence": [
            {
                "id": row.id,
                "evidence_type": row.evidence_type,
                "source_type": row.source_type,
                "source_name": row.source_name,
                "source_url": row.source_url,
                "details": row.details,
                "confidence_score": row.confidence_score,
                "observed_at": row.observed_at,
            }
            for row in evidence
        ],
        "unavailable": [
            "verified product sales",
            "confirmed supplier relationship",
            "worldwide competitor count",
            "competitor profit or ROAS",
        ],
    }


@router.get("/investigations/{item_id}")
def export_investigation_dossier(
    item_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    workspace = get_default_workspace(db, user.id)
    item = _item_or_404(db, workspace.id, item_id)
    if item.entity_type == "store":
        entity_data = build_store_report(db, workspace_id=workspace.id, store_id=item.entity_id)
    elif item.entity_type == "ad":
        ad = db.query(models.Ad).filter(
            models.Ad.workspace_id == workspace.id,
            models.Ad.id == item.entity_id,
        ).first()
        if not ad:
            raise HTTPException(status_code=404, detail="Ad not found")
        entity_data = _build_ad_autopsy(db, workspace.id, ad)
    else:
        entity_data = _product_dossier(db, workspace.id, item.entity_id)
    payload = {
        "dossier_version": DOSSIER_VERSION,
        "generated_at": datetime.utcnow(),
        "investigation": investigation_response(db, workspace.id, item),
        "entity_data": entity_data,
        "trust_notice": (
            "This dossier contains public observations, provider records/estimates, Northstar calculations, "
            "and user-entered research state. Inspect each field's source; unavailable values are not zero."
        ),
    }
    filename = f"northstar-investigation-{item.id}.json"
    return JSONResponse(
        content=jsonable_encoder(payload),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
