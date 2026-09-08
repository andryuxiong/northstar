from datetime import datetime
from decimal import Decimal
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.intelligence_schemas import (
    EstimationProfileOut,
    EstimationProfileUpdate,
    StoreIntelligenceReportOut,
)
from app.db import models
from app.db.session import get_db
from app.services.intelligence.report import (
    assumptions_from_profile,
    build_store_report,
    get_or_create_default_profile,
    profile_payload,
)
from app.services.workspace import get_default_workspace
from app.utils.security import get_current_user


router = APIRouter()


class IdentityConfirmationIn(BaseModel):
    confirmed: bool


def _store_or_404(db: Session, workspace_id: int, store_id: int) -> models.Store:
    store = (
        db.query(models.Store)
        .filter(models.Store.workspace_id == workspace_id, models.Store.id == store_id)
        .first()
    )
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    return store


@router.get("/stores/{store_id}", response_model=StoreIntelligenceReportOut)
def store_intelligence_report(
    store_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    workspace = get_default_workspace(db, user.id)
    report = build_store_report(db, workspace_id=workspace.id, store_id=store_id)
    if not report:
        raise HTTPException(status_code=404, detail="Store not found")
    return report


@router.post("/stores/{store_id}/recompute", response_model=StoreIntelligenceReportOut)
def recompute_store_intelligence(
    store_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    workspace = get_default_workspace(db, user.id)
    report = build_store_report(
        db,
        workspace_id=workspace.id,
        store_id=store_id,
        force_recompute=True,
    )
    if not report:
        raise HTTPException(status_code=404, detail="Store not found")
    return report


@router.get("/stores/{store_id}/evidence")
def store_evidence(
    store_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    workspace = get_default_workspace(db, user.id)
    _store_or_404(db, workspace.id, store_id)
    rows = (
        db.query(models.EvidenceRecord)
        .filter(
            models.EvidenceRecord.workspace_id == workspace.id,
            models.EvidenceRecord.store_id == store_id,
        )
        .order_by(models.EvidenceRecord.observed_at.desc(), models.EvidenceRecord.id.desc())
        .limit(1000)
        .all()
    )
    return [
        {
            "id": row.id,
            "store_id": row.store_id,
            "product_id": row.product_id,
            "ad_id": row.ad_id,
            "evidence_type": row.evidence_type,
            "independence_group": row.independence_group,
            "details": row.details,
            "source_type": row.source_type,
            "source_name": row.source_name,
            "source_url": row.source_url,
            "value": (
                str(row.value_numeric)
                if row.value_numeric is not None
                else row.value_text
                if row.value_text is not None
                else row.value_json
            ),
            "unit": row.unit,
            "currency": row.currency,
            "confidence_score": float(row.confidence_score) if row.confidence_score is not None else None,
            "is_contradictory": row.is_contradictory,
            "observed_at": row.observed_at,
            "retrieved_at": row.retrieved_at,
            "freshness_expires_at": row.freshness_expires_at,
            "collector_version": row.collector_version,
        }
        for row in rows
    ]


@router.get("/stores/{store_id}/identities")
def store_identities(
    store_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    workspace = get_default_workspace(db, user.id)
    _store_or_404(db, workspace.id, store_id)
    rows = (
        db.query(models.StoreIdentity)
        .filter(
            models.StoreIdentity.workspace_id == workspace.id,
            models.StoreIdentity.store_id == store_id,
        )
        .order_by(models.StoreIdentity.confidence_score.desc())
        .all()
    )
    return [
        {
            "id": row.id,
            "identity_type": row.identity_type,
            "display_value": row.display_value,
            "source_type": row.source_type,
            "source_url": row.source_url,
            "confidence_score": float(row.confidence_score),
            "is_confirmed": row.is_confirmed,
            "evidence": row.evidence_json or {},
            "first_seen_at": row.first_seen_at,
            "last_seen_at": row.last_seen_at,
            "confirmed_at": row.confirmed_at,
        }
        for row in rows
    ]


@router.patch("/stores/{store_id}/identities/{identity_id}")
def confirm_store_identity(
    store_id: int,
    identity_id: int,
    payload: IdentityConfirmationIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    workspace = get_default_workspace(db, user.id)
    _store_or_404(db, workspace.id, store_id)
    identity = (
        db.query(models.StoreIdentity)
        .filter(
            models.StoreIdentity.workspace_id == workspace.id,
            models.StoreIdentity.store_id == store_id,
            models.StoreIdentity.id == identity_id,
        )
        .first()
    )
    if not identity:
        raise HTTPException(status_code=404, detail="Store identity not found")
    identity.is_confirmed = payload.confirmed
    identity.confirmed_at = datetime.utcnow() if payload.confirmed else None
    db.commit()
    return {"id": identity.id, "is_confirmed": identity.is_confirmed, "confirmed_at": identity.confirmed_at}


@router.get("/settings", response_model=list[EstimationProfileOut])
def estimation_settings(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    workspace = get_default_workspace(db, user.id)
    get_or_create_default_profile(db, workspace.id)
    profiles = (
        db.query(models.EstimationProfile)
        .filter(models.EstimationProfile.workspace_id == workspace.id)
        .order_by(models.EstimationProfile.is_default.desc(), models.EstimationProfile.updated_at.desc())
        .all()
    )
    return [profile_payload(profile) for profile in profiles]


@router.put("/settings/{category_key}", response_model=EstimationProfileOut)
def update_estimation_settings(
    category_key: str,
    payload: EstimationProfileUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    if not re.fullmatch(r"[a-z0-9][a-z0-9_\-]{0,99}", category_key):
        raise HTTPException(status_code=422, detail="Category key must use lowercase letters, numbers, underscores, or hyphens")
    workspace = get_default_workspace(db, user.id)
    current = (
        db.query(models.EstimationProfile)
        .filter(
            models.EstimationProfile.workspace_id == workspace.id,
            models.EstimationProfile.category_key == category_key,
            models.EstimationProfile.is_default.is_(True),
        )
        .order_by(models.EstimationProfile.updated_at.desc())
        .first()
    )
    category_current = current
    if not current:
        current = get_or_create_default_profile(db, workspace.id)

    values: dict[str, Any] = {
        "name": current.name,
        "conversion_rate_low": current.conversion_rate_low,
        "conversion_rate_central": current.conversion_rate_central,
        "conversion_rate_high": current.conversion_rate_high,
        "basket_multiplier_low": current.basket_multiplier_low,
        "basket_multiplier_central": current.basket_multiplier_central,
        "basket_multiplier_high": current.basket_multiplier_high,
        "traffic_reliability_low": current.traffic_reliability_low,
        "traffic_reliability_central": current.traffic_reliability_central,
        "traffic_reliability_high": current.traffic_reliability_high,
        "freshness_limit_days": current.freshness_limit_days,
        "minimum_evidence_count": current.minimum_evidence_count,
        "score_weights_json": dict(current.score_weights_json or {}),
        "thresholds_json": dict(current.thresholds_json or {}),
    }
    updates = payload.model_dump(exclude_none=True)
    if "score_weights" in updates:
        updates["score_weights_json"] = {key: str(value) for key, value in updates.pop("score_weights").items()}
    if "thresholds" in updates:
        merged_thresholds = dict(values["thresholds_json"])
        merged_thresholds.update(updates.pop("thresholds"))
        updates["thresholds_json"] = merged_thresholds
    values.update(updates)

    low = Decimal(str(values["conversion_rate_low"]))
    central = Decimal(str(values["conversion_rate_central"]))
    high = Decimal(str(values["conversion_rate_high"]))
    basket_low = Decimal(str(values["basket_multiplier_low"]))
    basket_central = Decimal(str(values["basket_multiplier_central"]))
    basket_high = Decimal(str(values["basket_multiplier_high"]))
    traffic_low = Decimal(str(values["traffic_reliability_low"]))
    traffic_central = Decimal(str(values["traffic_reliability_central"]))
    traffic_high = Decimal(str(values["traffic_reliability_high"]))
    if not low <= central <= high:
        raise HTTPException(status_code=422, detail="Conversion rates must be ordered low <= central <= high")
    if not basket_low <= basket_central <= basket_high:
        raise HTTPException(status_code=422, detail="Basket multipliers must be ordered low <= central <= high")
    if not traffic_low <= traffic_central <= traffic_high or traffic_high < 1:
        raise HTTPException(status_code=422, detail="Traffic reliability must be ordered and include a high value >= 1")
    enabled_groups = sum(Decimal(str(weight)) > 0 for weight in values["score_weights_json"].values())
    if int(values["minimum_evidence_count"]) > enabled_groups:
        raise HTTPException(status_code=422, detail="Minimum evidence cannot exceed enabled product evidence groups")

    if category_current is not None:
        current.is_default = False
    version = f"estimation-profile-v1-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
    profile = models.EstimationProfile(
        workspace_id=workspace.id,
        category_key=category_key,
        version=version,
        is_default=True,
        **values,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    # Validate the complete profile against estimator invariants as a final
    # guard; derived insights retain their own assumption snapshot.
    try:
        assumptions_from_profile(profile)
    except ValueError as exc:
        db.delete(profile)
        current.is_default = True
        db.commit()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return profile_payload(profile)
