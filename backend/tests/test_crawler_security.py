import socket
import gzip

import httpx
import pytest

from app.db import models
from app.db.session import SessionLocal
from app.services.crawler import (
    ResponseTooLarge,
    UnsafeDestination,
    request_public_url,
    validate_public_destination,
)
from app.workers import tasks


def _dns_row(address: str):
    family = socket.AF_INET6 if ":" in address else socket.AF_INET
    return (family, socket.SOCK_STREAM, 6, "", (address, 443))


def test_dns_alias_to_private_network_is_rejected(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [_dns_row("10.0.0.12")],
    )
    with pytest.raises(UnsafeDestination):
        validate_public_destination("https://store.example/products/widget")


def test_redirect_to_literal_loopback_is_never_requested(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [_dns_row("93.184.216.34")],
    )
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return httpx.Response(302, headers={"location": "http://127.0.0.1/admin"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(UnsafeDestination):
            request_public_url(client, "https://store.example", timeout=2, rate_limit=False)

    assert requests == ["https://store.example/"]


def test_public_redirect_is_validated_and_followed(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [_dns_row("93.184.216.34")],
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "store.example":
            return httpx.Response(301, headers={"location": "https://www.store.example/catalog"})
        return httpx.Response(200, text="public catalog")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        response, final_url = request_public_url(
            client,
            "https://store.example",
            timeout=2,
            rate_limit=False,
        )

    assert response.text == "public catalog"
    assert final_url == "https://www.store.example/catalog"


def test_decompressed_response_body_is_bounded(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [_dns_row("93.184.216.34")],
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * 101)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ResponseTooLarge):
            request_public_url(
                client,
                "https://store.example",
                timeout=2,
                rate_limit=False,
                max_bytes=100,
            )


def test_streamed_compressed_response_is_not_decoded_twice(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [_dns_row("93.184.216.34")],
    )
    expected = b"public storefront"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-encoding": "gzip", "content-type": "text/html"},
            content=gzip.compress(expected),
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        response, _ = request_public_url(
            client,
            "https://store.example",
            timeout=2,
            rate_limit=False,
        )

    assert response.content == expected
    assert "content-encoding" not in response.headers


def test_failed_public_fetch_raises_for_job_runner(monkeypatch):
    db = SessionLocal()
    try:
        user = models.User(email="failed-fetch@example.com")
        db.add(user)
        db.flush()
        workspace = models.Workspace(name="Failed fetch", owner_user_id=user.id)
        db.add(workspace)
        db.flush()
        source = models.SourceUrl(
            workspace_id=workspace.id,
            url="https://failure.example/product",
            type=models.SourceUrlType.product,
        )
        db.add(source)
        db.commit()
        source_id = source.id
    finally:
        db.close()

    monkeypatch.setattr(tasks, "fetch_url", lambda url: (None, None, 500))
    with pytest.raises(RuntimeError, match="HTTP status 500"):
        tasks.fetch_url_task(source_id)

    db = SessionLocal()
    try:
        saved = db.query(models.SourceUrl).filter(models.SourceUrl.id == source_id).one()
        assert saved.fetch_status == "failed"
        assert saved.last_http_status == 500
    finally:
        db.close()
