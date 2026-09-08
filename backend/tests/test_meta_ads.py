from datetime import datetime
import json
import logging

import httpx
from fastapi.testclient import TestClient

from app.api import ads as ads_api
from app.api import integrations as integrations_api
from app.core.logging import setup_logging
from app.db import models
from app.db.base import Base
from app.db.session import SessionLocal
from app.main import app
from app.services.meta_ads import (
    MetaAdsAPIError,
    parse_meta_ad,
    persist_meta_ads,
    search_ads_archive,
)


client = TestClient(app)


def setup_module(module):
    db = SessionLocal()
    Base.metadata.create_all(bind=db.get_bind())
    db.close()


def test_provider_request_loggers_do_not_write_credential_urls():
    setup_logging()
    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING
    assert logging.getLogger("httpcore").getEffectiveLevel() >= logging.WARNING


def test_search_is_cursor_paginated_and_strictly_bounded():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert "/v25.0/ads_archive" in str(request.url)
        if request.url.params.get("after") is None:
            return httpx.Response(
                200,
                json={
                    "data": [{"id": "1"}, {"id": "2"}],
                    "paging": {"cursors": {"after": "next-cursor"}},
                },
            )
        return httpx.Response(
            200,
            json={
                "data": [{"id": "3"}, {"id": "4"}],
                "paging": {"cursors": {"after": "unused"}},
            },
        )

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as mock_client:
        rows = search_ads_archive(
            access_token="token-for-test",
            ad_reached_countries=["GB"],
            search_terms="shoes",
            limit=3,
            client=mock_client,
        )

    assert [row["id"] for row in rows] == ["1", "2", "3"]
    assert len(calls) == 2
    assert calls[0].url.params.get("limit") == "3"
    assert calls[1].url.params.get("limit") == "1"
    fields = calls[0].url.params.get("fields")
    assert "ad_creative_bodies" in fields
    assert "publisher_platforms" in fields


def test_provider_error_is_structured_and_never_exposes_token():
    secret = "SECRET_TOKEN_MUST_NOT_LEAK"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": {
                    "message": f"Bad URL access_token={secret}",
                    "type": "OAuthException",
                    "code": 190,
                    "error_subcode": 463,
                    "fbtrace_id": "trace-1",
                }
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as mock_client:
        try:
            search_ads_archive(
                access_token=secret,
                ad_reached_countries=["GB"],
                search_terms="shoes",
                client=mock_client,
            )
        except MetaAdsAPIError as exc:
            payload = exc.as_dict()
        else:
            raise AssertionError("Meta provider error was not propagated")

    assert payload["provider_code"] == 190
    assert payload["provider_subcode"] == 463
    assert payload["trace_id"] == "trace-1"
    assert secret not in json.dumps(payload)


def test_parser_handles_string_and_mapping_creatives_without_storing_snapshot_token():
    secret = "SNAPSHOT_SECRET"
    parsed = parse_meta_ad(
        {
            "id": "998877",
            "page_id": 1234,
            "page_name": "Real Merchant",
            "ad_creative_bodies": ["First body", {"text": "Second body"}],
            "ad_creative_link_titles": "A real headline",
            "ad_creation_time": "2026-01-01T12:00:00+00:00",
            "ad_delivery_start_time": "2026-01-02",
            "ad_delivery_stop_time": "2026-01-03T15:00:00Z",
            "publisher_platforms": '["FACEBOOK", "INSTAGRAM"]',
            "ad_snapshot_url": f"https://www.facebook.com/ads/archive/render_ad/?access_token={secret}",
        }
    )

    assert parsed is not None
    assert parsed.ad_text == "First body\n\nSecond body"
    assert parsed.headline == "A real headline"
    assert parsed.publisher_platforms == ["facebook", "instagram"]
    assert parsed.delivery_start_time == datetime(2026, 1, 2)
    assert parsed.ad_snapshot_url == "https://www.facebook.com/ads/library/?id=998877"
    assert secret not in json.dumps(parsed.__dict__, default=str)


