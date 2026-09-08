from datetime import datetime, timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.db import models
from app.db.session import get_db
from app.services.ad_watchlists import run_ad_watch
from app.services.workspace import get_default_workspace
from app.utils.security import get_current_user
from app.workers.runner import enqueue


router = APIRouter()


class AdWatchIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    provider: Literal["meta_ad_library", "tiktok_commercial_content", "google_transparency", "manual_capture"] = "meta_ad_library"
    store_id: Optional[int] = None
    search_terms: Optional[str] = Field(default=None, max_length=100)
    advertiser_id: Optional[str] = Field(default=None, max_length=255)
    countries: list[str] = Field(default_factory=lambda: ["GB"], min_length=1, max_length=25)
    interval_hours: int = Field(default=24, ge=1, le=24 * 30)
    result_limit: int = Field(default=50, ge=1, le=500)
    is_enabled: bool = True

    @field_validator("name", "search_terms", "advertiser_id", mode="before")
    @classmethod
    def strip_text(cls, value):
        if value is None:
            return None
        return str(value).strip() or None

    @field_validator("countries", mode="before")
    @classmethod
    def normalize_countries(cls, value):
        countries = list(dict.fromkeys(str(item).strip().upper() for item in (value or []) if str(item).strip()))
        if not countries or any(item != "ALL" and (len(item) != 2 or not item.isalpha()) for item in countries):
            raise ValueError("Use two-letter country codes such as GB, or ALL")
        return countries

    @model_validator(mode="after")
    def require_target(self):
        if not self.search_terms and not self.advertiser_id:
            raise ValueError("Provide search terms or a provider advertiser/Page ID")
        if self.provider == "meta_ad_library" and self.advertiser_id and not self.advertiser_id.isdigit():
            raise ValueError("Meta advertiser/Page IDs must be numeric")
        return self


