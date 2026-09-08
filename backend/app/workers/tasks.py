import logging
from datetime import datetime
from urllib.parse import urljoin, urlparse

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db import models
from app.services.classifier import classify_url, extract_domain
from app.services.crawler import fetch_url
from app.services.parsers.shopify import ShopifyParser
from app.services.parsers.generic import GenericProductParser
from app.services.snapshot import save_product_snapshot, save_landing_snapshot
from app.services.extract import extract_product_urls
from app.services.store_profile import analyze_store_homepage, persist_store_homepage_analysis
from app.services.product_identity import (
    find_product_by_shopify_identity,
    merge_shopify_redirect_aliases,
    normalize_shopify_product_url,
)
from app.services.signals import compute_product_signals
from app.services.scoring import compute_product_scores, compute_ad_scores
from app.services.integration_config import get_meta_credential
from app.services.meta_ads import (
    MetaAdsAPIError,
    effective_meta_fields,
    persist_meta_ads,
    search_ads_archive,
)
from app.workers.runner import enqueue
from app.core.config import settings
from app.utils.urls import normalize_public_url

logger = logging.getLogger(__name__)


def fetch_url_task(source_url_id: int):
    db = SessionLocal()
    try:
        source = db.query(models.SourceUrl).filter(models.SourceUrl.id == source_url_id).first()
        if not source:
            return
        source.fetch_status = "fetching"
        db.commit()
        try:
            html, final_url, status = fetch_url(source.url)
            source.last_fetched_at = datetime.utcnow()
            source.last_http_status = status
            if not html:
                source.fetch_status = "failed"
                db.commit()
                raise RuntimeError(f"Public fetch failed with HTTP status {status}")

            if source.type == models.SourceUrlType.product:
                redirected_type = classify_url(final_url) if final_url else source.type
                if redirected_type != models.SourceUrlType.product:
                    source.type = redirected_type
                    db.commit()
                    _handle_landing(db, source, html, final_url)
                else:
                    _handle_product(db, source, html, final_url)
            elif source.type in [models.SourceUrlType.landing_page, models.SourceUrlType.collection]:
                _handle_landing(db, source, html, final_url)
            elif source.type == models.SourceUrlType.sitemap:
                _handle_sitemap(db, source, html)
            elif source.type == models.SourceUrlType.store:
                _handle_store_homepage(db, source, html, final_url)

            source.fetch_status = "fetched"
            source.last_fetched_at = datetime.utcnow()
            db.commit()
            return {"source_url_id": source.id, "status": "fetched", "http_status": status}
        except Exception:
            # A successful HTTP request followed by a parse/persistence failure
            # is not a successful source collection.
            source.fetch_status = "failed"
            source.last_fetched_at = datetime.utcnow()
            db.commit()
            raise
    finally:
        db.close()


def crawl_store_sitemap_task(store_id: int):
    db = SessionLocal()
    try:
        store = db.query(models.Store).filter(models.Store.id == store_id).first()
        if not store:
            return
        homepage_source = (
            db.query(models.SourceUrl)
            .filter(
                models.SourceUrl.workspace_id == store.workspace_id,
                models.SourceUrl.type == models.SourceUrlType.store,
            )
            .all()
        )
        homepage_source = next(
            (source for source in homepage_source if extract_domain(source.url) == store.domain),
            None,
        )
        if not homepage_source:
            homepage_source = models.SourceUrl(
                workspace_id=store.workspace_id,
                url=f"https://{store.domain}/",
                type=models.SourceUrlType.store,
                fetch_status="queued",
            )
            db.add(homepage_source)
            db.commit()
            db.refresh(homepage_source)
        else:
            homepage_source.fetch_status = "queued"
            db.commit()
        enqueue(fetch_url_task, homepage_source.id, label=f"Fetch homepage for {store.domain}")

        sitemap_url = f"https://{store.domain}/sitemap.xml"
        sitemap_source = (
            db.query(models.SourceUrl)
            .filter(models.SourceUrl.workspace_id == store.workspace_id, models.SourceUrl.url == sitemap_url)
            .first()
        )
        if not sitemap_source:
            sitemap_source = models.SourceUrl(
                workspace_id=store.workspace_id,
                url=sitemap_url,
                type=models.SourceUrlType.sitemap,
                fetch_status="queued",
            )
            db.add(sitemap_source)
            db.commit()
            db.refresh(sitemap_source)
        else:
            sitemap_source.fetch_status = "queued"
            db.commit()
        enqueue(fetch_url_task, sitemap_source.id, label=f"Fetch sitemap for {store.domain}")
        return {
            "store_id": store.id,
            "homepage_source_id": homepage_source.id,
            "sitemap_source_id": sitemap_source.id,
            "status": "collection_queued",
        }
    finally:
        db.close()


