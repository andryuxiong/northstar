"""Conservative homepage identity and conversion-surface extraction.

This collector only records publicly visible evidence.  Pattern detections are
stored with their evidence and confidence so the report can distinguish a
reliable structured-data identity from a weaker text heuristic.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.db import models


PROFILE_VERSION = "store-homepage-v3"


@dataclass
class Detection:
    key: str
    label: str
    category: str
    confidence: float
    evidence: str
    source: str = "store_homepage"


@dataclass
class IdentityCandidate:
    identity_type: str
    display_value: str
    normalized_value: str
    source_type: str
    source_url: str | None
    confidence: float
    evidence: str


@dataclass
class OfferCandidate:
    offer_type: str
    text: str
    confidence: float
    evidence: str
    discount_percent: float | None = None
    minimum_spend: float | None = None
    currency: str | None = None


@dataclass
class StoreHomepageAnalysis:
    homepage_url: str
    title: str | None
    description: str | None
    brand_name: str | None
    brand_confidence: float
    logo_url: str | None
    primary_category: str | None
    primary_country: str | None
    currency: str | None
    language: str | None
    platform: str
    theme: dict[str, Any] | None = None
    identities: list[IdentityCandidate] = field(default_factory=list)
    technologies: list[Detection] = field(default_factory=list)
    funnel_elements: list[Detection] = field(default_factory=list)
    offers: list[OfferCandidate] = field(default_factory=list)

    def as_payload(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "description": self.description,
            "brand_name": self.brand_name,
            "brand_confidence": self.brand_confidence,
            "logo_url": self.logo_url,
            "primary_category": self.primary_category,
            "primary_country": self.primary_country,
            "currency": self.currency,
            "language": self.language,
            "platform": self.platform,
            "theme": self.theme,
            "identities": [asdict(item) for item in self.identities],
            "technologies": [asdict(item) for item in self.technologies],
            "funnel_elements": [asdict(item) for item in self.funnel_elements],
            "offers": [asdict(item) for item in self.offers],
            "profile_version": PROFILE_VERSION,
        }


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = BeautifulSoup(str(value), "html.parser").get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _normalized_identity(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _json_ld_objects(soup: BeautifulSoup) -> Iterable[dict[str, Any]]:
    for script in soup.find_all("script", attrs={"type": re.compile(r"ld\+json", re.I)}):
        raw = script.string or script.get_text()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        queue: list[Any] = payload if isinstance(payload, list) else [payload]
        while queue:
            item = queue.pop(0)
            if not isinstance(item, dict):
                continue
            graph = item.get("@graph")
            if isinstance(graph, list):
                queue.extend(graph)
            yield item


def _schema_types(item: dict[str, Any]) -> set[str]:
    value = item.get("@type")
    values = value if isinstance(value, list) else [value]
    return {str(entry).lower() for entry in values if entry}


def _meta(soup: BeautifulSoup, *names: str) -> str | None:
    wanted = {name.lower() for name in names}
    for tag in soup.find_all("meta"):
        key = str(tag.get("property") or tag.get("name") or "").lower()
        if key in wanted:
            value = _clean_text(tag.get("content"))
            if value:
                return value
    return None


def _context(text: str, match: re.Match[str], radius: int = 80) -> str:
    start = max(0, match.start() - radius)
    end = min(len(text), match.end() + radius)
    return re.sub(r"\s+", " ", text[start:end]).strip()[:240]


def _detect_category(text: str) -> tuple[str | None, float]:
    categories: dict[str, tuple[str, ...]] = {
        "beauty_and_personal_care": ("skincare", "beauty", "serum", "cosmetic", "makeup", "hair care"),
        "fashion_and_accessories": ("apparel", "clothing", "dress", "jewelry", "jewellery", "handbag", "shoe"),
        "home_and_garden": ("home decor", "kitchen", "garden", "furniture", "bedding", "household"),
        "pets": ("pet", "dog", "cat", "puppy", "kitten"),
        "electronics_and_gadgets": ("gadget", "electronic", "charger", "camera", "phone", "headphone"),
        "health_and_wellness": ("wellness", "supplement", "vitamin", "fitness", "recovery", "health"),
        "baby_and_kids": ("baby", "toddler", "children", "kids", "parenting"),
        "gifts_and_hobbies": ("gift", "craft", "hobby", "collectible", "gaming"),
    }
    scores = {
        category: sum(1 for keyword in keywords if keyword in text)
        for category, keywords in categories.items()
    }
    winner, score = max(scores.items(), key=lambda item: item[1], default=(None, 0))
    if not winner or score == 0:
        return None, 0.0
    return winner, min(0.75, 0.45 + score * 0.1)


TECHNOLOGY_PATTERNS: tuple[tuple[str, str, str, tuple[str, ...], float], ...] = (
    ("shopify", "Shopify", "commerce_platform", ("cdn.shopify.com", "shopify.theme", "myshopify.com"), 0.95),
    ("woocommerce", "WooCommerce", "commerce_platform", ("woocommerce", "wc-ajax"), 0.9),
    ("judgeme", "Judge.me", "reviews", ("judge.me", "judgeme"), 0.9),
    ("loox", "Loox", "reviews", ("loox.io", "loox-rating"), 0.9),
    ("yotpo", "Yotpo", "reviews_loyalty", ("yotpo",), 0.85),
    (
        "monimo_reviews",
        "Monimo: Product Reviews",
        "reviews",
        ("areviewsapp.com", "areviewsapp", "areviews_reviews_importer"),
        0.94,
    ),
    ("klaviyo", "Klaviyo", "email", ("klaviyo",), 0.9),
    ("omnisend", "Omnisend", "email_sms", ("omnisend",), 0.9),
    ("attentive", "Attentive", "sms", ("attn.tv", "attentive"), 0.85),
    ("postscript", "Postscript", "sms", ("postscript",), 0.85),
    ("recharge", "Recharge", "subscriptions", ("rechargepayments", "rechargecdn"), 0.9),
    ("gorgias", "Gorgias", "customer_service", ("gorgias",), 0.85),
    (
        "google_analytics",
        "Google Analytics 4 / Google tag",
        "analytics",
        ("googletagmanager.com", "gtag(", "google_tag_ids", "gtag_events"),
        0.86,
    ),
    ("meta_pixel", "Meta Pixel", "advertising_measurement", ("connect.facebook.net", "fbq("), 0.85),
    ("tiktok_pixel", "TikTok Pixel", "advertising_measurement", ("analytics.tiktok.com", "ttq."), 0.85),
    ("microsoft_clarity", "Microsoft Clarity", "behavior_analytics", ("clarity.ms", "clarity("), 0.85),
    ("hotjar", "Hotjar", "behavior_analytics", ("hotjar.com", "hj("), 0.85),
    ("afterpay", "Afterpay", "buy_now_pay_later", ("afterpay",), 0.8),
    ("klarna", "Klarna", "buy_now_pay_later", ("klarna",), 0.8),
)


SHOPIFY_APP_METADATA: dict[str, tuple[str, str, str]] = {
    "judge-me-reviews": ("judgeme", "Judge.me", "reviews"),
    "judgeme": ("judgeme", "Judge.me", "reviews"),
    "kaching-bundles": ("kaching_bundles", "Kaching Bundles", "bundles_upsells"),
    "pagefly-page-builder": ("pagefly", "PageFly", "page_builder"),
    "retailed-size-chart-guide": ("retailed_size_chart", "Retailed Size Chart & Guide", "sizing"),
    "klaviyo-email-marketing-sms": ("klaviyo", "Klaviyo", "email_sms"),
    "google-youtube": ("google_youtube", "Google & YouTube", "sales_channel"),
    "seowill-seoant-ai-seo": ("seoant", "SEOAnt", "seo"),
    "orbe-geolocation": ("orbe_geolocation", "Orbe Geolocation", "localization"),
    "freegifts": ("bogos", "BOGOS: Free Gift & Buy X Get Y", "bundles_upsells"),
    "gsc-countdown-timer": ("gsc_countdown", "GSC Countdown Timer", "conversion_optimization"),
}


INFRASTRUCTURE_HOST_SUFFIXES = (
    "cdn.shopify.com",
    "shopifycdn.com",
    "shopifysvc.com",
    "shopify.jsdeliver.cloud",
    "shop.app",
    "googleapis.com",
    "gstatic.com",
    "jsdelivr.net",
    "cloudfront.net",
    "cloudflare.com",
    "cloudflareinsights.com",
    "w3.org",
)


def _resource_host_detections(
    soup: BeautifulSoup,
    homepage_url: str,
    known_detections: list[Detection],
) -> list[Detection]:
    """Surface unseen third-party storefront resources without a signature."""
    store_host = (urlparse(homepage_url).hostname or "").lower().removeprefix("www.")
    resources: dict[str, tuple[float, str]] = {}
    for tag in soup.find_all(["script", "iframe", "link"]):
        attribute = "href" if tag.name == "link" else "src"
        raw_url = tag.get(attribute)
        if not isinstance(raw_url, str) or not raw_url.strip():
            continue
        if tag.name == "link":
            rel = {str(item).lower() for item in (tag.get("rel") or [])}
            resource_type = str(tag.get("as") or "").lower()
            if not (
                rel & {"stylesheet", "modulepreload"}
                or ("preload" in rel and resource_type in {"script", "style"})
            ):
                continue
        full_url = urljoin(homepage_url, raw_url.strip())
        host = (urlparse(full_url).hostname or "").lower().removeprefix("www.")
        if not host or host == store_host or host.endswith(f".{store_host}"):
            continue
        if any(host == suffix or host.endswith(f".{suffix}") for suffix in INFRASTRUCTURE_HOST_SUFFIXES):
            continue
        confidence = 0.74 if tag.name in {"script", "iframe"} else 0.66
        if host not in resources or confidence > resources[host][0]:
            resources[host] = (confidence, full_url[:240])

    known_tokens = {
        re.sub(r"[^a-z0-9]+", "", token.lower())
        for item in known_detections
        for token in (item.key, item.label, item.evidence)
    }
    detections: list[Detection] = []
    for host, (confidence, evidence) in sorted(resources.items()):
        labels = [
            part
            for part in host.split(".")
            if part not in {"www", "cdn", "api", "app", "static", "assets", "widget", "widgets"}
        ]
        vendor = labels[-2] if len(labels) >= 2 else labels[0]
        normalized_vendor = re.sub(r"[^a-z0-9]+", "", vendor.lower())
        if normalized_vendor and any(normalized_vendor in token for token in known_tokens):
            continue
        label = re.sub(r"[-_]+", " ", vendor).strip().title() or host
        detections.append(
            Detection(
                key=f"external_integration_{re.sub(r'[^a-z0-9]+', '_', host).strip('_')}",
                label=f"{label} ({host})",
                category="unclassified_integration",
                confidence=confidence,
                evidence=evidence,
            )
        )
    return detections


def _shopify_app_detections(raw_html: str) -> list[Detection]:
    """Extract explicit public Shopify theme-app-extension declarations.

    These markers are stronger than keyword guesses: Shopify emits the app slug
    in theme block metadata such as `shopify://apps/<slug>/blocks/...`.
    Unknown slugs remain transparently labeled from that public identifier.
    """
    slug_evidence = {
        slug.lower(): f"shopify://apps/{slug.lower()}"
        for slug in re.findall(r"shopify://apps/([a-z0-9][a-z0-9-]+)", raw_html, re.I)
    }
    for slug in re.findall(
        r"cdn\.shopify\.com/extensions/[a-z0-9-]+/([a-z0-9][a-z0-9-]*?)-\d+/assets/",
        raw_html,
        re.I,
    ):
        slug_evidence.setdefault(slug.lower(), f"shopify_extension/{slug.lower()}")
    detections: list[Detection] = []
    for normalized_slug, evidence in sorted(slug_evidence.items()):
        key, label, category = SHOPIFY_APP_METADATA.get(
            normalized_slug,
            (
                f"shopify_app_{normalized_slug.replace('-', '_')}",
                re.sub(r"\s+", " ", normalized_slug.replace("-", " ")).title(),
                "shopify_app",
            ),
        )
        detections.append(
            Detection(
                key=key,
                label=label,
                category=category,
                confidence=0.96,
                evidence=evidence,
            )
        )
    return detections


FUNNEL_PATTERNS: tuple[tuple[str, str, tuple[str, ...], float], ...] = (
    ("sticky_add_to_cart", "Sticky add to cart", ("sticky-add-to-cart", "sticky_atc", "sticky cart"), 0.75),
    ("reviews", "Product reviews", ("review-widget", "reviews-widget", "jdgm-widget", "loox-rating", "yotpo"), 0.8),
    ("video_demo", "Video demonstration", ("<video", "youtube.com/embed", "vimeo.com"), 0.75),
    ("before_after", "Before and after content", ("before and after", "before-after", "before_after"), 0.7),
    ("trust_badges", "Trust badges", ("trust badge", "secure checkout", "money-back guarantee"), 0.65),
    ("faq", "FAQ", ("frequently asked questions", "faq__", "faq-"), 0.7),
    ("bundle", "Bundle offer", ("bundle and save", "frequently bought together", "bundle builder"), 0.7),
    ("quantity_break", "Quantity breaks", ("buy more save more", "quantity break", "volume discount"), 0.75),
    ("subscription", "Subscription option", ("subscribe & save", "subscribe and save", "subscription"), 0.7),
    ("free_gift", "Free gift", ("free gift",), 0.7),
    ("free_shipping", "Free-shipping message", ("free shipping",), 0.7),
    ("countdown", "Countdown timer", ("countdown-timer", "countdown timer"), 0.7),
    ("stock_urgency", "Stock urgency", ("low stock", "selling fast", "only a few left"), 0.6),
    ("email_capture", "Email capture", ("newsletter", "email-signup", "email signup"), 0.65),
    ("sms_capture", "SMS capture", ("sms signup", "text to join", "phone number"), 0.55),
    ("returns_message", "Returns messaging", ("day returns", "return policy", "easy returns"), 0.6),
    ("shipping_estimate", "Shipping estimate", ("estimated delivery", "ships within", "delivery between"), 0.6),
)


def detect_storefront_technologies(
    page_url: str,
    html: str,
    *,
    source: str = "store_homepage",
) -> list[Detection]:
    soup = BeautifulSoup(html, "lxml")
    raw_lower = html.lower()
    technologies: list[Detection] = []
    for key, label, tech_category, patterns, confidence in TECHNOLOGY_PATTERNS:
        found = next((pattern for pattern in patterns if pattern in raw_lower), None)
        if found:
            technologies.append(Detection(key, label, tech_category, confidence, found, source))
    detected_keys = {item.key for item in technologies}
    for detection in _shopify_app_detections(raw_lower):
        detection.source = source
        if detection.key not in detected_keys:
            technologies.append(detection)
            detected_keys.add(detection.key)
    for detection in _resource_host_detections(soup, page_url, technologies):
        detection.source = source
        if detection.key not in detected_keys:
            technologies.append(detection)
            detected_keys.add(detection.key)
    return technologies


def _shopify_theme(html: str) -> dict[str, Any] | None:
    match = re.search(r"Shopify\.theme\s*=\s*(\{.*?\})\s*;", html, re.I | re.S)
    if not match:
        return None
    try:
        payload = json.loads(match.group(1))
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return {
        "name": payload.get("name"),
        "schema_name": payload.get("schema_name"),
        "schema_version": payload.get("schema_version"),
        "theme_id": payload.get("id"),
        "theme_store_id": payload.get("theme_store_id"),
        "role": payload.get("role"),
        "confidence": 0.98,
        "evidence": "Shopify.theme",
    }


def analyze_store_homepage(homepage_url: str, html: str) -> StoreHomepageAnalysis:
    soup = BeautifulSoup(html, "lxml")
    raw_lower = html.lower()
    visible_text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).lower()
    title = _clean_text(soup.title.string if soup.title and soup.title.string else None)
    description = _meta(soup, "description", "og:description")
    language = _clean_text(soup.html.get("lang")) if soup.html else None

    brand_candidates: list[tuple[str, float, str, str | None]] = []
    logo_url = None
    primary_country = None
    currency = _meta(soup, "product:price:currency", "og:price:currency")
    schema_socials: list[str] = []
    for item in _json_ld_objects(soup):
        types = _schema_types(item)
        if types & {"organization", "brand", "localbusiness", "store", "webSite".lower()}:
            name = _clean_text(item.get("name"))
            if name:
                brand_candidates.append((name, 0.94, "structured_data", homepage_url))
            logo = item.get("logo")
            if isinstance(logo, dict):
                logo = logo.get("url") or logo.get("contentUrl")
            if isinstance(logo, str) and not logo_url:
                logo_url = urljoin(homepage_url, logo)
            same_as = item.get("sameAs") or []
            if isinstance(same_as, str):
                same_as = [same_as]
            schema_socials.extend(str(url) for url in same_as if isinstance(url, str))
            address = item.get("address")
            if isinstance(address, dict) and not primary_country:
                primary_country = _clean_text(address.get("addressCountry"))

    site_name = _meta(soup, "og:site_name", "application-name")
    if site_name:
        brand_candidates.append((site_name, 0.88, "open_graph", homepage_url))
    logo = soup.find("img", alt=re.compile(r"logo", re.I))
    if logo:
        logo_alt = _clean_text(logo.get("alt"))
        if logo_alt and logo_alt.lower() not in {"logo", "store logo"}:
            brand_candidates.append((re.sub(r"\s*[|—-]?\s*logo\s*$", "", logo_alt, flags=re.I), 0.72, "logo_alt", homepage_url))
        if not logo_url and logo.get("src"):
            logo_url = urljoin(homepage_url, str(logo.get("src")))
    if title:
        title_brand = re.split(r"\s+[|—–]\s+|\s+-\s+", title, maxsplit=1)[0].strip()
        if title_brand and title_brand.lower() not in {"home", "online store", "shop"}:
            brand_candidates.append((title_brand, 0.62, "page_title", homepage_url))

    domain_label = urlparse(homepage_url).hostname or ""
    domain_label = domain_label.removeprefix("www.").split(".")[0]
    domain_brand = re.sub(r"[-_]", " ", domain_label).title()
    if domain_brand:
        brand_candidates.append((domain_brand, 0.4, "domain", homepage_url))
    brand_candidates.sort(key=lambda item: item[1], reverse=True)
    brand_name = brand_candidates[0][0] if brand_candidates else None
    brand_confidence = brand_candidates[0][1] if brand_candidates else 0.0

    identities: list[IdentityCandidate] = []
    if brand_name:
        identities.append(
            IdentityCandidate(
                identity_type="brand",
                display_value=brand_name,
                normalized_value=_normalized_identity(brand_name),
                source_type=brand_candidates[0][2],
                source_url=homepage_url,
                confidence=brand_confidence,
                evidence=brand_candidates[0][0],
            )
        )

    social_urls = list(schema_socials)
    social_urls.extend(str(link.get("href")) for link in soup.find_all("a", href=True))
    seen_socials: set[tuple[str, str]] = set()
    for raw_url in social_urls:
        full_url = urljoin(homepage_url, raw_url)
        host = (urlparse(full_url).hostname or "").lower()
        if "facebook.com" in host:
            kind = "facebook"
        elif "instagram.com" in host:
            kind = "instagram"
        else:
            continue
        path = urlparse(full_url).path.strip("/").split("/")[0]
        if not path or path.lower() in {"share", "sharer", "dialog"}:
            continue
        key = (kind, path.lower())
        if key in seen_socials:
            continue
        seen_socials.add(key)
        identities.append(
            IdentityCandidate(
                identity_type=kind,
                display_value=path,
                normalized_value=_normalized_identity(path),
                source_type="organization_schema" if raw_url in schema_socials else "homepage_link",
                source_url=full_url,
                confidence=0.9 if raw_url in schema_socials else 0.78,
                evidence=full_url,
            )
        )

    if not primary_country:
        country_match = re.search(r'"(?:countryCode|country_code)"\s*:\s*"([A-Z]{2})"', html)
        if country_match:
            primary_country = country_match.group(1)
    if primary_country:
        country_aliases = {
            "canada": "CA",
            "united states": "US",
            "united states of america": "US",
            "united kingdom": "GB",
            "great britain": "GB",
            "australia": "AU",
        }
        normalized_country = primary_country.strip()
        primary_country = (
            normalized_country.upper()
            if len(normalized_country) == 2
            else country_aliases.get(normalized_country.lower())
        )
    if not currency:
        currency_match = re.search(r'"(?:currencyCode|currency_code|currency)"\s*:\s*"([A-Z]{3})"', html)
        if currency_match:
            currency = currency_match.group(1)

    platform = "unknown"
    if any(pattern in raw_lower for pattern in ("cdn.shopify.com", "myshopify.com", "shopify.theme")):
        platform = "shopify"
    elif any(pattern in raw_lower for pattern in ("woocommerce", "wc-ajax")):
        platform = "woocommerce"

    category, _ = _detect_category(" ".join(part for part in (title or "", description or "", visible_text[:5000]) if part))

    technologies = detect_storefront_technologies(homepage_url, html)

    funnel_elements: list[Detection] = []
    for key, label, patterns, confidence in FUNNEL_PATTERNS:
        found = next((pattern for pattern in patterns if pattern in raw_lower or pattern in visible_text), None)
        if found:
            funnel_elements.append(Detection(key, label, "conversion", confidence, found))

    offers: list[OfferCandidate] = []
    offer_patterns: tuple[tuple[str, re.Pattern[str], float], ...] = (
        ("percentage_discount", re.compile(r"\b(\d{1,2})%\s+off\b", re.I), 0.78),
        ("free_shipping", re.compile(r"\bfree\s+shipping(?:\s+on\s+orders?\s+(?:over|above)\s+[$£€]?\s*(\d+(?:\.\d{1,2})?))?", re.I), 0.78),
        ("buy_one_get_one", re.compile(r"\b(?:buy\s+one\s+get\s+one|bogo)\b", re.I), 0.82),
        ("buy_x_get_y", re.compile(r"\bbuy\s+(\d+)\s+get\s+(\d+)\b", re.I), 0.8),
        ("free_gift", re.compile(r"\bfree\s+gift\b", re.I), 0.72),
        ("first_order_discount", re.compile(r"\b(?:first|your first)\s+order\b.{0,50}\b(?:off|discount)\b", re.I), 0.65),
    )
    seen_offers: set[tuple[str, str]] = set()
    for offer_type, pattern, confidence in offer_patterns:
        for match in list(pattern.finditer(visible_text))[:3]:
            snippet = _context(visible_text, match)
            key = (offer_type, snippet)
            if key in seen_offers:
                continue
            seen_offers.add(key)
            discount_percent = None
            minimum_spend = None
            if offer_type == "percentage_discount":
                discount_percent = float(match.group(1))
            elif offer_type == "free_shipping" and match.group(1):
                minimum_spend = float(match.group(1))
            offers.append(
                OfferCandidate(
                    offer_type=offer_type,
                    text=snippet,
                    confidence=confidence,
                    evidence=match.group(0),
                    discount_percent=discount_percent,
                    minimum_spend=minimum_spend,
                    currency=currency,
                )
            )

    return StoreHomepageAnalysis(
        homepage_url=homepage_url,
        title=title,
        description=description,
        brand_name=brand_name,
        brand_confidence=brand_confidence,
        logo_url=logo_url,
        primary_category=category,
        primary_country=primary_country,
        currency=currency,
        language=language,
        platform=platform,
        theme=_shopify_theme(html),
        identities=identities,
        technologies=technologies,
        funnel_elements=funnel_elements,
        offers=offers,
    )


def persist_store_homepage_analysis(
    db: Session,
    *,
    store: models.Store,
    source: models.SourceUrl,
    analysis: StoreHomepageAnalysis,
) -> models.StoreProfile:
    now = datetime.utcnow()
    profile = db.query(models.StoreProfile).filter(models.StoreProfile.store_id == store.id).first()
    payload = analysis.as_payload()
    if not profile:
        profile = models.StoreProfile(
            workspace_id=store.workspace_id,
            store_id=store.id,
            first_observed_at=now,
        )
        db.add(profile)
    profile.brand_name = analysis.brand_name
    profile.primary_category = analysis.primary_category
    profile.primary_country = analysis.primary_country
    profile.homepage_url = analysis.homepage_url
    profile.logo_url = analysis.logo_url
    profile.description = analysis.description
    profile.currency = analysis.currency
    profile.language = analysis.language
    profile.attributes_json = payload
    profile.profile_version = PROFILE_VERSION
    profile.last_observed_at = now

    for identity in analysis.identities:
        record = (
            db.query(models.StoreIdentity)
            .filter(
                models.StoreIdentity.store_id == store.id,
                models.StoreIdentity.identity_type == identity.identity_type,
                models.StoreIdentity.normalized_value == identity.normalized_value,
            )
            .first()
        )
        if not record:
            record = models.StoreIdentity(
                workspace_id=store.workspace_id,
                store_id=store.id,
                identity_type=identity.identity_type,
                normalized_value=identity.normalized_value,
                first_seen_at=now,
            )
            db.add(record)
        record.display_value = identity.display_value
        record.source_type = identity.source_type
        record.source_url = identity.source_url
        record.confidence_score = identity.confidence
        record.evidence_json = {"evidence": identity.evidence, "collector_version": PROFILE_VERSION}
        record.last_seen_at = now

    if analysis.platform == "shopify":
        store.platform_guess = models.PlatformGuess.shopify
    elif analysis.platform == "woocommerce":
        store.platform_guess = models.PlatformGuess.woocommerce
    store.last_seen_at = now
    db.add(
        models.StoreSnapshot(
            store_id=store.id,
            product_count=db.query(models.Product).filter(models.Product.store_id == store.id).count(),
            collections_count=None,
            raw_extracted_json={
                "profile": payload,
                "source_url_id": source.id,
                "collector_version": PROFILE_VERSION,
            },
        )
    )
    db.commit()
    db.refresh(profile)
    return profile