class AdWatchPatch(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    search_terms: Optional[str] = Field(default=None, max_length=100)
    advertiser_id: Optional[str] = Field(default=None, max_length=255)
    countries: Optional[list[str]] = None
    interval_hours: Optional[int] = Field(default=None, ge=1, le=24 * 30)
    result_limit: Optional[int] = Field(default=None, ge=1, le=500)
    is_enabled: Optional[bool] = None


def _watch_or_404(db: Session, workspace_id: int, watch_id: int) -> models.AdWatch:
    watch = db.query(models.AdWatch).filter(models.AdWatch.workspace_id == workspace_id, models.AdWatch.id == watch_id).first()
    if not watch:
        raise HTTPException(status_code=404, detail="Ad watch not found")
    return watch


def _watch_payload(db: Session, watch: models.AdWatch) -> dict:
    observations = db.query(models.AdWatchObservation).filter(models.AdWatchObservation.watch_id == watch.id).all()
    latest_run = db.query(models.AdCollectionRun).filter(models.AdCollectionRun.watch_id == watch.id).order_by(desc(models.AdCollectionRun.started_at)).first()
    tier_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    for item in observations:
        tier_counts[item.retention_tier] = tier_counts.get(item.retention_tier, 0) + 1
        status_counts[item.current_status] = status_counts.get(item.current_status, 0) + 1
    return {
        "id": watch.id,
        "name": watch.name,
        "provider": watch.provider,
        "store_id": watch.store_id,
        "store_domain": watch.store.domain if watch.store else None,
        "search_terms": watch.search_terms,
        "advertiser_id": watch.advertiser_id,
        "countries": list(watch.countries_json or []),
        "interval_hours": watch.interval_hours,
        "result_limit": watch.result_limit,
        "is_enabled": watch.is_enabled,
        "last_run_at": watch.last_run_at,
        "next_run_at": watch.next_run_at,
        "last_status": watch.last_status,
        "last_error": watch.last_error,
        "created_at": watch.created_at,
        "updated_at": watch.updated_at,
        "ad_count": len(observations),
        "retention_tiers": tier_counts,
        "observation_statuses": status_counts,
        "latest_run": _run_payload(latest_run) if latest_run else None,
    }


def _run_payload(run: models.AdCollectionRun) -> dict:
    return {
        "id": run.id,
        "watch_id": run.watch_id,
        "provider": run.provider,
        "trigger": run.trigger,
        "status": run.status,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "fetched_count": run.fetched_count,
        "inserted_count": run.inserted_count,
        "updated_count": run.updated_count,
        "recurring_count": run.recurring_count,
        "error_code": run.error_code,
        "error_message": run.error_message,
    }


@router.get("")
def list_ad_watches(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    workspace = get_default_workspace(db, user.id)
    watches = db.query(models.AdWatch).filter(models.AdWatch.workspace_id == workspace.id).order_by(desc(models.AdWatch.updated_at)).all()
    return {
        "watches": [_watch_payload(db, watch) for watch in watches],
        "summary": {
            "total": len(watches),
            "enabled": sum(1 for watch in watches if watch.is_enabled),
            "due": sum(1 for watch in watches if watch.is_enabled and watch.next_run_at and watch.next_run_at <= datetime.utcnow()),
            "failed": sum(1 for watch in watches if watch.last_status == "failed"),
        },
        "retention_policy": {
            "metadata": "Single observations keep compact metadata and provider references.",
            "evidence": "Repeated observations preserve longevity evidence.",
            "creative": "Recurring or long-running ads preserve creative references.",
            "research": "Investigation-saved ads receive the strongest retention priority.",
            "absence_rule": "A missing query result is recorded as not seen, never asserted to be inactive without provider evidence.",
        },
    }


@router.post("", status_code=201)
def create_ad_watch(payload: AdWatchIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    workspace = get_default_workspace(db, user.id)
    if payload.store_id:
        store = db.query(models.Store).filter(models.Store.workspace_id == workspace.id, models.Store.id == payload.store_id).first()
        if not store:
            raise HTTPException(status_code=400, detail="Store does not belong to this workspace")
    now = datetime.utcnow()
    watch = models.AdWatch(
        workspace_id=workspace.id,
        store_id=payload.store_id,
        name=payload.name,
        provider=payload.provider,
        search_terms=payload.search_terms,
        advertiser_id=payload.advertiser_id,
        countries_json=payload.countries,
        interval_hours=payload.interval_hours,
        result_limit=payload.result_limit,
        is_enabled=payload.is_enabled,
        next_run_at=now if payload.is_enabled else None,
        created_at=now,
        updated_at=now,
    )
    db.add(watch)
    db.commit()
    db.refresh(watch)
    return _watch_payload(db, watch)


@router.patch("/{watch_id}")
def update_ad_watch(watch_id: int, payload: AdWatchPatch, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    workspace = get_default_workspace(db, user.id)
    watch = _watch_or_404(db, workspace.id, watch_id)
    changes = payload.model_dump(exclude_unset=True)
    if "countries" in changes:
        changes["countries_json"] = AdWatchIn.normalize_countries(changes.pop("countries"))
    for key, value in changes.items():
        setattr(watch, key, value)
    if watch.provider == "meta_ad_library" and watch.advertiser_id and not watch.advertiser_id.isdigit():
        raise HTTPException(status_code=422, detail="Meta advertiser/Page IDs must be numeric")
    if not watch.search_terms and not watch.advertiser_id:
        raise HTTPException(status_code=422, detail="Provide search terms or an advertiser ID")
    now = datetime.utcnow()
    watch.updated_at = now
    if "is_enabled" in changes:
        watch.next_run_at = now if watch.is_enabled else None
        if not watch.is_enabled:
            watch.last_status = "paused"
    db.commit()
    db.refresh(watch)
    return _watch_payload(db, watch)


@router.post("/{watch_id}/run", status_code=202)
def run_watch_now(watch_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    workspace = get_default_workspace(db, user.id)
    watch = _watch_or_404(db, workspace.id, watch_id)
    if watch.last_status in {"queued", "running"}:
        raise HTTPException(status_code=409, detail="This watch is already queued or running")
    watch.last_status = "queued"
    watch.last_error = None
    watch.next_run_at = datetime.utcnow() + timedelta(minutes=10) if watch.is_enabled else None
    db.commit()
    job_id = enqueue(run_ad_watch, watch.id, "manual", label=f"Refresh ad watch {watch.name}")
    return {"watch_id": watch.id, "job_id": job_id, "status": "queued"}


@router.get("/{watch_id}/runs")
def list_watch_runs(watch_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    workspace = get_default_workspace(db, user.id)
    _watch_or_404(db, workspace.id, watch_id)
    runs = db.query(models.AdCollectionRun).filter(models.AdCollectionRun.watch_id == watch_id).order_by(desc(models.AdCollectionRun.started_at)).limit(100).all()
    return [_run_payload(run) for run in runs]


@router.delete("/{watch_id}", status_code=204)
def delete_ad_watch(watch_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    workspace = get_default_workspace(db, user.id)
    watch = _watch_or_404(db, workspace.id, watch_id)
    db.delete(watch)
    db.commit()
