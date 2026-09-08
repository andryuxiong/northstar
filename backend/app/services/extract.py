from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


PRODUCT_HINTS = ["/products/", "/product/"]


def extract_product_urls(base_url: str, html: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    urls = set()
    for a in soup.find_all("a"):
        href = a.get("href")
        if not href:
            continue
        full = urljoin(base_url, href)
        path = urlparse(full).path.lower()
        if any(h in path for h in PRODUCT_HINTS):
            urls.add(full)
    return list(urls)