def test_persistence_upserts_provider_fields():
    db = SessionLocal()
    try:
        user = models.User(email="meta-persist@example.com")
        db.add(user)
        db.flush()
        workspace = models.Workspace(name="Meta test", owner_user_id=user.id)
        db.add(workspace)
        db.commit()
        db.refresh(workspace)

        first = persist_meta_ads(
            db,
            workspace_id=workspace.id,
            raw_ads=[
                {
                    "id": "meta-upsert-1",
                    "page_name": "Merchant One",
                    "ad_creative_bodies": "Original body",
                    "ad_creative_link_titles": ["Original headline"],
                    "ad_delivery_start_time": "2026-02-01",
                    "publisher_platforms": ["facebook"],
                    "ad_snapshot_url": "https://example.invalid/snapshot?access_token=private",
                }
            ],
        )
        second = persist_meta_ads(
            db,
            workspace_id=workspace.id,
            raw_ads=[
                {
                    "id": "meta-upsert-1",
                    "page_name": "Merchant One Updated",
                    "ad_creative_bodies": ["Updated body"],
                    "ad_creative_link_titles": [{"text": "Updated headline"}],
                    "publisher_platforms": ["instagram"],
                }
            ],
        )

        assert first.inserted_count == 1
        assert second.updated_count == 1
        row = second.records[0]
        assert row.advertiser_name == "Merchant One Updated"
        assert row.headline == "Updated headline"
        assert row.publisher_platforms_json == ["instagram"]
        assert row.delivery_start_time == datetime(2026, 2, 1)
        assert "access_token" not in (row.ad_snapshot_url or "")
        assert (
            db.query(models.Ad)
            .filter(models.Ad.workspace_id == workspace.id, models.Ad.external_ad_id == "meta-upsert-1")
            .count()
            == 1
        )
    finally:
        db.close()


def test_real_search_endpoint_contract_and_not_configured_guard(monkeypatch):
    token_response = client.post("/auth/local")
    assert token_response.status_code == 200
    headers = {"Authorization": f"Bearer {token_response.json()['access_token']}"}
    client.delete("/integrations/meta/config", headers=headers)
    request_payload = {
        "search_terms": "shoes",
        "ad_reached_countries": ["GB"],
        "ad_type": "ALL",
        "limit": 2,
    }

    missing = client.post("/ads/meta/search", json=request_payload, headers=headers)
    assert missing.status_code == 409
    assert missing.json()["status"] == "not_configured"
    assert missing.json()["configured"] is False
    legacy_missing = client.post("/ingest/meta-ads-search", json=request_payload, headers=headers)
    assert legacy_missing.status_code == 409

    secret = "LOCAL_META_TEST_TOKEN"
    configured = client.put(
        "/integrations/meta/config",
        json={"access_token": secret},
        headers=headers,
    )
    assert configured.status_code == 200
    assert secret not in configured.text

    def fake_search(**kwargs):
        assert kwargs["access_token"] == secret
        return [
            {
                "id": "endpoint-meta-1",
                "page_name": "Endpoint Merchant",
                "ad_creative_bodies": "Actual provider body",
                "ad_creative_link_titles": ["Actual provider title"],
                "publisher_platforms": ["facebook", "instagram"],
                "ad_snapshot_url": f"https://meta.invalid/snapshot?access_token={secret}",
            }
        ]

    monkeypatch.setattr(ads_api, "search_ads_archive", fake_search)
    monkeypatch.setattr(integrations_api, "search_ads_archive", fake_search)
    searched = client.post("/ads/meta/search", json=request_payload, headers=headers)
    assert searched.status_code == 200
    body = searched.json()
    assert body["status"] == "completed"
    assert body["source"] == "official_meta_graph_api"
    assert body["fetched_count"] == 1
    assert body["ads"][0]["headline"] == "Actual provider title"
    assert body["ads"][0]["publisher_platforms"] == ["facebook", "instagram"]
    assert secret not in searched.text

    tested = client.post("/integrations/meta/test", json=request_payload, headers=headers)
    assert tested.status_code == 200
    assert tested.json()["fetched_count"] == 1
    assert secret not in tested.text

    removed = client.delete("/integrations/meta/config", headers=headers)
    assert removed.status_code == 200
    assert secret not in removed.text
