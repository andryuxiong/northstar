from fastapi.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal
from app.db.base import Base
from app.db import models
from app.utils.security import hash_password

client = TestClient(app)


def setup_module(module):
    db = SessionLocal()
    Base.metadata.create_all(bind=db.get_bind())
    db.close()


def test_auth_and_products():
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.email == "api@example.com").first()
        if not user:
            user = models.User(email="api@example.com", password_hash=hash_password("pass123"))
            db.add(user)
            db.commit()
            db.refresh(user)
            ws = models.Workspace(name="Default", owner_user_id=user.id)
            db.add(ws)
            db.commit()
        res = client.post("/auth/login", data={"username": "api@example.com", "password": "pass123"})
        assert res.status_code == 200
        token = res.json()["access_token"]

        res = client.get("/products", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
    finally:
        db.close()


def test_manual_public_ad_import_preserves_provenance_and_is_searchable():
    token_response = client.post("/auth/local")
    assert token_response.status_code == 200
    headers = {"Authorization": f"Bearer {token_response.json()['access_token']}"}
    imported = client.post(
        "/ingest/ad",
        headers=headers,
        json={
            "platform": "tiktok",
            "source_url": "https://ads.tiktok.com/business/creativecenter/inspiration/topads/pc/en?access_token=must-not-store&view=public",
            "advertiser_name": "Example merchant",
            "headline": "Portable blender demonstration",
            "ad_text": "A public ad saved for personal research",
            "creative_type": "video",
            "creative_urls": ["https://cdn.example.com/creative.mp4"],
            "landing_url": "https://merchant.example/products/blender",
            "cta": "Shop now",
            "metrics": [
                {
                    "metric_key": "likes",
                    "value_kind": "reported_value",
                    "value_text": "34K",
                    "unit": "count",
                    "provider": "tiktok_creative_center",
                },
                {
                    "metric_key": "ctr",
                    "value_kind": "percentile",
                    "value_text": "Top 18%",
                    "unit": "category_percentile",
                    "provider": "tiktok_creative_center",
                },
            ],
        },
    )
    assert imported.status_code == 200, imported.text
    body = imported.json()
    assert body["data_provider"] == "northstar_manual"
    assert body["source_type"] == "manual_public_import"
    assert body["source_url"].startswith("https://ads.tiktok.com/")
    assert "access_token" not in body["source_url"]
    assert "view=public" in body["source_url"]

    analytics = client.get(f"/ads/{body['id']}/analytics", headers=headers)
    assert analytics.status_code == 200, analytics.text
    analytics_body = analytics.json()
    assert {metric["metric_key"] for metric in analytics_body["metrics"]} == {"likes", "ctr"}
    assert analytics_body["has_provider_performance_metrics"] is True
    assert any(item["metric_key"] == "impressions" for item in analytics_body["unavailable_metrics"])

    autopsy = client.get(f"/ads/{body['id']}/autopsy", headers=headers)
    assert autopsy.status_code == 200, autopsy.text
    autopsy_body = autopsy.json()
    assert autopsy_body["ad"]["id"] == body["id"]
    assert autopsy_body["analytics"]["ad_id"] == body["id"]
    assert autopsy_body["creative_analysis"]["asset_count"] == 1
    assert autopsy_body["creative_analysis"]["transcript_status"] == "not_collected"
    assert autopsy_body["creative_analysis"]["ocr_status"] == "not_collected"
    assert autopsy_body["conclusion"]["status"] == "weak_evidence"
    assert autopsy_body["products"] == []
    assert autopsy_body["landing_pages"]
    assert autopsy_body["landing_pages"][0]["url"] == body["landing_url"]

    recaptured = client.post(
        "/ingest/ad",
        headers=headers,
        json={
            "platform": "tiktok",
            "source_url": body["source_url"],
            "headline": "Portable blender demonstration — reviewed",
            "creative_type": "video",
            "creative_urls": ["https://cdn.example.com/creative.mp4"],
            "landing_url": body["landing_url"],
            "capture_metadata": {
                "adapter_id": "tiktok_creative_center",
                "adapter_version": "capture-adapters-v1",
                "confidence": "medium",
                "warnings": ["Advertiser was reviewed manually."],
                "captured_fields": ["headline", "creative_url", "landing_url"],
            },
        },
    )
    assert recaptured.status_code == 200, recaptured.text
    recaptured_body = recaptured.json()
    assert recaptured_body["id"] == body["id"]
    assert recaptured_body["source_type"] == "browser_extension_capture"
    assert recaptured_body["provider_metadata"]["capture"]["adapter_version"] == "capture-adapters-v1"
    db = SessionLocal()
    try:
        assert db.query(models.AdLandingEdge).filter(models.AdLandingEdge.ad_id == body["id"]).count() == 1
    finally:
        db.close()

    # Distinct landing URLs that resolve to the same collected product are related
    # through stored graph evidence rather than URL or advertiser-name heuristics.
    db = SessionLocal()
    try:
        imported_ad = db.query(models.Ad).filter(models.Ad.id == body["id"]).one()
        first_landing = (
            db.query(models.SourceUrl)
            .join(models.AdLandingEdge, models.AdLandingEdge.url_id == models.SourceUrl.id)
            .filter(models.AdLandingEdge.ad_id == imported_ad.id)
            .one()
        )
        store = models.Store(
            workspace_id=imported_ad.workspace_id,
            domain="merchant.example",
            platform_guess=models.PlatformGuess.shopify,
        )
        db.add(store)
        db.flush()
        product = models.Product(
            workspace_id=imported_ad.workspace_id,
            store_id=store.id,
            canonical_url="https://merchant.example/products/blender",
            title="Portable blender",
        )
        db.add(product)
        db.flush()
        second_landing = models.SourceUrl(
            workspace_id=imported_ad.workspace_id,
            url="https://merchant.example/pages/blender-offer",
            type=models.SourceUrlType.landing_page,
            fetch_status="completed",
        )
        db.add(second_landing)
        db.flush()
        related_ad = models.Ad(
            workspace_id=imported_ad.workspace_id,
            platform=models.AdPlatform.meta,
            data_provider="meta_ad_library",
            source_type="official_provider_api",
            advertiser_name="A different recorded advertiser",
            headline="A second funnel for the same product",
            creative_type=models.CreativeType.image,
            landing_url=second_landing.url,
        )
        db.add(related_ad)
        db.flush()
        db.add_all(
            [
                models.LandingProductEdge(landing_url_id=first_landing.id, product_id=product.id),
                models.LandingProductEdge(landing_url_id=second_landing.id, product_id=product.id),
                models.AdLandingEdge(ad_id=related_ad.id, url_id=second_landing.id),
            ]
        )
        db.commit()
        related_ad_id = related_ad.id
    finally:
        db.close()

    resolved_autopsy = client.get(f"/ads/{body['id']}/autopsy", headers=headers)
    assert resolved_autopsy.status_code == 200, resolved_autopsy.text
    resolved_body = resolved_autopsy.json()
    assert resolved_body["conclusion"]["status"] == "investigate"
    assert resolved_body["products"][0]["title"] == "Portable blender"
    related_match = next(item for item in resolved_body["related_ads"] if item["ad"]["id"] == related_ad_id)
    assert "same resolved product" in related_match["reasons"]

    added_metric = client.post(
        f"/ads/{body['id']}/metrics",
        headers=headers,
        json={
            "metric_key": "reach",
            "value_kind": "range",
            "range_low": 10000,
            "range_high": 50000,
            "unit": "people",
            "provider": "manual_public_source",
            "geography": "US",
        },
    )
    assert added_metric.status_code == 200, added_metric.text
    assert added_metric.json()["range_low"] == "10000.000000"

    facets = client.get("/ads/facets", headers=headers)
    assert facets.status_code == 200, facets.text
    facets_body = facets.json()
    assert {"likes", "ctr", "reach"} <= set(facets_body["metric_keys"])
    assert "US" in facets_body["geographies"]
    assert "reach" in facets_body["metric_keys_by_ad"][str(body["id"])]
    assert "does not call Meta" in facets_body["data_notice"]

    listed = client.get("/ads?query=portable%20blender", headers=headers)
    assert listed.status_code == 200
    assert any(row["id"] == body["id"] for row in listed.json())

    invalid = client.post(
        "/ingest/ad",
        headers=headers,
        json={"platform": "manual", "advertiser_name": "No evidence"},
    )
    assert invalid.status_code == 422

    invalid_range = client.post(
        f"/ads/{body['id']}/metrics",
        headers=headers,
        json={
            "metric_key": "impressions",
            "value_kind": "range",
            "range_low": 100,
            "range_high": 10,
            "provider": "manual_public_source",
        },
    )
    assert invalid_range.status_code == 422
