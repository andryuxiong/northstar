from fastapi.testclient import TestClient

from app.db import models
from app.db.base import Base
from app.db.session import SessionLocal
from app.main import app


client = TestClient(app)


def _fixture() -> tuple[int, int, dict[str, str]]:
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
        store = models.Store(
            workspace_id=workspace.id,
            domain="shortlist.example",
            platform_guess=models.PlatformGuess.shopify,
        )
        db.add(store)
        db.flush()
        product = models.Product(
            workspace_id=workspace.id,
            store_id=store.id,
            canonical_url="https://shortlist.example/products/candidate",
            title="Shortlist candidate",
            currency="USD",
        )
        db.add(product)
        db.flush()
        evidence = models.EvidenceRecord(
            workspace_id=workspace.id,
            store_id=store.id,
            product_id=product.id,
            evidence_key=f"shortlist-evidence-{product.id}",
            evidence_type="public_product",
            independence_group="storefront",
            details="Observed on the public product page.",
            source_type="public_storefront",
            collector_version="test-v1",
        )
        db.add(evidence)
        db.commit()
        return product.id, evidence.id, headers
    finally:
        db.close()


def test_investigation_shortlist_is_idempotent_and_decision_focused():
    product_id, evidence_id, headers = _fixture()
    payload = {
        "entity_type": "product",
        "entity_id": product_id,
        "workflow_stage": "researching",
        "decision": "investigate",
        "priority": "high",
        "thesis": "The offer may be worth a controlled test.",
        "risks": "Supplier and review evidence are missing.",
        "next_action": "Enter a manual economics scenario.",
        "evidence_ids": [evidence_id],
    }
    created = client.post("/investigations", headers=headers, json=payload)
    assert created.status_code == 200, created.text
    item = created.json()
    assert item["entity_title"] == "Shortlist candidate"
    assert item["entity_subtitle"] == "shortlist.example"
    assert item["evidence"][0]["id"] == evidence_id

    repeated = client.post(
        "/investigations",
        headers=headers,
        json={"entity_type": "product", "entity_id": product_id},
    )
    assert repeated.status_code == 200
    assert repeated.json()["id"] == item["id"]
    assert repeated.json()["thesis"] == payload["thesis"]

    updated = client.put(
        f"/investigations/{item['id']}",
        headers=headers,
        json={
            "workflow_stage": "ready_to_test",
            "decision": "test",
            "priority": "high",
            "thesis": payload["thesis"],
            "risks": payload["risks"],
            "next_action": "Define kill criteria and launch a small test.",
            "evidence_ids": [evidence_id],
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["workflow_stage"] == "ready_to_test"
    assert updated.json()["decision"] == "test"

    listed = client.get("/investigations?entity_type=product", headers=headers)
    assert listed.status_code == 200
    assert [row["id"] for row in listed.json()] == [item["id"]]

    invalid_evidence = client.put(
        f"/investigations/{item['id']}",
        headers=headers,
        json={
            "workflow_stage": "researching",
            "decision": "investigate",
            "priority": "medium",
            "evidence_ids": [999999],
        },
    )
    assert invalid_evidence.status_code == 422

    dossier = client.get(f"/exports/investigations/{item['id']}", headers=headers)
    assert dossier.status_code == 200, dossier.text
    assert "northstar-investigation" in dossier.headers["content-disposition"]
    dossier_body = dossier.json()
    assert dossier_body["dossier_version"] == "research-dossier-v1"
    assert dossier_body["investigation"]["id"] == item["id"]
    assert dossier_body["entity_data"]["product"]["id"] == product_id
    assert "verified product sales" in dossier_body["entity_data"]["unavailable"]
    assert "unavailable values are not zero" in dossier_body["trust_notice"]

    archived = client.delete(f"/investigations/{item['id']}", headers=headers)
    assert archived.status_code == 200
    assert client.get("/investigations", headers=headers).json() == []
    history = client.get("/investigations?include_archived=true", headers=headers).json()
    assert history[0]["workflow_stage"] == "archived"
