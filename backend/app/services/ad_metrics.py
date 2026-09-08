"""Persistence and presentation helpers for source-scoped ad analytics."""

from __future__ import annotations

from datetime import datetime
import json
from typing import Iterable

from sqlalchemy.orm import Session

from app.api.schemas import AdMetricIn
from app.db import models
from app.utils.hashing import sha256_text


PERFORMANCE_METRICS = (
    "impressions",
    "reach",
    "clicks",
    "ctr",
    "spend",
    "conversions",
    "conversion_rate",
    "cpa",
    "roas",
)


def persist_ad_metrics(
    db: Session,
    *,
    ad: models.Ad,
    metrics: Iterable[AdMetricIn],
    retrieved_at: datetime | None = None,
) -> list[models.AdMetricObservation]:
    retrieved_at = retrieved_at or datetime.utcnow()
    records: list[models.AdMetricObservation] = []
    for metric in metrics:
        observed_at = metric.observed_at or retrieved_at
        payload = metric.model_dump(mode="json", exclude_none=True)
        key_payload = json.dumps(
            {
                "workspace_id": ad.workspace_id,
                "ad_id": ad.id,
                "metric": payload,
                "observed_at": observed_at.isoformat(),
                "source_url": ad.source_url,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        observation_key = sha256_text(key_payload)
        existing = (
            db.query(models.AdMetricObservation)
            .filter(
                models.AdMetricObservation.workspace_id == ad.workspace_id,
                models.AdMetricObservation.observation_key == observation_key,
            )
            .first()
        )
        if existing:
            records.append(existing)
            continue
        record = models.AdMetricObservation(
            workspace_id=ad.workspace_id,
            ad_id=ad.id,
            observation_key=observation_key,
            metric_key=metric.metric_key,
            value_kind=metric.value_kind,
            value_numeric=metric.value_numeric,
            range_low=metric.range_low,
            range_high=metric.range_high,
            value_text=metric.value_text,
            unit=metric.unit,
            provider=metric.provider,
            source_type=metric.source_type,
            source_url=ad.source_url,
            geography=metric.geography,
            period_start=metric.period_start,
            period_end=metric.period_end,
            confidence_score=metric.confidence_score,
            observed_at=observed_at,
            retrieved_at=retrieved_at,
            metadata_json=metric.metadata,
        )
        db.add(record)
        records.append(record)
    db.flush()
    return records


def build_ad_analytics(db: Session, ad: models.Ad) -> dict:
    metrics = (
        db.query(models.AdMetricObservation)
        .filter(models.AdMetricObservation.ad_id == ad.id)
        .order_by(
            models.AdMetricObservation.observed_at.desc(),
            models.AdMetricObservation.id.desc(),
        )
        .all()
    )
    observed_signals: list[dict] = [
        {
            "metric_key": "northstar_first_observed",
            "value_kind": "timestamp",
            "value": ad.first_seen_at,
            "source": "northstar_observation",
            "explanation": "When Northstar first saved or imported this record; not the ad launch time.",
        },
        {
            "metric_key": "creative_asset_count",
            "value_kind": "exact",
            "value": len(ad.creative_urls_json or []),
            "unit": "assets",
            "source": "northstar_observation",
            "explanation": "Count of creative URLs attached to this local record.",
        },
    ]
    if ad.delivery_start_time:
        observed_signals.append(
            {
                "metric_key": "provider_delivery_start",
                "value_kind": "timestamp",
                "value": ad.delivery_start_time,
                "source": ad.data_provider,
                "explanation": "Provider-reported delivery start when available.",
            }
        )
    if ad.delivery_start_time and ad.delivery_stop_time:
        observed_signals.append(
            {
                "metric_key": "completed_delivery_duration",
                "value_kind": "exact",
                "value": max(0, (ad.delivery_stop_time - ad.delivery_start_time).days),
                "unit": "days",
                "source": ad.data_provider,
                "explanation": "Completed provider delivery window; not proof of continuous spend or profitability.",
            }
        )

    recorded_keys = {row.metric_key for row in metrics if row.value_kind != "unavailable"}
    explicitly_unavailable = {
        row.metric_key: row.value_text
        for row in metrics
        if row.value_kind == "unavailable"
    }
    unavailable = [
        {
            "metric_key": key,
            "reason": explicitly_unavailable.get(
                key,
                "This source has not supplied a verified value for this competitor ad.",
            ),
        }
        for key in PERFORMANCE_METRICS
        if key not in recorded_keys
    ]
    return {
        "ad_id": ad.id,
        "data_provider": ad.data_provider,
        "source_type": ad.source_type,
        "source_url": ad.source_url,
        "metrics": metrics,
        "observed_signals": observed_signals,
        "unavailable_metrics": unavailable,
        "has_provider_performance_metrics": bool(recorded_keys & set(PERFORMANCE_METRICS)),
        "data_notice": (
            "Metrics retain their source and value kind. A reported value, range, percentile, "
            "classification, or Northstar observation is never converted into exact competitor performance."
        ),
    }
