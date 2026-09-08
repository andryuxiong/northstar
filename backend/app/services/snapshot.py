from typing import Any, Optional
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.db import models
from app.core.config import settings
from app.services.storage import write_html, write_json, download_images
from app.utils.hashing import sha256_text


def compute_content_hash(html: str) -> str:
    normalized = " ".join(html.split())
    return sha256_text(normalized)


def save_product_snapshot(
    db: Session,
    product: models.Product,
    html: str,
    extracted: dict,
) -> models.ProductSnapshot:
    domain = urlparse(product.canonical_url).netloc
    content_hash = compute_content_hash(html)
    write_html(domain, content_hash, html)
    write_json(domain, content_hash, extracted, "product")
    images = extracted.get("images") or []
    if settings.mirror_product_images and isinstance(images, list) and images:
        download_images(domain, content_hash, images)

    prices = [v.get("price") for v in extracted.get("variants", []) if v.get("price") is not None]
    available_values = [v.get("available") for v in extracted.get("variants", []) if v.get("available") is not None]

    snapshot = models.ProductSnapshot(
        product_id=product.id,
        title=extracted.get("title"),
        price_min=min(prices) if prices else None,
        price_max=max(prices) if prices else None,
        available=any(available_values) if available_values else None,
        variant_count=len(extracted.get("variants", [])),
        images_json=extracted.get("images"),
        raw_extracted_json=extracted,
        content_hash=content_hash,
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


def save_landing_snapshot(
    db: Session,
    source_url: models.SourceUrl,
    html: str,
    extracted_product_urls: Optional[list[str]] = None,
    final_url: Optional[str] = None,
) -> models.LandingPageSnapshot:
    domain = urlparse(source_url.url).netloc
    content_hash = compute_content_hash(html)
    write_html(domain, content_hash, html)
    write_json(domain, content_hash, {"product_urls": extracted_product_urls or []}, "landing")

    snap = models.LandingPageSnapshot(
        url_id=source_url.id,
        final_url=final_url,
        html_hash=content_hash,
        extracted_product_urls_json=extracted_product_urls or [],
    )
    db.add(snap)
    db.commit()
    db.refresh(snap)
    return snap