def _handle_product(
    db: Session,
    source: models.SourceUrl,
    html: str,
    final_url: str | None = None,
) -> None:
    domain = extract_domain(source.url)
    store = db.query(models.Store).filter(models.Store.workspace_id == source.workspace_id, models.Store.domain == domain).first()
    if not store:
        store = models.Store(workspace_id=source.workspace_id, domain=domain, platform_guess=models.PlatformGuess.unknown)
        db.add(store)
        db.commit()
        db.refresh(store)

    is_shopify = ShopifyParser.is_shopify(html)
    parser = ShopifyParser(html) if is_shopify else GenericProductParser(html)
    if is_shopify and store.platform_guess != models.PlatformGuess.shopify:
        store.platform_guess = models.PlatformGuess.shopify
        db.commit()
    extracted = parser.parse() or {}

    canonical_candidate = urljoin(
        final_url or source.url,
        parser.canonical() or final_url or source.url,
    )
    if extract_domain(canonical_candidate).removeprefix("www.") != domain.removeprefix("www."):
        canonical_candidate = source.url
    canonical_url = normalize_public_url(canonical_candidate)
    if is_shopify:
        canonical_url = normalize_shopify_product_url(canonical_url)
        product = find_product_by_shopify_identity(
            db,
            workspace_id=source.workspace_id,
            store_id=store.id,
            canonical_url=canonical_url,
            external_id=extracted.get("external_id"),
        )
        source_identity_url = normalize_shopify_product_url(normalize_public_url(source.url))
        source_product = (
            db.query(models.Product)
            .filter(
                models.Product.workspace_id == source.workspace_id,
                models.Product.store_id == store.id,
                models.Product.canonical_url == source_identity_url,
            )
            .first()
        )
        if product is None and source_product:
            product = source_product
            product.canonical_url = canonical_url
            db.commit()
        elif product and source_product and source_product.id != product.id:
            product = merge_shopify_redirect_aliases(
                db,
                products=[product, source_product],
                canonical_url=canonical_url,
            )
    else:
        product = (
            db.query(models.Product)
            .filter(
                models.Product.workspace_id == source.workspace_id,
                models.Product.canonical_url == canonical_url,
            )
            .first()
        )
    if not product:
        product = models.Product(
            workspace_id=source.workspace_id,
            store_id=store.id,
            canonical_url=canonical_url,
            title=extracted.get("title") or parser.title() or canonical_url,
            description=extracted.get("description"),
            currency=extracted.get("currency"),
            last_seen_at=datetime.utcnow(),
        )
        db.add(product)
        db.commit()
        db.refresh(product)
    else:
        product.title = extracted.get("title") or product.title
        product.description = extracted.get("description") or product.description
        product.currency = extracted.get("currency") or product.currency
        product.last_seen_at = datetime.utcnow()
        db.commit()

    db.query(models.ProductVariant).filter(models.ProductVariant.product_id == product.id).delete()
    for v in extracted.get("variants", []) or []:
        variant = models.ProductVariant(
            product_id=product.id,
            sku=v.get("sku"),
            title=v.get("title") or product.title,
            price=v.get("price"),
            compare_at_price=v.get("compare_at_price"),
            available=bool(v.get("available", True)),
            last_seen_at=datetime.utcnow(),
        )
        db.add(variant)
    db.commit()

    save_product_snapshot(db, product, html, extracted)
    _reconcile_product_landing_edges(db, product)
    compute_product_signals(db, product.id)
    compute_product_scores(db, product.id)


