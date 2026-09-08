from fastapi.testclient import TestClient

from app.main import app
from app.db.base import Base
from app.db.session import engine


client = TestClient(app)


def setup_module(module):
    Base.metadata.create_all(bind=engine)


def _headers() -> dict[str, str]:
    response = client.post("/auth/local")
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_ad_watch_crud_and_retention_policy():
    headers = _headers()
    created = client.post(
        "/ad-watches",
        headers=headers,
        json={
            "name": "Acme Meta watch",
            "provider": "meta_ad_library",
            "search_terms": "Acme",
            "countries": ["gb", "de", "GB"],
            "interval_hours": 24,
            "result_limit": 25,
            "is_enabled": False,
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["countries"] == ["GB", "DE"]
    assert body["last_status"] == "never_run"
    assert body["next_run_at"] is None
    assert body["ad_count"] == 0

    listed = client.get("/ad-watches", headers=headers)
    assert listed.status_code == 200, listed.text
    assert any(item["id"] == body["id"] for item in listed.json()["watches"])
    policy = listed.json()["retention_policy"]
    assert {"metadata", "evidence", "creative", "research", "absence_rule"} <= set(policy)

    enabled = client.patch(
        f"/ad-watches/{body['id']}",
        headers=headers,
        json={"is_enabled": True, "countries": ["FR"]},
    )
    assert enabled.status_code == 200, enabled.text
    assert enabled.json()["is_enabled"] is True
    assert enabled.json()["countries"] == ["FR"]
    assert enabled.json()["next_run_at"] is not None

    deleted = client.delete(f"/ad-watches/{body['id']}", headers=headers)
    assert deleted.status_code == 204


def test_meta_watch_requires_numeric_page_id():
    response = client.post(
        "/ad-watches",
        headers=_headers(),
        json={
            "name": "Invalid page",
            "provider": "meta_ad_library",
            "advertiser_id": "not-a-page-id",
            "countries": ["GB"],
            "is_enabled": False,
        },
    )
    assert response.status_code == 422
