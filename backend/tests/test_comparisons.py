from fastapi.testclient import TestClient

from app.db import models
from app.db.base import Base
from app.db.session import SessionLocal
from app.main import app


client = TestClient(app)


def test_product_comparison_uses_known_corpus_and_explicit_unavailable_fields():
    db = SessionLocal()
    try:
        Base.metadata.create_all(bind=db.get_bind())
    finally:
        db.close()
    token = client.post("/auth/local").json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.email == "local@northstar").one()
        workspace = db.query(models.Workspace).filter(models.Workspace.owner_user_id == user.id).one()
        stores = [
            models.Store(workspace_id=workspace.id, domain="compare-one.example", platform_guess=models.PlatformGuess.shopify),
            models.Store(workspace_id=workspace.id, domain="compare-two.example", platform_guess=models.PlatformGuess.woocommerce),
        ]
        db.add_all(stores)
        db.flush()
        products = [
            models.Product(workspace_id=workspace.id, store_id=stores[0].id, canonical_url="https://compare-one.example/products/a", title="Comparison A", currency="USD"),
            models.Product(workspace_id=workspace.id, store_id=stores[1].id, canonical_url="https://compare-two.example/products/b", title="Comparison B", currency="USD"),
        ]
        db.add_all(products)
        db.flush()
        db.add_all([
            models.ProductSnapshot(product_id=products[0].id, title=products[0].title, price_min=39, price_max=49, available=True, variant_count=3, images_json=["a", "b"], content_hash="compare-a"),
            models.ProductSnapshot(product_id=products[1].id, title=products[1].title, price_min=55, price_max=55, available=None, variant_count=1, images_json=["c"], content_hash="compare-b"),
        ])
        db.commit()
        product_ids = [product.id for product in products]
    finally:
        db.close()

    response = client.get(
        f"/comparisons/products?ids={product_ids[0]},{product_ids[1]}", headers=headers
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["known_corpus"]["selected_product_count"] == 2
    assert [row["product_id"] for row in body["products"]] == product_ids
    assert body["products"][0]["price_low"] == 39
    assert body["products"][0]["image_count"] == 2
    assert "verified sales" in body["products"][0]["unavailable"]
    assert body["products"][0]["economics"] is None
    assert "private Northstar corpus" in body["data_notice"]

    too_few = client.get(f"/comparisons/products?ids={product_ids[0]}", headers=headers)
    assert too_few.status_code == 422
    missing = client.get(
        f"/comparisons/products?ids={product_ids[0]},999999", headers=headers
    )
    assert missing.status_code == 404