def _handle_store_homepage(
    db: Session,
    source: models.SourceUrl,
    html: str,
    final_url: str | None,
) -> None:
    domain = extract_domain(final_url or source.url)
    store = (
        db.query(models.Store)
        .filter(models.Store.workspace_id == source.workspace_id, models.Store.domain == domain)
        .first()
    )
    if not store:
        # Redirects between bare/www hosts are common. Keep the submitted store
        # when present rather than creating a second record for the redirect.
        submitted_domain = extract_domain(source.url)
        store = (
            db.query(models.Store)
            .filter(models.Store.workspace_id == source.workspace_id, models.Store.domain == submitted_domain)
            .first()
        )
    if not store:
        store = models.Store(
            workspace_id=source.workspace_id,
            domain=domain,
            platform_guess=models.PlatformGuess.unknown,
        )
        db.add(store)
        db.commit()
        db.refresh(store)

    homepage_url = final_url or source.url
    product_urls = extract_product_urls(homepage_url, html)
    save_landing_snapshot(db, source, html, product_urls, final_url)
    analysis = analyze_store_homepage(homepage_url, html)
    persist_store_homepage_analysis(db, store=store, source=source, analysis=analysis)

    # Homepage products are useful even when the site has no discoverable
    # sitemap. Mark them queued so a later sitemap task will not duplicate the
    # same work in this scan.
    for url in product_urls[: settings.max_products_per_scan]:
        _enqueue_product_url(db, source.workspace_id, url, label_prefix="Fetch featured product")


def _handle_landing(db: Session, source: models.SourceUrl, html: str, final_url: str | None) -> None:
    product_urls = extract_product_urls(final_url or source.url, html)
    save_landing_snapshot(db, source, html, product_urls, final_url)
    for url in product_urls:
        _enqueue_product_url(db, source.workspace_id, url, label_prefix="Fetch product")

        product = (
            db.query(models.Product)
            .filter(models.Product.workspace_id == source.workspace_id, models.Product.canonical_url == url)
            .first()
        )
        if product and not db.query(models.LandingProductEdge).filter(
            models.LandingProductEdge.landing_url_id == source.id,
            models.LandingProductEdge.product_id == product.id,
        ).first():
            edge = models.LandingProductEdge(landing_url_id=source.id, product_id=product.id)
            db.add(edge)
            db.commit()


def _handle_sitemap(db: Session, source: models.SourceUrl, xml_text: str) -> None:
    urls = extract_sitemap_urls(xml_text)
    scheduled_products = 0
    for url in urls:
        url_type = classify_url(url)
        if url_type not in [models.SourceUrlType.product, models.SourceUrlType.sitemap]:
            continue
        if url_type == models.SourceUrlType.product:
            url = normalize_shopify_product_url(url)
            if scheduled_products >= settings.max_products_per_scan:
                break
            scheduled_products += 1
        # Do not follow sitemap entries onto another host. Cross-domain public
        # URLs can be submitted explicitly, but one store scan must stay scoped
        # to the store being investigated.
        if extract_domain(url).removeprefix("www.") != extract_domain(source.url).removeprefix("www."):
            continue
        existing = db.query(models.SourceUrl).filter(models.SourceUrl.workspace_id == source.workspace_id, models.SourceUrl.url == url).first()
        if not existing:
            existing = models.SourceUrl(workspace_id=source.workspace_id, url=url, type=url_type, fetch_status="queued")
            db.add(existing)
            db.commit()
            db.refresh(existing)
        elif existing.fetch_status in {"queued", "fetching"}:
            continue
        else:
            existing.fetch_status = "queued"
            db.commit()
        enqueue(fetch_url_task, existing.id, label=f"Fetch {url_type.value} {url}")


def _enqueue_product_url(db: Session, workspace_id: int, url: str, *, label_prefix: str) -> None:
    url = normalize_shopify_product_url(url)
    product_source = (
        db.query(models.SourceUrl)
        .filter(models.SourceUrl.workspace_id == workspace_id, models.SourceUrl.url == url)
        .first()
    )
    if product_source and product_source.fetch_status in {"queued", "fetching"}:
        return
    if not product_source:
        product_source = models.SourceUrl(
            workspace_id=workspace_id,
            url=url,
            type=models.SourceUrlType.product,
            fetch_status="queued",
        )
        db.add(product_source)
        db.commit()
        db.refresh(product_source)
    else:
        product_source.fetch_status = "queued"
        db.commit()
    enqueue(fetch_url_task, product_source.id, label=f"{label_prefix} {url}")


