from calendar import monthrange
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.orm import Session

from app.db import models
from app.utils.hashing import sha256_text


TRAFFIC_DATA_NOTICE = (
    "Similarweb traffic and rank are third-party estimates. They are not exact, "
    "real-time, or first-party store analytics."
)


def persist_traffic_snapshot(
    db: Session,
    *,
    workspace_id: int,
    store_id: int | None,
    result: dict[str, Any],
) -> models.TrafficSnapshot:
    snapshot = models.TrafficSnapshot(
        workspace_id=workspace_id,
        store_id=store_id,
        domain=result["domain"],
        provider=result["provider"],
        period_start=result["period_start"],
        period_end=result["period_end"],
        country=result["country"],
        granularity=result["granularity"],
        main_domain_only=result["main_domain_only"],
        total_visits=result["total_visits"],
        global_rank=result["global_rank"],
        visits_series_json=result["visits_series"],
        global_rank_series_json=result["global_rank_series"],
        metric_status_json=result["metric_status"],
        fetch_status=result["fetch_status"],
        provider_last_updated=result["provider_last_updated"],
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    normalize_traffic_observations(db, snapshot)
    return snapshot


def _period(value: str) -> tuple[date, date] | None:
    try:
        parsed = datetime.strptime(value[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        try:
            parsed = datetime.strptime(value[:7], "%Y-%m").date()
        except (TypeError, ValueError):
            return None
    start = parsed.replace(day=1)
    end = parsed.replace(day=monthrange(parsed.year, parsed.month)[1])
    return start, end


def _provider_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed


def normalize_traffic_observations(
    db: Session,
    snapshot: models.TrafficSnapshot,
) -> list[models.TrafficObservation]:
    """Normalize provider series while retaining the raw snapshot unchanged."""

    metric_rows = (
        ("monthly_visits", "visits", snapshot.visits_series_json or [], "visits_per_month"),
        ("global_rank", "global_rank", snapshot.global_rank_series_json or [], "rank"),
    )
    records: list[models.TrafficObservation] = []
    metric_status = snapshot.metric_status_json or {}
    for metric_key, provider_key, rows, unit in metric_rows:
        provider_status = metric_status.get(
            "total_visits" if metric_key == "monthly_visits" else "global_rank",
            {},
        ).get("status", snapshot.fetch_status)
        for row in rows:
            if not isinstance(row, dict):
                continue
            parsed_period = _period(str(row.get("date") or ""))
            if not parsed_period:
                continue
            try:
                value = Decimal(str(row.get(provider_key)))
            except (InvalidOperation, TypeError, ValueError):
                continue
            if not value.is_finite() or value < 0:
                continue
            period_start, period_end = parsed_period
            key_payload = "|".join(
                (
                    str(snapshot.workspace_id),
                    str(snapshot.id),
                    snapshot.provider,
                    snapshot.domain,
                    metric_key,
                    period_start.isoformat(),
                    snapshot.country,
                )
            )
            observation_key = sha256_text(key_payload)
            record = (
                db.query(models.TrafficObservation)
                .filter(
                    models.TrafficObservation.workspace_id == snapshot.workspace_id,
                    models.TrafficObservation.observation_key == observation_key,
                )
                .first()
            )
            if not record:
                record = models.TrafficObservation(
                    workspace_id=snapshot.workspace_id,
                    observation_key=observation_key,
                )
                db.add(record)
            record.store_id = snapshot.store_id
            record.traffic_snapshot_id = snapshot.id
            record.domain = snapshot.domain
            record.provider = snapshot.provider
            record.metric_key = metric_key
            record.period_start = period_start
            record.period_end = period_end
            record.country = snapshot.country
            record.dimension_type = ""
            record.dimension_value = ""
            record.value_numeric = value
            record.value_text = None
            record.unit = unit
            record.data_kind = "estimated"
            record.status = provider_status
            record.confidence_score = Decimal("0.65") if provider_status == "success" else Decimal("0.45")
            record.observed_at = datetime.combine(period_end, datetime.min.time())
            record.retrieved_at = snapshot.fetched_at
            record.provider_last_updated_at = _provider_datetime(snapshot.provider_last_updated)
            record.source_payload_json = row
            records.append(record)
    db.commit()
    for record in records:
        db.refresh(record)
    return records


def traffic_snapshot_payload(snapshot: models.TrafficSnapshot, *, include_series: bool = True) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": snapshot.id,
        "store_id": snapshot.store_id,
        "domain": snapshot.domain,
        "provider": snapshot.provider,
        "data_kind": "estimated",
        "fetched_at": snapshot.fetched_at,
        "period_start": snapshot.period_start,
        "period_end": snapshot.period_end,
        "country": snapshot.country,
        "granularity": snapshot.granularity,
        "main_domain_only": snapshot.main_domain_only,
        "total_visits": snapshot.total_visits,
        "global_rank": snapshot.global_rank,
        "fetch_status": snapshot.fetch_status,
        "metric_status": snapshot.metric_status_json or {},
        "provider_last_updated": snapshot.provider_last_updated,
        "data_notice": TRAFFIC_DATA_NOTICE,
    }
    if include_series:
        payload["visits_series"] = snapshot.visits_series_json or []
        payload["global_rank_series"] = snapshot.global_rank_series_json or []
    return payload
