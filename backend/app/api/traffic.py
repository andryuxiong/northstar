from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.api.schemas import TrafficRefreshIn
from app.db import models
from app.db.session import get_db
from app.services.integration_config import IntegrationConfigError, get_similarweb_credential
from app.services.similarweb import SimilarwebClient, normalize_domain
from app.services.traffic import persist_traffic_snapshot, traffic_snapshot_payload
from app.services.workspace import get_default_workspace
from app.utils.security import get_current_user


router = APIRouter()


def _credential() -> str:
    try:
        api_key, _ = get_similarweb_credential()
    except IntegrationConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if not api_key:
        raise HTTPException(status_code=409, detail="Configure a Similarweb REST API key first")
    return api_key


def _domain(value: str) -> str:
    try:
        return normalize_domain(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _refresh(
    db: Session,
    *,
    workspace_id: int,
    store_id: int | None,
    domain: str,
    payload: TrafficRefreshIn,
):
    if not payload.force:
        cached = (
            db.query(models.TrafficSnapshot)
            .filter(
                models.TrafficSnapshot.workspace_id == workspace_id,
                models.TrafficSnapshot.domain == domain,
                models.TrafficSnapshot.period_start == payload.start_date,
                models.TrafficSnapshot.period_end == payload.end_date,
                models.TrafficSnapshot.country == payload.country,
                models.TrafficSnapshot.main_domain_only == payload.main_domain_only,
                models.TrafficSnapshot.fetch_status.in_(["success", "partial"]),
                models.TrafficSnapshot.fetched_at >= datetime.utcnow() - timedelta(hours=24),
            )
            .order_by(models.TrafficSnapshot.fetched_at.desc())
            .first()
        )
        if cached:
            response = traffic_snapshot_payload(cached)
            response["cached"] = True
            response["cache_notice"] = (
                "Reused a traffic snapshot collected within 24 hours to avoid duplicate provider credit use. "
                "Send force=true to request a new provider response."
            )
            return response
    with SimilarwebClient(_credential()) as client:
        result = client.fetch(
            domain=domain,
            start_date=payload.start_date,
            end_date=payload.end_date,
            country=payload.country,
            main_domain_only=payload.main_domain_only,
        )
    snapshot = persist_traffic_snapshot(
        db,
        workspace_id=workspace_id,
        store_id=store_id,
        result=result,
    )
    response = traffic_snapshot_payload(snapshot)
    response["cached"] = False
    return response


@router.post("/stores/{store_id}/refresh")
def refresh_store_traffic(
    store_id: int,
    payload: TrafficRefreshIn | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    workspace = get_default_workspace(db, user.id)
    store = (
        db.query(models.Store)
        .filter(models.Store.workspace_id == workspace.id, models.Store.id == store_id)
        .first()
    )
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    return _refresh(
        db,
        workspace_id=workspace.id,
        store_id=store.id,
        domain=store.domain,
        payload=payload or TrafficRefreshIn(),
    )


@router.post("/domains/{domain}/refresh")
def refresh_domain_traffic(
    domain: str,
    payload: TrafficRefreshIn | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    workspace = get_default_workspace(db, user.id)
    normalized = _domain(domain)
    store = (
        db.query(models.Store)
        .filter(models.Store.workspace_id == workspace.id, models.Store.domain == normalized)
        .first()
    )
    return _refresh(
        db,
        workspace_id=workspace.id,
        store_id=store.id if store else None,
        domain=normalized,
        payload=payload or TrafficRefreshIn(),
    )


@router.get("/stores/{store_id}")
def store_traffic_history(
    store_id: int,
    limit: int = Query(default=24, ge=1, le=200),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    workspace = get_default_workspace(db, user.id)
    store = (
        db.query(models.Store)
        .filter(models.Store.workspace_id == workspace.id, models.Store.id == store_id)
        .first()
    )
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    rows = (
        db.query(models.TrafficSnapshot)
        .filter(
            models.TrafficSnapshot.workspace_id == workspace.id,
            models.TrafficSnapshot.store_id == store.id,
        )
        .order_by(desc(models.TrafficSnapshot.fetched_at))
        .limit(limit)
        .all()
    )
    return [traffic_snapshot_payload(row) for row in rows]


@router.get("/domains/{domain}")
def domain_traffic_history(
    domain: str,
    limit: int = Query(default=24, ge=1, le=200),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    workspace = get_default_workspace(db, user.id)
    normalized = _domain(domain)
    rows = (
        db.query(models.TrafficSnapshot)
        .filter(
            models.TrafficSnapshot.workspace_id == workspace.id,
            models.TrafficSnapshot.domain == normalized,
        )
        .order_by(desc(models.TrafficSnapshot.fetched_at))
        .limit(limit)
        .all()
    )
    return [traffic_snapshot_payload(row) for row in rows]