def _reconcile_product_landing_edges(db: Session, product: models.Product) -> None:
    snapshots = (
        db.query(models.LandingPageSnapshot)
        .join(models.SourceUrl, models.LandingPageSnapshot.url_id == models.SourceUrl.id)
        .filter(models.SourceUrl.workspace_id == product.workspace_id)
        .all()
    )
    for snapshot in snapshots:
        product_urls = snapshot.extracted_product_urls_json or []
        normalized_urls = {normalize_shopify_product_url(url) for url in product_urls}
        if normalize_shopify_product_url(product.canonical_url) not in normalized_urls:
            continue
        exists = db.query(models.LandingProductEdge).filter(
            models.LandingProductEdge.landing_url_id == snapshot.url_id,
            models.LandingProductEdge.product_id == product.id,
        ).first()
        if not exists:
            db.add(models.LandingProductEdge(landing_url_id=snapshot.url_id, product_id=product.id))
    db.commit()


def extract_sitemap_urls(xml_text: str) -> list[str]:
    """Parse sitemap locations without DTD loading or entity resolution."""

    from lxml import etree

    parser = etree.XMLParser(
        resolve_entities=False,
        load_dtd=False,
        no_network=True,
        recover=True,
        huge_tree=False,
    )
    try:
        root = etree.fromstring(xml_text.encode("utf-8", errors="replace"), parser=parser)
    except (etree.XMLSyntaxError, ValueError):
        return []
    urls: list[str] = []
    for node in root.xpath("//*[local-name()='loc']"):
        if any(isinstance(child, etree._Entity) for child in node.iter()):
            continue
        text = "".join(node.itertext()).strip()
        if text:
            urls.append(text)
    return list(dict.fromkeys(urls))


def recompute_scores_task(entity_type: str, entity_id: int):
    db = SessionLocal()
    try:
        if entity_type == "product":
            compute_product_signals(db, entity_id)
            compute_product_scores(db, entity_id)
        elif entity_type == "ad":
            compute_ad_scores(db, entity_id)
    finally:
        db.close()


def scheduled_refresh_products():
    db = SessionLocal()
    try:
        products = db.query(models.Product).all()
        for p in products:
            source = db.query(models.SourceUrl).filter(models.SourceUrl.url == p.canonical_url).first()
            if source:
                enqueue(fetch_url_task, source.id, label=f"Refresh product {p.title}")
    finally:
        db.close()


def scheduled_refresh_stores():
    db = SessionLocal()
    try:
        stores = db.query(models.Store).all()
        for s in stores:
            enqueue(crawl_store_sitemap_task, s.id, label=f"Refresh store {s.domain}")
    finally:
        db.close()


def scheduled_refresh_landings():
    db = SessionLocal()
    try:
        landings = db.query(models.SourceUrl).filter(models.SourceUrl.type == models.SourceUrlType.landing_page).all()
        for l in landings:
            enqueue(fetch_url_task, l.id, label=f"Refresh landing {l.url}")
    finally:
        db.close()


def meta_ads_search_task(workspace_id: int, payload: dict):
    db = SessionLocal()
    try:
        access_token, _ = get_meta_credential()
        if not access_token:
            raise MetaAdsAPIError(
                "Configure a Meta Ad Library access token first",
                code="META_NOT_CONFIGURED",
            )

        raw_ads = search_ads_archive(
            access_token=access_token,
            ad_reached_countries=payload.get("ad_reached_countries", []),
            search_terms=payload.get("search_terms"),
            search_page_ids=payload.get("search_page_ids"),
            ad_type=payload.get("ad_type") or "ALL",
            ad_active_status=payload.get("ad_active_status"),
            ad_delivery_date_min=payload.get("ad_delivery_date_min"),
            ad_delivery_date_max=payload.get("ad_delivery_date_max"),
            fields=payload.get("fields"),
            limit=payload.get("limit") or 50,
        )
        persisted = persist_meta_ads(db, workspace_id=workspace_id, raw_ads=raw_ads)
        return {
            "provider": "meta_ad_library",
            "source": "official_meta_graph_api",
            "configured": True,
            "status": "completed",
            "graph_version": settings.meta_graph_version,
            "requested_limit": payload.get("limit") or 50,
            "fetched_count": len(raw_ads),
            "inserted_count": persisted.inserted_count,
            "updated_count": persisted.updated_count,
            "skipped_count": persisted.skipped_count,
            "effective_fields": effective_meta_fields(payload.get("fields")),
            "ad_ids": [record.id for record in persisted.records],
        }
    finally:
        db.close()
