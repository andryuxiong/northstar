import json
from typing import Any, Optional

from bs4 import BeautifulSoup


class BaseHTMLParser:
    def __init__(self, html: str):
        self.html = html
        self.soup = BeautifulSoup(html, "lxml")

    def title(self) -> Optional[str]:
        if self.soup.title and self.soup.title.string:
            return self.soup.title.string.strip()
        og = self.soup.find("meta", property="og:title")
        if og and og.get("content"):
            return og["content"].strip()
        return None

    def canonical(self) -> Optional[str]:
        link = self.soup.find("link", rel="canonical")
        return link["href"].strip() if link and link.get("href") else None

    def json_ld(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for script in self.soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                if isinstance(data, list):
                    items.extend([d for d in data if isinstance(d, dict)])
                elif isinstance(data, dict):
                    items.append(data)
                    graph = data.get("@graph")
                    if isinstance(graph, list):
                        items.extend([entry for entry in graph if isinstance(entry, dict)])
            except Exception:
                continue
        return items

    def meta(self) -> dict[str, str]:
        meta = {}
        for m in self.soup.find_all("meta"):
            key = m.get("name") or m.get("property")
            if key and m.get("content"):
                meta[key.lower()] = m["content"].strip()
        return meta
