"""Conservative same-store product identity helpers.

Shopify emits locale-prefixed URLs such as ``/hi/products/widget`` for the
same product handle. Within one store, an identical Shopify handle is strong
enough to normalize as one product entity. Raw source URLs and every snapshot
remain intact and are reassigned to the canonical product.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

from sqlalchemy.orm import Session

from app.db import models


_SHOPIFY_PRODUCT_PATH = re.compile(
    r"^/(?:[a-z]{2}(?:-[a-z]{2})?/)?products/([^/?#]+)",
    re.IGNORECASE,
)


def normalize_shopify_product_url(url: str) -> str:
    parsed = urlparse(url)
    match = _SHOPIFY_PRODUCT_PATH.match(parsed.path or "")
    if not parsed.hostname or not match:
        return url
    host = parsed.hostname.lower().rstrip(".")
    if parsed.port:
        host = f"{host}:{parsed.port}"
    return urlunparse(
        (
            parsed.scheme.lower() if parsed.scheme else "https",
            host,
            f"/products/{match.group(1)}",
            "",
            "",
            "",
        )
    )


@dataclass(frozen=True)
class ConsolidationResult:
    groups_merged: int
    products_removed: int
    snapshots_preserved: int


def _merge_group(
    db: Session,
    products: list[models.Product],
    canonical_url: str,
) -> tuple[models.Product, int, int]:
    keeper = next(
        (product for product in products if product.canonical_url == canonical_url),
        min(products, key=lambda product: product.id),
    )
    newest = max(products, key=lambda product: product.last_seen_at)
    duplicate_ids = [product.id for product in products if product.id != keeper.id]
    if not duplicate_ids:
        if keeper.canonical_url != canonical_url:
            keeper.canonical_url = canonical_url
            db.commit()
        return keeper, 0, 0

    all_variant_rows = (
        db.query(models.ProductVariant)
        .filter(models.ProductVariant.product_id.in_([product.id for product in products]))
        .all()
    )
    variant_source_id = (
        max(all_variant_rows, key=lambda row: row.last_seen_at).product_id
        if all_variant_rows
        else None
    )
    variant_rows = [row for row in all_variant_rows if row.product_id == variant_source_id]
    variants = [
        {
            "sku": row.sku,
            "title": row.title,
            "price": row.price,
            "compare_at_price": row.compare_at_price,
            "available": row.available,
            "last_seen_at": row.last_seen_at,
        }
        for row in variant_rows
    ]
    snapshot_count = (
        db.query(models.ProductSnapshot)
        .filter(models.ProductSnapshot.product_id.in_(duplicate_ids))
        .count()
    )

    db.query(models.ProductVariant).filter(
        models.ProductVariant.product_id.in_([product.id for product in products])
    ).delete(synchronize_session="fetch")
    db.flush()
    db.query(models.ProductSnapshot).filter(
        models.ProductSnapshot.product_id.in_(duplicate_ids)
    ).update({models.ProductSnapshot.product_id: keeper.id}, synchronize_session=False)

    for edge in (
        db.query(models.LandingProductEdge)
        .filter(models.LandingProductEdge.product_id.in_(duplicate_ids))
        .all()
    ):
        exists = (
            db.query(models.LandingProductEdge.id)
            .filter(
                models.LandingProductEdge.landing_url_id == edge.landing_url_id,
                models.LandingProductEdge.product_id == keeper.id,
            )
            .first()
        )
        if exists:
            db.delete(edge)
        else:
            edge.product_id = keeper.id

    db.query(models.DerivedInsight).filter(
        models.DerivedInsight.product_id.in_(duplicate_ids)
    ).update({models.DerivedInsight.product_id: keeper.id}, synchronize_session=False)
    db.query(models.EvidenceRecord).filter(
        models.EvidenceRecord.product_id.in_(duplicate_ids)
    ).update({models.EvidenceRecord.product_id: keeper.id}, synchronize_session=False)
    db.query(models.TagAssignment).filter(
        models.TagAssignment.entity_type == models.TagEntityType.product,
        models.TagAssignment.entity_id.in_(duplicate_ids),
    ).update({models.TagAssignment.entity_id: keeper.id}, synchronize_session=False)
    db.query(models.Signal).filter(
        models.Signal.entity_type == models.SignalEntityType.product,
        models.Signal.entity_id.in_(duplicate_ids),
    ).update({models.Signal.entity_id: keeper.id}, synchronize_session=False)
    db.query(models.Score).filter(
        models.Score.entity_type == models.SignalEntityType.product,
        models.Score.entity_id.in_(duplicate_ids),
    ).update({models.Score.entity_id: keeper.id}, synchronize_session=False)
    db.query(models.AlertRule).filter(
        models.AlertRule.entity_type == models.SignalEntityType.product,
        models.AlertRule.entity_id.in_(duplicate_ids),
    ).update({models.AlertRule.entity_id: keeper.id}, synchronize_session=False)

    keeper.title = newest.title or keeper.title
    keeper.description = newest.description or keeper.description
    keeper.currency = newest.currency or keeper.currency
    keeper.created_at = min(product.created_at for product in products)
    keeper.last_seen_at = max(product.last_seen_at for product in products)
    for product in products:
        if product.id != keeper.id:
            db.delete(product)
    db.flush()
    keeper.canonical_url = canonical_url
    for values in variants:
        db.add(models.ProductVariant(product_id=keeper.id, **values))
    db.commit()
    db.refresh(keeper)
    return keeper, len(duplicate_ids), snapshot_count


def consolidate_shopify_locale_products(
    db: Session,
    *,
    store_id: int,
) -> ConsolidationResult:
    products = (
        db.query(models.Product)
        .filter(models.Product.store_id == store_id)
        .order_by(models.Product.id.asc())
        .all()
    )
    groups: dict[str, list[models.Product]] = {}
    for product in products:
        key = normalize_shopify_product_url(product.canonical_url)
        groups.setdefault(key, []).append(product)
    groups_merged = 0
    removed = 0
    snapshots = 0
    for canonical_url, group in groups.items():
        if len(group) < 2:
            product = group[0]
            if product.canonical_url != canonical_url:
                product.canonical_url = canonical_url
                db.commit()
            continue
        _, group_removed, group_snapshots = _merge_group(db, group, canonical_url)
        groups_merged += 1
        removed += group_removed
        snapshots += group_snapshots
    return ConsolidationResult(groups_merged, removed, snapshots)


def merge_shopify_redirect_aliases(
    db: Session,
    *,
    products: list[models.Product],
    canonical_url: str,
) -> models.Product:
    """Merge products proven equivalent by an HTTP/canonical redirect."""

    unique = {product.id: product for product in products}
    keeper, _, _ = _merge_group(db, list(unique.values()), canonical_url)
    return keeper


def find_product_by_shopify_identity(
    db: Session,
    *,
    workspace_id: int,
    store_id: int,
    canonical_url: str,
    external_id: str | int | None = None,
) -> models.Product | None:
    normalized = normalize_shopify_product_url(canonical_url)
    matches = [
        product
        for product in db.query(models.Product)
        .filter(
            models.Product.workspace_id == workspace_id,
            models.Product.store_id == store_id,
        )
        .all()
        if normalize_shopify_product_url(product.canonical_url) == normalized
    ]
    if external_id is not None:
        external_text = str(external_id)
        identity_product_ids = {
            snapshot.product_id
            for snapshot in db.query(models.ProductSnapshot)
            .join(models.Product)
            .filter(models.Product.store_id == store_id)
            .all()
            if str((snapshot.raw_extracted_json or {}).get("external_id") or "")
            == external_text
        }
        for product in (
            db.query(models.Product)
            .filter(models.Product.id.in_(identity_product_ids))
            .all()
            if identity_product_ids
            else []
        ):
            if product.id not in {item.id for item in matches}:
                matches.append(product)
    if not matches:
        return None
    keeper, _, _ = _merge_group(db, matches, normalized)
    return keeper
