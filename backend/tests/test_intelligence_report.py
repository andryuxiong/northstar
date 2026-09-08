from datetime import datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from app.db import models
from app.db.base import Base
from app.db.session import SessionLocal
from app.main import app
from app.services.workspace import get_default_workspace
from app.services.similarweb import default_month


client = TestClient(app)


def setup_module(module):
    db = SessionLocal()
    Base.metadata.create_all(bind=db.get_bind())
    db.close()


def _local_token() -> str:
    response = client.post("/auth/local")
    assert response.status_code == 200
    return response.json()["access_token"]


def _store_with_catalog(*, traffic: bool = False) -> tuple[int, int]:
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.email == "local@northstar").first()
        assert user is not None
        workspace = get_default_workspace(db, user.id)
        slug = uuid4().hex
        store = models.Store(
            workspace_id=workspace.id,
            domain=f"{slug}.example.com",
            platform_guess=models.PlatformGuess.shopify,
        )
        db.add(store)
        db.flush()
        prices = [20, 30, 40, 50, 60]
        for index, price in enumerate(prices, start=1):
            product = models.Product(
                workspace_id=workspace.id,
                store_id=store.id,
                canonical_url=f"https://{store.domain}/products/item-{index}",
                title=f"Primary product {index}",
                currency="USD",
            )
            db.add(product)
            db.flush()
            db.add(
                models.ProductSnapshot(
                    product_id=product.id,
                    title=product.title,
                    price_min=price,
                    price_max=price,
                    available=True,
                    variant_count=1,
                    images_json=[f"https://cdn.example.com/{index}.jpg"],
                    raw_extracted_json={"variants": [{"price": price}]},
                    content_hash=f"{slug}-{index}",
                )
            )
        gift = models.Product(
            workspace_id=workspace.id,
            store_id=store.id,
            canonical_url=f"https://{store.domain}/products/free-gift",
            title="Tripod (Free Gift)",
            currency="USD",
        )
        db.add(gift)
        db.flush()
        db.add(
            models.ProductSnapshot(
                product_id=gift.id,
                title=gift.title,
                price_min=0,
                price_max=0,
                available=True,
                variant_count=1,
                images_json=[],
                raw_extracted_json={"variants": [{"price": 0}]},
                content_hash=f"{slug}-gift",
            )
        )
        if traffic:
            db.add(
                models.TrafficSnapshot(
                    workspace_id=workspace.id,
                    store_id=store.id,
                    domain=store.domain,
                    provider="similarweb",
                    period_start="2026-04",
                    period_end="2026-06",
                    country="world",
                    granularity="monthly",
                    main_domain_only=True,
                    total_visits=130000,
                    global_rank=50000,
                    visits_series_json=[
                        {"date": "2026-04-01", "visits": 100000},
                        {"date": "2026-05-01", "visits": 115000},
                        {"date": "2026-06-01", "visits": 130000},
                    ],
                    global_rank_series_json=[
                        {"date": "2026-04-01", "global_rank": 65000},
                        {"date": "2026-05-01", "global_rank": 57000},
                        {"date": "2026-06-01", "global_rank": 50000},
                    ],
                    metric_status_json={
                        "total_visits": {"status": "success"},
                        "global_rank": {"status": "success"},
                    },
                    fetch_status="success",
                    provider_last_updated="2026-07-01",
                    fetched_at=datetime(2026, 7, 2),
                )
            )
        db.commit()
        return workspace.id, store.id
    finally:
        db.close()


