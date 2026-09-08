from decimal import Decimal

from fastapi.testclient import TestClient

from app.db import models
from app.db.base import Base
from app.db.session import SessionLocal
from app.main import app
from app.services.product_economics import calculate_product_economics


client = TestClient(app)


def _product() -> tuple[int, dict[str, str]]:
    db = SessionLocal()
    try:
        Base.metadata.create_all(bind=db.get_bind())
    finally:
        db.close()
    token = client.post("/auth/local").json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.email.is_(None)).first()
        if not user:
            user = db.query(models.User).filter(models.User.email == "local@northstar").one()
        workspace = db.query(models.Workspace).filter(models.Workspace.owner_user_id == user.id).first()
        store = models.Store(
            workspace_id=workspace.id,
            domain="economics.example",
            platform_guess=models.PlatformGuess.shopify,
        )
        db.add(store)
        db.flush()
        product = models.Product(
            workspace_id=workspace.id,
            store_id=store.id,
            canonical_url="https://economics.example/products/test-product",
            title="Economics test product",
            currency="USD",
        )
        db.add(product)
        db.commit()
        return product.id, headers
    finally:
        db.close()


def test_unit_economics_formula_keeps_cost_sensitivity_ordered():
    result = calculate_product_economics(
        {
            "selling_price": Decimal("50"),
            "product_cost_low": Decimal("10"),
            "product_cost_high": Decimal("15"),
            "shipping_cost_low": Decimal("3"),
            "shipping_cost_high": Decimal("5"),
            "fulfillment_cost_low": Decimal("1"),
            "fulfillment_cost_high": Decimal("2"),
            "other_variable_cost_low": Decimal("0"),
            "other_variable_cost_high": Decimal("1"),
            "payment_fee_rate": Decimal("0.03"),
            "payment_fee_fixed": Decimal("0.30"),
            "refund_allowance_rate": Decimal("0.05"),
            "target_profit_margin": Decimal("0.20"),
        }
    )
    assert result["landed_variable_cost_low"] == Decimal("14.00")
    assert result["landed_variable_cost_high"] == Decimal("23.00")
    assert result["payment_fee"] == Decimal("1.80")
    assert result["refund_allowance"] == Decimal("2.50")
    assert result["break_even_cpa_low"] == Decimal("22.70")
    assert result["break_even_cpa_high"] == Decimal("31.70")
    assert result["break_even_roas_low"] < result["break_even_roas_high"]
    assert result["status"] == "target_viable"


def test_product_economics_api_versions_and_archives_scenarios():
    product_id, headers = _product()
    payload = {
        "name": "Conservative test",
        "currency": "usd",
        "selling_price": 49.99,
        "product_cost_low": 11,
        "product_cost_high": 16,
        "shipping_cost_low": 3,
        "shipping_cost_high": 6,
        "fulfillment_cost_low": 1,
        "fulfillment_cost_high": 2,
        "other_variable_cost_low": 0,
        "other_variable_cost_high": 1,
        "payment_fee_rate": 0.029,
        "payment_fee_fixed": 0.30,
        "refund_allowance_rate": 0.05,
        "target_profit_margin": 0.20,
        "notes": "Manual planning inputs, not supplier evidence.",
    }
    created = client.post(f"/products/{product_id}/economics", headers=headers, json=payload)
    assert created.status_code == 200, created.text
    first = created.json()
    assert first["revision"] == 1
    assert first["input_source"] == "user_entered"
    assert first["currency"] == "USD"
    assert first["calculation"]["version"] == "unit-economics-v1"

    revised_payload = {**payload, "product_cost_high": 19, "name": "Revised conservative test"}
    revised = client.put(
        f"/products/{product_id}/economics/{first['id']}",
        headers=headers,
        json=revised_payload,
    )
    assert revised.status_code == 200, revised.text
    second = revised.json()
    assert second["scenario_key"] == first["scenario_key"]
    assert second["revision"] == 2
    assert second["supersedes_id"] == first["id"]

    active = client.get(f"/products/{product_id}/economics", headers=headers).json()
    assert [row["id"] for row in active] == [second["id"]]
    history = client.get(
        f"/products/{product_id}/economics?include_history=true", headers=headers
    ).json()
    assert {row["revision"] for row in history} == {1, 2}
    assert next(row for row in history if row["revision"] == 1)["is_active"] is False

    invalid = client.post(
        f"/products/{product_id}/economics",
        headers=headers,
        json={**payload, "product_cost_low": 20, "product_cost_high": 10},
    )
    assert invalid.status_code == 422

    archived = client.delete(
        f"/products/{product_id}/economics/{second['id']}", headers=headers
    )
    assert archived.status_code == 200
    assert client.get(f"/products/{product_id}/economics", headers=headers).json() == []
