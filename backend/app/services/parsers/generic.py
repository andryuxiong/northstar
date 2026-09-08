from typing import Any, Optional

from app.services.parsers.base import BaseHTMLParser


class GenericProductParser(BaseHTMLParser):
    def parse(self) -> Optional[dict[str, Any]]:
        data = self._parse_json_ld()
        if data:
            return data
        data = self._parse_meta_tags()
        if data:
            return data
        return None

    def _parse_json_ld(self) -> Optional[dict[str, Any]]:
        for item in self.json_ld():
            if item.get("@type") == "Product":
                offers = item.get("offers") or {}
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}
                price = _safe_float(offers.get("price"))
                currency = offers.get("priceCurrency")
                availability = str(offers.get("availability") or "").lower()
                available = None
                if availability:
                    available = not any(
                        marker in availability
                        for marker in ("outofstock", "soldout", "discontinued")
                    )
                images = item.get("image") or []
                if isinstance(images, str):
                    images = [images]
                return {
                    "external_id": item.get("productID") or item.get("@id"),
                    "brand": (item.get("brand") or {}).get("name") if isinstance(item.get("brand"), dict) else item.get("brand"),
                    "title": item.get("name") or self.title(),
                    "description": item.get("description"),
                    "currency": currency,
                    "images": images,
                    "variants": [
                        {
                            "title": item.get("name") or self.title(),
                            "price": price,
                            "compare_at_price": None,
                            "available": available,
                            "sku": item.get("sku"),
                        }
                    ],
                }
        return None

    def _parse_meta_tags(self) -> Optional[dict[str, Any]]:
        meta = self.meta()
        title = meta.get("og:title") or self.title()
        price = _safe_float(meta.get("product:price:amount") or meta.get("price"))
        currency = meta.get("product:price:currency")
        image = meta.get("og:image")
        if title or price or image:
            return {
                "title": title,
                "description": meta.get("og:description"),
                "currency": currency,
                "images": [image] if image else [],
                "variants": [
                    {
                        "title": title,
                        "price": price,
                        "compare_at_price": None,
                        "available": True,
                        "sku": None,
                    }
                ],
            }
        return None


def _safe_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except Exception:
        return None
