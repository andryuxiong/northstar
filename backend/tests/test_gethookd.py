import json

import httpx
from fastapi.testclient import TestClient

from app.api import ads as ads_api
from app.db.base import Base
from app.db.session import SessionLocal
from app.main import app
from app.services.gethookd import GetHookdAPIError, search_gethookd_ads


client = TestClient(app)


def setup_module(module):
    db = SessionLocal()
    Base.metadata.create_all(bind=db.get_bind())
    db.close()


def _headers() -> dict[str, str]:
    response = client.post("/auth/local")
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_explore_request_and_normalization_are_bounded_and_labeled():
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.headers["Authorization"] == "Bearer test-gethookd-token"
        return httpx.Response(
            200,
            json={
                "errors": False,
                "data": [
                    {
                        "id": 123,
                        "external_id": "meta-456",
                        "platform": "facebook, instagram",
                        "display_format": "video",
                        "title": "A useful headline",
                        "body": "Provider ad body",
                        "landing_page": "https://merchant.example/products/item",
                        "cta_text": "Shop Now",
                        "start_date": "2026-06-01",
                        "end_date": None,
                        "days_active": 40,
                        "active_in_library": 1,
                        "used_count": 3,
                        "performance_score": 72,
                        "performance_score_title": "Growing",
                        "share_url": "https://app.gethookd.ai/share/ad/123",
                        "brand": {
                            "external_id": "brand-1",
                            "name": "Merchant",
                            "logo_url": "https://cdn.example/logo.png",
                        },
                        "media": [
                            {
                                "type": "video",
                                "url": "https://cdn.example/ad.mp4",
                                "thumbnail_url": "https://cdn.example/ad.jpg",
                            }
                        ],
                    }
                ],
                "used_credits": 0.1,
                "remaining_credits": 9.9,
                "meta": {"result_count": 1},
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as mock_client:
        result = search_gethookd_ads(
            api_token="test-gethookd-token",
            query="portable blender",
            limit=10,
            platform="facebook",
            status="active",
            ad_format="video",
            minimum_days_active=14,
            client=mock_client,
        )

    assert len(calls) == 1
    params = calls[0].url.params
    assert params["query"] == "portable blender"
    assert params["per_page"] == "10"
    assert params["run-time"] == "14"
    assert params["ad-format"] == "video"
    assert result["used_credits"] == 0.1
    ad = result["ads"][0]
    assert ad["provider"] == "gethookd"
    assert ad["platforms"] == ["facebook", "instagram"]
    assert ad["creative_type"] == "video"
    assert ad["thumbnail_url"] == "https://cdn.example/ad.jpg"
    assert ad["days_active"] == 40
    assert ad["provider_classification"] == "Growing"
    assert "do not establish" in result["data_notice"]


def test_provider_error_is_structured_and_token_is_redacted():
    secret = "GETHOOKD_SECRET_MUST_NOT_LEAK"

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"errors": True, "message": f"Bad token {secret}"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as mock_client:
        try:
            search_gethookd_ads(
                api_token=secret,
                query="shoes",
                client=mock_client,
            )
        except GetHookdAPIError as exc:
            payload = exc.as_dict()
        else:
            raise AssertionError("GetHookd provider error was not propagated")

    assert payload["code"] == "GETHOOKD_SCOPE_ERROR"
    assert secret not in json.dumps(payload)


def test_config_and_live_search_endpoint_contract(monkeypatch):
    headers = _headers()
    client.delete("/integrations/gethookd/config", headers=headers)

    missing = client.post(
        "/ads/gethookd/search",
        headers=headers,
        json={"query": "shoes", "limit": 5},
    )
    assert missing.status_code == 409

    secret = "LOCAL_GETHOOKD_TEST_TOKEN"
    configured = client.put(
        "/integrations/gethookd/config",
        headers=headers,
        json={"api_token": secret},
    )
    assert configured.status_code == 200, configured.text
    assert configured.json()["configured"] is True
    assert secret not in configured.text

    def fake_search(**kwargs):
        assert kwargs["api_token"] == secret
        assert kwargs["query"] == "shoes"
        return {
            "provider": "gethookd",
            "source": "gethookd_public_api",
            "status": "completed",
            "query": "shoes",
            "result_count": 0,
            "used_credits": 0,
            "remaining_credits": 12,
            "ads": [],
            "data_notice": "Provider signal only.",
        }

    monkeypatch.setattr(ads_api, "search_gethookd_ads", fake_search)
    searched = client.post(
        "/ads/gethookd/search",
        headers=headers,
        json={"query": "shoes", "limit": 5, "status": "active"},
    )
    assert searched.status_code == 200, searched.text
    assert searched.json()["provider"] == "gethookd"
    assert searched.json()["remaining_credits"] == 12
    assert secret not in searched.text

    removed = client.delete("/integrations/gethookd/config", headers=headers)
    assert removed.status_code == 200
    assert removed.json()["configured"] is False
    assert secret not in removed.text
