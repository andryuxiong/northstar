from uuid import uuid4

from app.db import models
from app.db.base import Base
from app.db.session import SessionLocal
from app.services.product_identity import (
    consolidate_shopify_locale_products,
    normalize_shopify_product_url,
)


def setup_module(module):
    db = SessionLocal()
    Base.metadata.create_all(bind=db.get_bind())
    db.close()


def test_shopify_locale_url_normalization_keeps_one_handle_identity():
    assert (
        normalize_shopify_product_url("https://shop.example/hi/products/widget?variant=1")
        == "https://shop.example/products/widget"
    )
    assert (
        normalize_shopify_product_url("https://shop.example/en-US/products/widget")
        == "https://shop.example/products/widget"
    )
    assert (
        normalize_shopify_product_url("https://shop.example/products/another-widget")
        == "https://shop.example/products/another-widget"
    )


def test_locale_product_consolidation_preserves_snapshots_sources_and_edges():
    db = SessionLocal()
    try:
        slug = uuid4().hex
        user = models.User(email=f"locale-{slug}@example.com", password_hash="x")
        db.add(user)
        db.flush()
        workspace = models.Workspace(name="Locale", owner_user_id=user.id)
        db.add(workspace)
        db.flush()
        store = models.Store(
            workspace_id=workspace.id,
            domain=f"{slug}.example.com",
            platform_guess=models.PlatformGuess.shopify,
        )
        db.add(store)
        db.flush()
        source = models.SourceUrl(
            workspace_id=workspace.id,
            url=f"https://{store.domain}/",
            type=models.SourceUrlType.store,
        )
        localized_source = models.SourceUrl(
            workspace_id=workspace.id,
            url=f"https://{store.domain}/hi/products/widget",
            type=models.SourceUrlType.product,
        )
        db.add_all([source, localized_source])
        db.flush()
        base = models.Product(
            workspace_id=workspace.id,
            store_id=store.id,
            canonical_url=f"https://{store.domain}/products/widget",
            title="Widget",
            currency="USD",
        )
        localized = models.Product(
            workspace_id=workspace.id,
            store_id=store.id,
            canonical_url=f"https://{store.domain}/hi/products/widget",
            title="Widget localized",
            currency="USD",
        )
        db.add_all([base, localized])
        db.flush()
        db.add_all(
            [
                models.ProductSnapshot(
                    product_id=base.id,
                    title=base.title,
                    price_min=30,
                    price_max=30,
                    available=True,
                    variant_count=1,
                    images_json=[],
                    raw_extracted_json={"variants": [{"price": 30}]},
                    content_hash=f"{slug}-base",
                ),
                models.ProductSnapshot(
                    product_id=localized.id,
                    title=localized.title,
                    price_min=32,
                    price_max=32,
                    available=True,
                    variant_count=1,
                    images_json=[],
                    raw_extracted_json={"variants": [{"price": 32}]},
                    content_hash=f"{slug}-localized",
                ),
                models.ProductVariant(
                    product_id=localized.id,
                    title="Localized current variant",
                    price=32,
                    available=True,
                ),
                models.LandingProductEdge(landing_url_id=source.id, product_id=base.id),
                models.LandingProductEdge(landing_url_id=source.id, product_id=localized.id),
            ]
        )
        db.commit()

        result = consolidate_shopify_locale_products(db, store_id=store.id)
        assert result.groups_merged == 1
        assert result.products_removed == 1
        assert result.snapshots_preserved == 1
        products = db.query(models.Product).filter(models.Product.store_id == store.id).all()
        assert len(products) == 1
        assert products[0].canonical_url == f"https://{store.domain}/products/widget"
        assert db.query(models.ProductSnapshot).filter(models.ProductSnapshot.product_id == products[0].id).count() == 2
        assert db.query(models.ProductVariant).filter(models.ProductVariant.product_id == products[0].id).count() == 1
        assert db.query(models.LandingProductEdge).filter(models.LandingProductEdge.product_id == products[0].id).count() == 1
        assert db.query(models.SourceUrl).filter(models.SourceUrl.workspace_id == workspace.id).count() == 2
    finally:
        db.close()

