import json
import os
from datetime import datetime
from typing import Any

import httpx

from app.core.config import settings
from app.services.crawler import request_public_url


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def snapshot_base_dir() -> str:
    base = settings.snapshot_dir
    ensure_dir(base)
    return base


def write_html(domain: str, content_hash: str, html: str) -> str:
    base = os.path.join(snapshot_base_dir(), "html", domain)
    ensure_dir(base)
    path = os.path.join(base, f"{content_hash}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path


def write_json(domain: str, content_hash: str, data: Any, kind: str) -> str:
    base = os.path.join(snapshot_base_dir(), "json", domain, kind)
    ensure_dir(base)
    path = os.path.join(base, f"{content_hash}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"saved_at": datetime.utcnow().isoformat(), "data": data}, f)
    return path


def download_images(domain: str, content_hash: str, urls: list[str]) -> list[str]:
    base = os.path.join(snapshot_base_dir(), "images", domain, content_hash)
    ensure_dir(base)
    saved = []
    with httpx.Client(headers={"User-Agent": settings.user_agent}) as client:
        for idx, url in enumerate(urls):
            try:
                resp, _ = request_public_url(client, url, timeout=15)
                content_type = resp.headers.get("content-type", "").lower()
                if resp.status_code != 200 or not content_type.startswith("image/"):
                    continue
                ext = "png" if "png" in content_type else "jpg"
                filename = f"{idx}.{ext}"
                path = os.path.join(base, filename)
                with open(path, "wb") as f:
                    f.write(resp.content)
                saved.append(path)
            except Exception:
                continue
    return saved
