import json
import re
from typing import Any, Optional

from app.services.parsers.base import BaseHTMLParser


class ShopifyParser(BaseHTMLParser):
    @staticmethod
    def is_shopify(html: str) -> bool:
        patterns = ["cdn.shopify.com", "Shopify", "shopify" ]
        return any(p in html for p in patterns)

    def parse(self) -> Optional[dict[str, Any]]:
        # Shopify's product JSON normally contains richer variant,
        # compare-at-price, SKU, and availability data than JSON-LD.
        product_json = self._parse_product_json_script()
        json_ld = self._parse_json_ld_product()
        if not product_json:
            return json_ld
        if not json_ld:
            return self._with_meta_image_fallback(product_json)

        # Shopify's `meta.product` object commonly has the best variant and
        # identity fields but no product images. Merge complementary public
        # JSON-LD fields instead of discarding them just because the richer
        # object was found first.
        merged = dict(product_json)
        for key in ("title", "description", "currency", "vendor"):
            if not merged.get(key) and json_ld.get(key):
                merged[key] = json_ld[key]
        merged["images"] = _dedupe_images(
            [*(product_json.get("images") or []), *(json_ld.get("images") or [])]
        )
        return self._with_meta_image_fallback(merged)

    def _with_meta_image_fallback(self, data: dict[str, Any]) -> dict[str, Any]:
        if data.get("images"):
            return data
        image = self.meta().get("og:image") or self.meta().get("twitter:image")
        if not image:
            return data
        return {**data, "images": [image]}

    def _parse_json_ld_product(self) -> Optional[dict[str, Any]]:
        for item in self.json_ld():
            if item.get("@type") == "Product":
                offers = item.get("offers") or {}
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}
                price = _safe_float(offers.get("price"))
                currency = offers.get("priceCurrency")
                images = _normalize_images(item.get("image"))
                return {
                    "external_id": item.get("productID") or item.get("@id"),
                    "handle": None,
                    "vendor": (item.get("brand") or {}).get("name") if isinstance(item.get("brand"), dict) else item.get("brand"),
                    "title": item.get("name"),
                    "description": item.get("description"),
                    "currency": currency,
                    "images": images,
                    "variants": [
                        {
                            "title": item.get("name"),
                            "price": price,
                            "compare_at_price": None,
                            "available": True,
                            "sku": item.get("sku"),
                        }
                    ],
                }
        return None

    def _parse_product_json_script(self) -> Optional[dict[str, Any]]:
        scripts = self.soup.find_all("script")
        for script in scripts:
            if not script.string:
                continue
            if "var meta" in script.string and "product" in script.string:
                json_blob = _extract_json_object(script.string)
                if json_blob and isinstance(json_blob, dict) and "product" in json_blob:
                    return _from_shopify_product(json_blob["product"])
            if "ProductJson" in (script.get("id") or ""):
                try:
                    payload = json.loads(script.string)
                    return _from_shopify_product(payload)
                except Exception:
                    continue
        return None


def _from_shopify_product(product: dict[str, Any]) -> dict[str, Any]:
    variants = []
    for v in product.get("variants", []):
        variants.append(
            {
                "title": v.get("title") or product.get("title"),
                "price": _safe_float(v.get("price")) / 100 if v.get("price") else None,
                "compare_at_price": _safe_float(v.get("compare_at_price")) / 100 if v.get("compare_at_price") else None,
                "available": bool(v.get("available", True)),
                "sku": v.get("sku"),
            }
        )
    images = _normalize_images(product.get("images"))
    return {
        "external_id": str(product.get("id")) if product.get("id") is not None else None,
        "handle": product.get("handle"),
        "vendor": product.get("vendor"),
        "product_type": product.get("type") or product.get("product_type"),
        "title": product.get("title"),
        "description": product.get("body_html"),
        "currency": product.get("currency") or product.get("presentment_currency"),
        "images": images,
        "variants": variants,
    }


def _safe_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except Exception:
        return None


def _normalize_images(value: Any) -> list[str]:
    values = value if isinstance(value, list) else [value]
    images: list[str] = []
    for item in values:
        if isinstance(item, str) and item.strip():
            images.append(item.strip())
        elif isinstance(item, dict):
            image = item.get("url") or item.get("contentUrl") or item.get("src")
            if isinstance(image, str) and image.strip():
                images.append(image.strip())
    return _dedupe_images(images)


def _dedupe_images(images: list[str]) -> list[str]:
    return list(dict.fromkeys(image for image in images if image))


def _extract_json_object(text: str) -> Optional[dict[str, Any]]:
    match = re.search(r"var meta\s*=\s*(\{.*\});", text, re.DOTALL)
    if not match:
        return None
    blob = match.group(1)
    try:
        return json.loads(blob)
    except Exception:
        return None
