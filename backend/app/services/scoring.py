from datetime import datetime
from typing import Any, Tuple

from sqlalchemy.orm import Session

from app.db import models


def _upsert_score(db: Session, entity_type: models.SignalEntityType, entity_id: int, score_type: models.ScoreType, score_value: float, confidence: float, components: dict[str, Any]):
    db.query(models.Score).filter(
        models.Score.entity_type == entity_type,
        models.Score.entity_id == entity_id,
        models.Score.score_type == score_type,
    ).delete()
    score = models.Score(
        entity_type=entity_type,
        entity_id=entity_id,
        score_type=score_type,
        score_value=score_value,
        confidence=confidence,
        components_json=components,
        computed_at=datetime.utcnow(),
    )
    db.add(score)
    db.commit()


def compute_product_scores(db: Session, product_id: int) -> list[models.Score]:
    signals = db.query(models.Signal).filter(
        models.Signal.entity_type == models.SignalEntityType.product,
        models.Signal.entity_id == product_id,
    ).all()
    sig_map = {s.signal_type: s.value_json or {} for s in signals}

    price_changes = sig_map.get("price_change_velocity", {}).get("changes_30d", 0) or 0
    stock_flips = sig_map.get("stock_volatility", {}).get("flips_30d", 0) or 0
    new_variants = sig_map.get("new_variant_introductions", {}).get("count_30d", 0) or 0
    discount_amount = sig_map.get("discount_depth", {}).get("amount") or 0
    ads_linking = sig_map.get("catalog_pressure", {}).get("ads_linking", 0) or 0
    dup_title = sig_map.get("cross_store_duplication", {}).get("similar_title_count", 0) or 0

    momentum = (
        min(price_changes * 8, 40)
        + min(stock_flips * 6, 20)
        + min(new_variants * 10, 30)
    )
    winner = (
        min(ads_linking * 12, 40)
        + min(discount_amount * 2, 30)
        + max(0, 20 - dup_title * 2)
    )

    momentum = max(0, min(100, momentum))
    winner = max(0, min(100, winner))

    snapshot_times = [
        row[0]
        for row in db.query(models.ProductSnapshot.fetched_at)
        .filter(models.ProductSnapshot.product_id == product_id)
        .order_by(models.ProductSnapshot.fetched_at.asc())
        .all()
    ]
    snapshot_count = len(snapshot_times)
    observed_days = (
        max(0.0, (snapshot_times[-1] - snapshot_times[0]).total_seconds() / 86400)
        if snapshot_count >= 2
        else 0.0
    )
    momentum_confidence = min(
        1.0,
        0.25 + min(snapshot_count, 5) * 0.1 + min(observed_days / 30, 1.0) * 0.25,
    )
    has_trend_history = snapshot_count >= 2 and observed_days >= 1.0
    if has_trend_history:
        _upsert_score(
            db,
            models.SignalEntityType.product,
            product_id,
            models.ScoreType.momentum,
            momentum,
            momentum_confidence,
            {
                "price_changes_30d": price_changes,
                "stock_flips_30d": stock_flips,
                "new_variants_30d": new_variants,
                "snapshot_count": snapshot_count,
                "observed_days": observed_days,
            },
        )
    else:
        db.query(models.Score).filter(
            models.Score.entity_type == models.SignalEntityType.product,
            models.Score.entity_id == product_id,
            models.Score.score_type == models.ScoreType.momentum,
        ).delete()
        db.commit()

    winner_confidence = min(0.85, 0.25 + min(snapshot_count, 3) * 0.1 + min(len(signals), 4) * 0.05)
    _upsert_score(
        db,
        models.SignalEntityType.product,
        product_id,
        models.ScoreType.winner,
        winner,
        winner_confidence,
        {
            "ads_linking": ads_linking,
            "discount_amount": discount_amount,
            "duplicate_titles": dup_title,
            "snapshot_count": snapshot_count,
        },
    )

    return (
        db.query(models.Score)
        .filter(models.Score.entity_type == models.SignalEntityType.product, models.Score.entity_id == product_id)
        .all()
    )


def compute_ad_scores(db: Session, ad_id: int) -> list[models.Score]:
    signals = db.query(models.Signal).filter(
        models.Signal.entity_type == models.SignalEntityType.ad,
        models.Signal.entity_id == ad_id,
    ).all()
    longevity = 0
    for s in signals:
        if s.signal_type == "ad_longevity":
            longevity = s.value_json.get("days", 0) if s.value_json else 0

    score_value = min(100, longevity * 5)
    confidence = min(1.0, 0.2 + len(signals) * 0.2)
    _upsert_score(
        db,
        models.SignalEntityType.ad,
        ad_id,
        models.ScoreType.longevity_proxy,
        score_value,
        confidence,
        {"days": longevity},
    )
    return (
        db.query(models.Score)
        .filter(models.Score.entity_type == models.SignalEntityType.ad, models.Score.entity_id == ad_id)
        .all()
    )
