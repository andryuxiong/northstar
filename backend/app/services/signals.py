from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.db import models


def _upsert_signal(db: Session, entity_type: models.SignalEntityType, entity_id: int, signal_type: str, value: dict[str, Any]):
    db.query(models.Signal).filter(
        models.Signal.entity_type == entity_type,
        models.Signal.entity_id == entity_id,
        models.Signal.signal_type == signal_type,
    ).delete()
    signal = models.Signal(
        entity_type=entity_type,
        entity_id=entity_id,
        signal_type=signal_type,
        value_json=value,
        computed_at=datetime.utcnow(),
    )
    db.add(signal)
    db.commit()


def compute_product_signals(db: Session, product_id: int) -> list[models.Signal]:
    now = datetime.utcnow()
    cutoff = now - timedelta(days=30)
    snaps = (
        db.query(models.ProductSnapshot)
        .filter(models.ProductSnapshot.product_id == product_id, models.ProductSnapshot.fetched_at >= cutoff)
        .order_by(models.ProductSnapshot.fetched_at.asc())
        .all()
    )

    price_changes = 0
    stock_flips = 0
    new_variants = 0
    last_price = None
    last_available = None
    last_variant_count = None

    for s in snaps:
        if s.price_min is not None and last_price is not None and s.price_min != last_price:
            price_changes += 1
        if s.available is not None and last_available is not None and s.available != last_available:
            stock_flips += 1
        if s.variant_count is not None and last_variant_count is not None and s.variant_count > last_variant_count:
            new_variants += 1
        if s.price_min is not None:
            last_price = s.price_min
        if s.available is not None:
            last_available = s.available
        if s.variant_count is not None:
            last_variant_count = s.variant_count

    _upsert_signal(
        db,
        models.SignalEntityType.product,
        product_id,
        "price_change_velocity",
        {"changes_30d": price_changes},
    )
    _upsert_signal(
        db,
        models.SignalEntityType.product,
        product_id,
        "stock_volatility",
        {"flips_30d": stock_flips},
    )
    _upsert_signal(
        db,
        models.SignalEntityType.product,
        product_id,
        "new_variant_introductions",
        {"count_30d": new_variants},
    )

    latest = snaps[-1] if snaps else None
    discount_depth = None
    if latest and latest.raw_extracted_json:
        variants = latest.raw_extracted_json.get("variants", [])
        if variants:
            v = variants[0]
            if v.get("compare_at_price") and v.get("price"):
                discount_depth = max(0.0, float(v["compare_at_price"]) - float(v["price"]))
    _upsert_signal(
        db,
        models.SignalEntityType.product,
        product_id,
        "discount_depth",
        {"amount": discount_depth},
    )

    ad_count = (
        db.query(models.AdLandingEdge)
        .join(models.LandingProductEdge, models.LandingProductEdge.landing_url_id == models.AdLandingEdge.url_id)
        .filter(models.LandingProductEdge.product_id == product_id)
        .count()
    )
    _upsert_signal(
        db,
        models.SignalEntityType.product,
        product_id,
        "catalog_pressure",
        {"ads_linking": ad_count},
    )

    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    title = (product.title or "").strip().lower() if product else ""
    dup_count = 0
    if title:
        dup_count = (
            db.query(models.Product)
            .filter(models.Product.id != product_id, models.Product.title.ilike(title))
            .count()
        )
    _upsert_signal(
        db,
        models.SignalEntityType.product,
        product_id,
        "cross_store_duplication",
        {"similar_title_count": dup_count},
    )

    return (
        db.query(models.Signal)
        .filter(models.Signal.entity_type == models.SignalEntityType.product, models.Signal.entity_id == product_id)
        .all()
    )


def compute_ad_signals(db: Session, ad_id: int) -> list[models.Signal]:
    ad = db.query(models.Ad).filter(models.Ad.id == ad_id).first()
    if not ad:
        return []
    longevity_days = (ad.last_seen_at - ad.first_seen_at).days
    _upsert_signal(
        db,
        models.SignalEntityType.ad,
        ad_id,
        "ad_longevity",
        {"days": longevity_days},
    )
    return (
        db.query(models.Signal)
        .filter(models.Signal.entity_type == models.SignalEntityType.ad, models.Signal.entity_id == ad_id)
        .all()
    )
