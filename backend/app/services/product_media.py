"""Resolve product media from normalized snapshots with a saved-HTML fallback."""

from __future__ import annotations

from functools import lru_cache
from html import unescape
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlparse

from app.core.config import settings
from app.services.parsers.generic import GenericProductParser
from app.services.parsers.shopify import ShopifyParser


def product_image_url(
    canonical_url: str,
    snapshot: Any | None,
    *,
    snapshot_dir: str | None = None,
) -> str | None:
    if snapshot is None:
        return None
    images = snapshot.images_json if isinstance(snapshot.images_json, list) else []
    direct = next((str(item).strip() for item in images if str(item).strip()), None)
    if direct:
        return direct
    content_hash = getattr(snapshot, "content_hash", None)
    if not content_hash:
        return None
    domain = (urlparse(canonical_url).hostname or "").lower()
    if not domain:
        return None
    base = snapshot_dir or settings.snapshot_dir
    return _saved_html_image(str(Path(base).resolve()), domain, str(content_hash))


@lru_cache(maxsize=2048)
def _saved_html_image(snapshot_dir: str, domain: str, content_hash: str) -> str | None:
    path = Path(snapshot_dir) / "html" / domain / f"{content_hash}.html"
    try:
        html = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    meta_image = _open_graph_image(html)
    if meta_image:
        return meta_image
    parser = ShopifyParser(html) if ShopifyParser.is_shopify(html) else GenericProductParser(html)
    extracted = parser.parse() or {}
    images = extracted.get("images") if isinstance(extracted.get("images"), list) else []
    return next((str(item).strip() for item in images if str(item).strip()), None)


def _open_graph_image(html: str) -> str | None:
    for match in re.finditer(r"<meta\b[^>]*>", html, re.I):
        tag = match.group(0)
        key = re.search(r"(?:property|name)\s*=\s*(['\"])(.*?)\1", tag, re.I)
        if not key or key.group(2).strip().lower() not in {"og:image", "twitter:image"}:
            continue
        content = re.search(r"content\s*=\s*(['\"])(.*?)\1", tag, re.I | re.S)
        if content and content.group(2).strip():
            return unescape(content.group(2).strip())
    return None