def test_report_is_honest_when_traffic_and_product_demand_are_missing():
    token = _local_token()
    workspace_id, store_id = _store_with_catalog(traffic=False)
    response = client.get(
        f"/intelligence/stores/{store_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    report = response.json()
    metrics = report["executive_summary"]["metrics"]
    assert metrics["aov"]["status"] == "available"
    assert metrics["monthly_visits"]["status"] == "insufficient_data"
    assert metrics["monthly_orders"]["status"] == "insufficient_data"
    assert metrics["monthly_revenue"]["status"] == "insufficient_data"
    assert metrics["dropshipping_likelihood"]["value"] is None
    assert report["executive_summary"]["verdict"] == "Little evidence of meaningful demand"
    assert report["store"]["product_count"] == 5
    assert len(report["products"]) == 5
    assert all("free gift" not in product["title"].lower() for product in report["products"])
    assert report["diagnostics"]["auxiliary_product_count"] == 1
    assert all(product["momentum"]["status"] == "insufficient_data" for product in report["products"])
    assert all(product["saturation"]["status"] == "insufficient_data" for product in report["products"])

    db = SessionLocal()
    try:
        runs = db.query(models.AnalysisRun).filter(models.AnalysisRun.store_id == store_id).count()
        insights = db.query(models.DerivedInsight).filter(models.DerivedInsight.store_id == store_id).count()
        evidence = db.query(models.EvidenceRecord).filter(models.EvidenceRecord.store_id == store_id).count()
        assert runs == 1
        assert insights >= 4
        assert evidence >= 1
    finally:
        db.close()


def test_report_produces_disclosed_ranges_when_required_inputs_exist():
    token = _local_token()
    _, store_id = _store_with_catalog(traffic=True)
    response = client.get(
        f"/intelligence/stores/{store_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    report = response.json()
    metrics = report["executive_summary"]["metrics"]
    for key in ("monthly_visits", "aov", "monthly_orders", "monthly_revenue"):
        insight = metrics[key]
        assert insight["status"] == "available"
        assert insight["low"] <= insight["central"] <= insight["high"]
        assert insight["estimator_version"]
        assert insight["assumptions"]
        assert insight["evidence"]
    assert "not profit" in metrics["monthly_revenue"]["explanation"]
    assert metrics["monthly_revenue"]["confidence_label"] == "low"
    assert len(report["traffic"]["periods"]) == 3
    assert report["traffic"]["trend"]["value"] == "Growing"


def test_estimation_settings_are_versioned_and_validated():
    token = _local_token()
    headers = {"Authorization": f"Bearer {token}"}
    initial = client.get("/intelligence/settings", headers=headers)
    assert initial.status_code == 200
    original = initial.json()[0]

    updated = client.put(
        "/intelligence/settings/general_ecommerce",
        headers=headers,
        json={
            "conversion_rate_low": 0.004,
            "conversion_rate_central": 0.01,
            "conversion_rate_high": 0.02,
            "freshness_limit_days": 60,
        },
    )
    assert updated.status_code == 200, updated.text
    payload = updated.json()
    assert payload["id"] != original["id"]
    assert payload["version"] != original["version"]
    assert payload["conversion_rate_central"] == 0.01
    assert payload["freshness_limit_days"] == 60

    invalid = client.put(
        "/intelligence/settings/general_ecommerce",
        headers=headers,
        json={
            "conversion_rate_low": 0.03,
            "conversion_rate_central": 0.02,
            "conversion_rate_high": 0.01,
        },
    )
    assert invalid.status_code == 422


def test_report_is_workspace_scoped():
    token = _local_token()
    db = SessionLocal()
    try:
        stranger = models.User(email=f"stranger-{uuid4().hex}@example.com", password_hash="x")
        db.add(stranger)
        db.flush()
        workspace = models.Workspace(name="Other", owner_user_id=stranger.id)
        db.add(workspace)
        db.flush()
        store = models.Store(
            workspace_id=workspace.id,
            domain=f"private-{uuid4().hex}.example.com",
            platform_guess=models.PlatformGuess.unknown,
        )
        db.add(store)
        db.commit()
        store_id = store.id
    finally:
        db.close()
    response = client.get(
        f"/intelligence/stores/{store_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


def test_store_identity_candidates_can_be_reviewed_and_confirmation_is_scoped():
    token = _local_token()
    headers = {"Authorization": f"Bearer {token}"}
    workspace_id, store_id = _store_with_catalog()
    db = SessionLocal()
    try:
        candidate = models.StoreIdentity(
            workspace_id=workspace_id,
            store_id=store_id,
            identity_type="instagram",
            display_value="northstar-test",
            normalized_value="northstar-test",
            source_type="homepage_link",
            source_url="https://www.instagram.com/northstar-test/",
            confidence_score=0.78,
            evidence_json={"evidence": "homepage social link"},
        )
        db.add(candidate)
        db.flush()
        candidate_id = candidate.id

        other_store = models.Store(
            workspace_id=workspace_id,
            domain=f"other-{uuid4().hex}.example.com",
            platform_guess=models.PlatformGuess.unknown,
        )
        db.add(other_store)
        db.flush()
        other_store_id = other_store.id
        db.commit()
    finally:
        db.close()

    listed = client.get(
        f"/intelligence/stores/{store_id}/identities",
        headers=headers,
    )
    assert listed.status_code == 200, listed.text
    assert listed.json() == [
        {
            "id": candidate_id,
            "identity_type": "instagram",
            "display_value": "northstar-test",
            "source_type": "homepage_link",
            "source_url": "https://www.instagram.com/northstar-test/",
            "confidence_score": 0.78,
            "is_confirmed": False,
            "evidence": {"evidence": "homepage social link"},
            "first_seen_at": listed.json()[0]["first_seen_at"],
            "last_seen_at": listed.json()[0]["last_seen_at"],
            "confirmed_at": None,
        }
    ]

    confirmed = client.patch(
        f"/intelligence/stores/{store_id}/identities/{candidate_id}",
        headers=headers,
        json={"confirmed": True},
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["is_confirmed"] is True
    assert confirmed.json()["confirmed_at"] is not None

    wrong_store = client.patch(
        f"/intelligence/stores/{other_store_id}/identities/{candidate_id}",
        headers=headers,
        json={"confirmed": False},
    )
    assert wrong_store.status_code == 404

    unconfirmed = client.patch(
        f"/intelligence/stores/{store_id}/identities/{candidate_id}",
        headers=headers,
        json={"confirmed": False},
    )
    assert unconfirmed.status_code == 200
    assert unconfirmed.json()["is_confirmed"] is False
    assert unconfirmed.json()["confirmed_at"] is None


def test_newer_rank_fetch_does_not_make_old_visit_estimate_fresh():
    token = _local_token()
    workspace_id, store_id = _store_with_catalog(traffic=False)
    now = datetime.utcnow()
    db = SessionLocal()
    try:
        db.add_all(
            [
                models.TrafficSnapshot(
                    workspace_id=workspace_id,
                    store_id=store_id,
                    domain=db.get(models.Store, store_id).domain,
                    provider="similarweb",
                    fetched_at=now - timedelta(days=90),
                    period_start=now.strftime("%Y-%m"),
                    period_end=now.strftime("%Y-%m"),
                    country="world",
                    granularity="monthly",
                    main_domain_only=True,
                    total_visits=50000,
                    global_rank=None,
                    visits_series_json=[
                        {"date": now.strftime("%Y-%m-01"), "visits": 50000}
                    ],
                    global_rank_series_json=[],
                    metric_status_json={
                        "total_visits": {"status": "success"},
                        "global_rank": {"status": "unavailable"},
                    },
                    fetch_status="partial",
                ),
                models.TrafficSnapshot(
                    workspace_id=workspace_id,
                    store_id=store_id,
                    domain=db.get(models.Store, store_id).domain,
                    provider="similarweb",
                    fetched_at=now,
                    period_start=now.strftime("%Y-%m"),
                    period_end=now.strftime("%Y-%m"),
                    country="world",
                    granularity="monthly",
                    main_domain_only=True,
                    total_visits=None,
                    global_rank=10000,
                    visits_series_json=[],
                    global_rank_series_json=[
                        {"date": now.strftime("%Y-%m-01"), "global_rank": 10000}
                    ],
                    metric_status_json={
                        "total_visits": {"status": "unavailable"},
                        "global_rank": {"status": "success"},
                    },
                    fetch_status="partial",
                ),
            ]
        )
        db.commit()
    finally:
        db.close()

    response = client.get(
        f"/intelligence/stores/{store_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    visits = response.json()["executive_summary"]["metrics"]["monthly_visits"]
    assert visits["status"] == "available"
    assert "fresh_traffic_observation" in visits["missing_signals"]


def test_completed_analysis_runs_and_evidence_are_immutable():
    token = _local_token()
    _, store_id = _store_with_catalog(traffic=True)
    headers = {"Authorization": f"Bearer {token}"}
    first_response = client.get(f"/intelligence/stores/{store_id}", headers=headers)
    assert first_response.status_code == 200, first_response.text

    db = SessionLocal()
    try:
        first_run = (
            db.query(models.AnalysisRun)
            .filter(models.AnalysisRun.store_id == store_id)
            .order_by(models.AnalysisRun.id.desc())
            .first()
        )
        first_run_id = first_run.id
        first_completed_at = first_run.completed_at
        first_insight = (
            db.query(models.DerivedInsight)
            .filter(models.DerivedInsight.analysis_run_id == first_run_id)
            .order_by(models.DerivedInsight.id.asc())
            .first()
        )
        first_insight_calculated_at = first_insight.calculated_at
        first_link_count = (
            db.query(models.InsightEvidence)
            .join(models.DerivedInsight)
            .filter(models.DerivedInsight.analysis_run_id == first_run_id)
            .count()
        )
        linked_evidence = (
            db.query(models.EvidenceRecord)
            .join(models.InsightEvidence)
            .join(models.DerivedInsight)
            .filter(models.DerivedInsight.analysis_run_id == first_run_id)
            .first()
        )
        evidence_retrieved_at = linked_evidence.retrieved_at
        evidence_details = linked_evidence.details
    finally:
        db.close()

    second_response = client.get(f"/intelligence/stores/{store_id}", headers=headers)
    assert second_response.status_code == 200, second_response.text

    db = SessionLocal()
    try:
        assert db.query(models.AnalysisRun).filter(models.AnalysisRun.store_id == store_id).count() == 2
        unchanged_run = db.get(models.AnalysisRun, first_run_id)
        unchanged_insight = db.get(models.DerivedInsight, first_insight.id)
        unchanged_evidence = db.get(models.EvidenceRecord, linked_evidence.id)
        assert unchanged_run.completed_at == first_completed_at
        assert unchanged_insight.calculated_at == first_insight_calculated_at
        assert unchanged_evidence.retrieved_at == evidence_retrieved_at
        assert unchanged_evidence.details == evidence_details
        assert (
            db.query(models.InsightEvidence)
            .join(models.DerivedInsight)
            .filter(models.DerivedInsight.analysis_run_id == first_run_id)
            .count()
            == first_link_count
        )
    finally:
        db.close()


def test_recent_traffic_refresh_is_cached_to_protect_provider_credits():
    token = _local_token()
    workspace_id, store_id = _store_with_catalog(traffic=False)
    period = default_month()
    db = SessionLocal()
    try:
        store = db.get(models.Store, store_id)
        db.add(
            models.TrafficSnapshot(
                workspace_id=workspace_id,
                store_id=store_id,
                domain=store.domain,
                provider="similarweb",
                period_start=period,
                period_end=period,
                country="world",
                granularity="monthly",
                main_domain_only=True,
                total_visits=12345,
                global_rank=54321,
                visits_series_json=[{"date": f"{period}-01", "visits": 12345}],
                global_rank_series_json=[
                    {"date": f"{period}-01", "global_rank": 54321}
                ],
                metric_status_json={
                    "total_visits": {"status": "success"},
                    "global_rank": {"status": "success"},
                },
                fetch_status="success",
            )
        )
        db.commit()
    finally:
        db.close()
    response = client.post(
        f"/traffic/stores/{store_id}/refresh",
        headers={"Authorization": f"Bearer {token}"},
        json={"start_date": period, "end_date": period},
    )
    assert response.status_code == 200, response.text
    assert response.json()["cached"] is True
    assert "provider credit" in response.json()["cache_notice"]
