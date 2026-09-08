import json

import httpx

from app.core.config import settings
from app.services.integration_config import (
    delete_similarweb_credential,
    get_similarweb_credential,
    save_similarweb_credential,
    similarweb_status,
)
from app.services.similarweb import SimilarwebClient


def test_similarweb_parses_only_provider_values():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/global-rank/global-rank"):
            return httpx.Response(
                200,
                json={
                    "meta": {"last_updated": "2026-07-01"},
                    "global_rank": [{"date": "2026-06-01", "global_rank": 1234}],
                },
            )
        return httpx.Response(
            200,
            json={
                "meta": {"last_updated": "2026-07-02"},
                "visits": [{"date": "2026-06-01", "visits": 98765.5}],
            },
        )

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        with SimilarwebClient("secret", client=http_client) as client:
            result = client.fetch(
                domain="https://www.example.com/path",
                start_date="2026-06",
                end_date="2026-06",
            )
    finally:
        http_client.close()

    assert result["fetch_status"] == "success"
    assert result["domain"] == "example.com"
    assert result["total_visits"] == 98765.5
    assert result["global_rank"] == 1234
    assert result["data_kind"] == "estimated"
    assert result["provider_last_updated"] == "2026-07-02"


def test_similarweb_keeps_partial_data_when_plan_withholds_a_metric():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/global-rank/global-rank"):
            return httpx.Response(403, json={"message": "No credits for endpoint"})
        return httpx.Response(
            200,
            json={"visits": [{"date": "2026-06-01", "visits": 4200}]},
        )

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        with SimilarwebClient("do-not-echo", client=http_client) as client:
            result = client.fetch(
                domain="example.com",
                start_date="2026-06",
                end_date="2026-06",
            )
    finally:
        http_client.close()

    assert result["fetch_status"] == "partial"
    assert result["global_rank"] is None
    assert result["total_visits"] == 4200
    rank_status = result["metric_status"]["global_rank"]
    assert rank_status["status"] == "access_or_credits"
    assert rank_status["available"] is False
    assert "do-not-echo" not in json.dumps(result)


def test_local_similarweb_config_is_masked_and_removable(tmp_path, monkeypatch):
    config_path = tmp_path / "integrations.json"
    monkeypatch.setattr(settings, "integration_config_path", str(config_path))
    monkeypatch.setattr(settings, "similarweb_api_key", "")

    save_similarweb_credential("test-key-1234")
    key, source = get_similarweb_credential()
    status = similarweb_status()

    assert (key, source) == ("test-key-1234", "local_file")
    assert status["configured"] is True
    assert status["masked_key"].endswith("1234")
    assert "test-key-1234" not in json.dumps(status)
    assert delete_similarweb_credential() is True
    assert get_similarweb_credential() == (None, None)
