from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.schemas import UrlIngest
from app.db.base import Base
from app.db.session import SessionLocal
from app.main import app


client = TestClient(app)


def setup_module(module):
    db = SessionLocal()
    Base.metadata.create_all(bind=db.get_bind())
    db.close()


def test_loopback_login_and_empty_library_contract():
    login = client.post("/auth/local")
    assert login.status_code == 200
    token = login.json()["access_token"]
    library = client.get("/library", headers={"Authorization": f"Bearer {token}"})
    assert library.status_code == 200
    payload = library.json()
    assert set(payload) == {"summary", "stores", "products", "sources", "jobs"}
    assert set(payload["summary"]) == {
        "stores",
        "observed_stores",
        "submitted_stores",
        "products",
        "sources",
        "fetched_sources",
        "active_jobs",
    }


def test_url_ingest_normalizes_scheme_and_rejects_private_targets():
    assert UrlIngest(url="example.com/products/widget").url == "https://example.com/products/widget"
    for target in ["http://localhost:8000", "http://127.0.0.1/admin", "file:///etc/passwd"]:
        try:
            UrlIngest(url=target)
        except ValidationError:
            pass
        else:
            raise AssertionError(f"private target was accepted: {target}")


def test_browser_extension_origin_can_call_loopback_api():
    origin = "chrome-extension://abcdefghijklmnopabcdefghijklmnop"
    response = client.options(
        "/ingest/ad",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
