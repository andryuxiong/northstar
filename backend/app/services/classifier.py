from urllib.parse import urlparse

from app.db.models import SourceUrlType


def classify_url(url: str) -> SourceUrlType:
    parsed = urlparse(url)
    path = (parsed.path or "").lower()
    if path.endswith("/sitemap.xml") or "sitemap" in path:
        return SourceUrlType.sitemap
    if "/collections" in path:
        return SourceUrlType.collection
    if "/products" in path or "/product" in path:
        return SourceUrlType.product
    if path == "" or path == "/":
        return SourceUrlType.store
    return SourceUrlType.landing_page


def extract_domain(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc.lower()
