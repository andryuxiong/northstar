"""Durable, provider-honest ad watch collection and retention classification."""

from __future__ import annotations

from datetime import datetime, timedelta
from threading import Event, Thread
from typing import Any

from sqlalchemy.orm import Session

from app.db import models
from app.db.session import SessionLocal
from app.services.integration_config import IntegrationConfigError, get_meta_credential
from app.services.meta_ads import MetaAdsAPIError, persist_meta_ads, search_ads_archive
from app.workers.runner import enqueue


_scheduler_stop = Event()
_scheduler_thread: Thread | None = None


def _retention(ad: models.Ad, observation_count: int, first_seen: datetime, pinned: bool) -> tuple[str, str]:
    observed_days = max(0, (ad.last_seen_at - first_seen).days)
    provider_days = max(
        0,
        ((ad.delivery_stop_time or datetime.utcnow()) - ad.delivery_start_time).days,
    ) if ad.delivery_start_time else 0
    if pinned:
        return "research", "Saved to an investigation; retain metadata and available creative evidence."
    if observation_count >= 3 or observed_days >= 7 or provider_days >= 14:
        return "creative", "Recurring or long-running ad; retain creative references and normalized metadata."
    if observation_count >= 2 or observed_days >= 2 or provider_days >= 3:
        return "evidence", "Repeated observation; retain as campaign-longevity evidence."
    return "metadata", "Single or short observation; retain compact metadata and hashes only."


def run_ad_watch(watch_id: int, trigger: str = "manual") -> dict[str, Any]:
    db = SessionLocal()
    run: models.AdCollectionRun | None = None
    try:
        watch = db.query(models.AdWatch).filter(models.AdWatch.id == watch_id).first()
        if not watch:
            raise ValueError("Ad watch does not exist")
        now = datetime.utcnow()
        run = models.AdCollectionRun(
            workspace_id=watch.workspace_id,
            watch_id=watch.id,
            provider=watch.provider,
            trigger=trigger,
            status="running",
            started_at=now,
        )
        watch.last_status = "running"
        watch.last_error = None
        db.add(run)
        db.commit()
        db.refresh(run)

        if watch.provider != "meta_ad_library":
            raise MetaAdsAPIError(
                "This source is queued for official access or user-assisted capture; automatic scraping is disabled",
                code="PROVIDER_NOT_AUTOMATED",
            )
        try:
            access_token, _ = get_meta_credential()
        except IntegrationConfigError as exc:
            raise MetaAdsAPIError(str(exc), code="META_CONFIG_ERROR") from exc
        if not access_token:
            raise MetaAdsAPIError("Configure a Meta Ad Library access token first", code="META_NOT_CONFIGURED")

        raw_ads = search_ads_archive(
            access_token=access_token,
            ad_reached_countries=list(watch.countries_json or ["GB"]),
            search_terms=watch.search_terms,
            search_page_ids=[watch.advertiser_id] if watch.advertiser_id else None,
            ad_type="ALL",
            ad_active_status="ALL",
            limit=watch.result_limit,
        )
        persisted = persist_meta_ads(db, workspace_id=watch.workspace_id, raw_ads=raw_ads, observed_at=now)
        seen_ids = {ad.id for ad in persisted.records}
        existing = {
            item.ad_id: item
            for item in db.query(models.AdWatchObservation)
            .filter(models.AdWatchObservation.watch_id == watch.id)
            .all()
        }
        recurring = 0
        pinned_ad_ids = {
            row[0]
            for row in db.query(models.InvestigationItem.entity_id)
            .filter(
                models.InvestigationItem.workspace_id == watch.workspace_id,
                models.InvestigationItem.entity_type == "ad",
            )
            .all()
        }
        for ad in persisted.records:
            observation = existing.get(ad.id)
            if observation:
                observation.observation_count += 1
                observation.last_seen_at = now
                observation.consecutive_misses = 0
                observation.current_status = "observed"
                recurring += 1
            else:
                observation = models.AdWatchObservation(
                    workspace_id=watch.workspace_id,
                    watch_id=watch.id,
                    ad_id=ad.id,
                    first_seen_at=now,
                    last_seen_at=now,
                )
                db.add(observation)
            tier, reason = _retention(ad, observation.observation_count, observation.first_seen_at, ad.id in pinned_ad_ids)
            observation.retention_tier = tier
            observation.retention_reason = reason

        # Absence is recorded as query evidence, not claimed as ad inactivity.
        for ad_id, observation in existing.items():
            if ad_id not in seen_ids:
                observation.consecutive_misses += 1
                observation.current_status = "not_seen_latest" if observation.consecutive_misses < 2 else "not_seen_repeatedly"

        finished = datetime.utcnow()
        run.status = "completed"
        run.finished_at = finished
        run.fetched_count = len(raw_ads)
        run.inserted_count = persisted.inserted_count
        run.updated_count = persisted.updated_count
        run.recurring_count = recurring
        watch.last_run_at = finished
        watch.next_run_at = finished + timedelta(hours=watch.interval_hours) if watch.is_enabled else None
        watch.last_status = "completed"
        watch.updated_at = finished
        db.commit()
        return {
            "watch_id": watch.id,
            "run_id": run.id,
            "status": run.status,
            "fetched_count": run.fetched_count,
            "inserted_count": run.inserted_count,
            "updated_count": run.updated_count,
            "recurring_count": run.recurring_count,
        }
    except Exception as exc:
        db.rollback()
        now = datetime.utcnow()
        watch = db.query(models.AdWatch).filter(models.AdWatch.id == watch_id).first()
        if run:
            run = db.query(models.AdCollectionRun).filter(models.AdCollectionRun.id == run.id).first()
            if run:
                run.status = "failed"
                run.finished_at = now
                run.error_code = getattr(exc, "code", exc.__class__.__name__)
                run.error_message = str(exc)[:500]
        if watch:
            watch.last_run_at = now
            watch.next_run_at = now + timedelta(hours=watch.interval_hours) if watch.is_enabled else None
            watch.last_status = "failed"
            watch.last_error = str(exc)[:500]
            watch.updated_at = now
        db.commit()
        raise
    finally:
        db.close()


def enqueue_due_watches() -> int:
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        watches = (
            db.query(models.AdWatch)
            .filter(
                models.AdWatch.is_enabled.is_(True),
                models.AdWatch.next_run_at.isnot(None),
                models.AdWatch.next_run_at <= now,
                models.AdWatch.last_status != "queued",
                models.AdWatch.last_status != "running",
            )
            .all()
        )
        ids = [watch.id for watch in watches]
        for watch in watches:
            watch.last_status = "queued"
            watch.next_run_at = now + timedelta(minutes=10)
        db.commit()
    finally:
        db.close()
    for watch_id in ids:
        enqueue(run_ad_watch, watch_id, "scheduled", label=f"Refresh ad watch {watch_id}")
    return len(ids)


def _scheduler_loop() -> None:
    while not _scheduler_stop.wait(60):
        try:
            enqueue_due_watches()
        except Exception:
            # Individual durable runs carry user-visible errors; the scheduler
            # remains alive for later watches and transient SQLite contention.
            continue


def start_ad_watch_scheduler() -> None:
    global _scheduler_thread
    if _scheduler_thread and _scheduler_thread.is_alive():
        return
    _scheduler_stop.clear()
    _scheduler_thread = Thread(target=_scheduler_loop, name="northstar-ad-watch-scheduler", daemon=True)
    _scheduler_thread.start()


def stop_ad_watch_scheduler() -> None:
    _scheduler_stop.set()
