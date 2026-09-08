"""Build and persist the unified Store Intelligence Report.

The orchestrator consumes only collected records and versioned pure
estimators. Unsupported sections return explicit missing signals rather than
zeros or synthetic demo values.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.db import models
from app.core.config import settings
from app.services.product_media import product_image_url
from app.services.store_profile import analyze_store_homepage, detect_storefront_technologies
from app.services.traffic import TRAFFIC_DATA_NOTICE, normalize_traffic_observations
from app.utils.hashing import sha256_text
from app.workers.runner import recent_jobs

from .assumptions import DEFAULT_ASSUMPTIONS, EstimatorAssumptions
from .estimators import (
    AOV_ESTIMATOR_VERSION,
    Evidence,
    MerchandiseObservation,
    ORDERS_ESTIMATOR_VERSION,
    PRODUCT_MOMENTUM_ESTIMATOR_VERSION,
    REVENUE_ESTIMATOR_VERSION,
    TRAFFIC_ESTIMATOR_VERSION,
    TrafficObservation as EstimatorTrafficObservation,
    classify_sellable_merchandise,
    estimate_aov,
    estimate_gross_revenue,
    estimate_orders,
    estimate_product_momentum,
    estimate_traffic,
)
from .types import InsightResult


REPORT_VERSION = "store-intelligence-v1"
EVIDENCE_COLLECTOR_VERSION = "report-evidence-v1"
GENERAL_CATEGORY = "general_ecommerce"

TECHNOLOGY_ICON_DOMAINS = {
    "shopify": "shopify.com",
    "judgeme": "judge.me",
    "monimo_reviews": "areviewsapp.com",
    "klaviyo": "klaviyo.com",
    "google_analytics": "analytics.google.com",
    "google_youtube": "google.com",
    "hotjar": "hotjar.com",
    "kaching_bundles": "kachingappz.com",
    "pagefly": "pagefly.io",
    "bogos": "bogos.io",
    "orbe_geolocation": "orbe.app",
    "seoant": "seoant.com",
    "vimeo": "vimeo.com",
}


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_safe(item) for item in value]
    return value


def _enum_value(value: Any) -> str:
    return getattr(value, "value", value) or "unknown"


def _confidence_label(score: float | Decimal, *, required: bool = False) -> str:
    value = float(score)
    if required and value < 0.25:
        return "insufficient_data"
    if value >= 0.75:
        return "high"
    if value >= 0.50:
        return "medium"
    if value >= 0.25:
        return "low"
    return "insufficient_data"


def _evidence_payload(item: Evidence, *, evidence_id: int | None = None) -> dict[str, Any]:
    return {
        "id": evidence_id,
        "type": item.evidence_type,
        "label": item.evidence_type.replace("_", " ").title(),
        "value": _json_safe(item.value),
        "source": item.source,
        "observed_at": _json_safe(item.observed_at),
        "source_url": None,
        "reliability": float(item.reliability),
        "independence_group": item.independence_group,
        "detail": item.details,
    }


def insight_payload(result: InsightResult, calculated_at: datetime) -> dict[str, Any]:
    return {
        "metric": result.metric,
        "status": result.status,
        "low": float(result.low) if result.low is not None else None,
        "central": float(result.central) if result.central is not None else None,
        "high": float(result.high) if result.high is not None else None,
        "value": result.classification,
        "score": float(result.score) if result.score is not None else None,
        "unit": result.unit,
        "currency": result.currency,
        "confidence_score": float(result.confidence_score),
        "confidence_label": result.confidence_label,
        "evidence": [_evidence_payload(item) for item in result.evidence],
        "assumptions": _json_safe(dict(result.assumptions)),
        "missing_signals": list(result.missing_signals),
        "explanation": result.explanation,
        "estimator_version": result.estimator_version,
        "calculated_at": calculated_at,
    }


def unsupported_result(
    metric: str,
    *,
    missing: Iterable[str],
    explanation: str,
    evidence: Iterable[Evidence] = (),
    version: str = "availability-v1",
) -> InsightResult:
    missing_signals = tuple(dict.fromkeys(missing)) or ("required_public_evidence",)
    return InsightResult(
        metric=metric,
        status="insufficient_data",
        confidence_score=Decimal("0"),
        confidence_label="insufficient_data",
        evidence=tuple(evidence),
        assumptions={"missing_values_are_not_treated_as_zero": True},
        missing_signals=missing_signals,
        explanation=explanation,
        estimator_version=version,
    )


def unsupported_insight(
    metric: str,
    *,
    missing: Iterable[str],
    explanation: str,
    calculated_at: datetime,
    evidence: Iterable[Evidence] = (),
    version: str = "availability-v1",
) -> dict[str, Any]:
    return insight_payload(
        unsupported_result(
            metric,
            missing=missing,
            explanation=explanation,
            evidence=evidence,
            version=version,
        ),
        calculated_at,
    )


def get_or_create_default_profile(
    db: Session,
    workspace_id: int,
    category_key: str = GENERAL_CATEGORY,
) -> models.EstimationProfile:
    profile = (
        db.query(models.EstimationProfile)
        .filter(
            models.EstimationProfile.workspace_id == workspace_id,
            models.EstimationProfile.category_key == category_key,
            models.EstimationProfile.is_default.is_(True),
        )
        .order_by(models.EstimationProfile.id.asc())
        .first()
    )
    if profile:
        return profile
    if category_key != GENERAL_CATEGORY:
        # Unknown categories inherit the disclosed general profile until the
        # user deliberately creates an active version for that category.
        return get_or_create_default_profile(db, workspace_id, GENERAL_CATEGORY)
    defaults = DEFAULT_ASSUMPTIONS
    profile = models.EstimationProfile(
        workspace_id=workspace_id,
        name="Personal planning defaults",
        category_key=GENERAL_CATEGORY,
        version="estimation-profile-v1",
        is_default=True,
        conversion_rate_low=defaults.conversion_rate_low,
        conversion_rate_central=defaults.conversion_rate_central,
        conversion_rate_high=defaults.conversion_rate_high,
        basket_multiplier_low=defaults.items_per_order_low,
        basket_multiplier_central=defaults.items_per_order_central,
        basket_multiplier_high=defaults.items_per_order_high,
        traffic_reliability_low=defaults.traffic_envelope_low,
        traffic_reliability_central=Decimal("1"),
        traffic_reliability_high=defaults.traffic_envelope_high,
        minimum_evidence_count=defaults.momentum_minimum_groups,
        freshness_limit_days=defaults.freshness_days,
        score_weights_json={key: str(value) for key, value in defaults.momentum_weights},
        thresholds_json={
            "minimum_sellable_products": defaults.minimum_sellable_products,
            "traffic_monthly_direction": str(defaults.traffic_monthly_direction_threshold),
            "traffic_endpoint_direction": str(defaults.traffic_endpoint_direction_threshold),
            "momentum_minimum_span_days": defaults.momentum_minimum_span_days,
        },
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def assumptions_from_profile(profile: models.EstimationProfile) -> EstimatorAssumptions:
    thresholds = profile.thresholds_json or {}
    weights = profile.score_weights_json or {}
    default_weight_map = DEFAULT_ASSUMPTIONS.momentum_weight_map
    if weights:
        if set(weights) != set(default_weight_map):
            raise ValueError("Estimation profile has unknown or missing product evidence groups")
        configured_weights = [
            (group, Decimal(str(weights[group]))) for group in default_weight_map
        ]
        if sum(weight for _, weight in configured_weights) != Decimal("1"):
            raise ValueError("Estimation profile product evidence weights must sum to 1")
    else:
        configured_weights = list(DEFAULT_ASSUMPTIONS.momentum_weights)
    if profile.minimum_evidence_count > sum(weight > 0 for _, weight in configured_weights):
        raise ValueError("Minimum evidence count exceeds enabled product evidence groups")
    return EstimatorAssumptions(
        conversion_rate_low=Decimal(str(profile.conversion_rate_low)),
        conversion_rate_central=Decimal(str(profile.conversion_rate_central or profile.conversion_rate_low)),
        conversion_rate_high=Decimal(str(profile.conversion_rate_high)),
        items_per_order_low=Decimal(str(profile.basket_multiplier_low)),
        items_per_order_central=Decimal(str(profile.basket_multiplier_central or profile.basket_multiplier_low)),
        items_per_order_high=Decimal(str(profile.basket_multiplier_high)),
        traffic_envelope_low=Decimal(str(profile.traffic_reliability_low)),
        traffic_envelope_high=Decimal(str(profile.traffic_reliability_high)),
        freshness_days=profile.freshness_limit_days,
        minimum_sellable_products=int(
            thresholds.get("minimum_sellable_products", DEFAULT_ASSUMPTIONS.minimum_sellable_products)
        ),
        traffic_monthly_direction_threshold=Decimal(
            str(thresholds.get("traffic_monthly_direction", DEFAULT_ASSUMPTIONS.traffic_monthly_direction_threshold))
        ),
        traffic_endpoint_direction_threshold=Decimal(
            str(thresholds.get("traffic_endpoint_direction", DEFAULT_ASSUMPTIONS.traffic_endpoint_direction_threshold))
        ),
        momentum_minimum_groups=profile.minimum_evidence_count,
        momentum_minimum_span_days=int(
            thresholds.get("momentum_minimum_span_days", DEFAULT_ASSUMPTIONS.momentum_minimum_span_days)
        ),
        momentum_weights=tuple(configured_weights),
    )


def profile_payload(profile: models.EstimationProfile) -> dict[str, Any]:
    return {
        "id": profile.id,
        "name": profile.name,
        "category_key": profile.category_key,
        "is_default": profile.is_default,
        "version": profile.version,
        "conversion_rate_low": float(profile.conversion_rate_low),
        "conversion_rate_central": float(profile.conversion_rate_central) if profile.conversion_rate_central is not None else None,
        "conversion_rate_high": float(profile.conversion_rate_high),
        "basket_multiplier_low": float(profile.basket_multiplier_low),
        "basket_multiplier_central": float(profile.basket_multiplier_central) if profile.basket_multiplier_central is not None else None,
        "basket_multiplier_high": float(profile.basket_multiplier_high),
        "traffic_reliability_low": float(profile.traffic_reliability_low),
        "traffic_reliability_central": float(profile.traffic_reliability_central) if profile.traffic_reliability_central is not None else None,
        "traffic_reliability_high": float(profile.traffic_reliability_high),
        "freshness_limit_days": profile.freshness_limit_days,
        "minimum_evidence_count": profile.minimum_evidence_count,
        "score_weights": {key: float(value) for key, value in (profile.score_weights_json or {}).items()},
        "thresholds": profile.thresholds_json or {},
        "updated_at": profile.updated_at,
    }


def _normalized_traffic(
    db: Session,
    store: models.Store,
) -> tuple[list[EstimatorTrafficObservation], list[dict[str, Any]], list[models.TrafficObservation]]:
    snapshots = (
        db.query(models.TrafficSnapshot)
        .filter(
            models.TrafficSnapshot.workspace_id == store.workspace_id,
            models.TrafficSnapshot.store_id == store.id,
        )
        .order_by(models.TrafficSnapshot.fetched_at.asc())
        .all()
    )
    for snapshot in snapshots:
        normalize_traffic_observations(db, snapshot)
    rows = (
        db.query(models.TrafficObservation)
        .filter(
            models.TrafficObservation.workspace_id == store.workspace_id,
            models.TrafficObservation.store_id == store.id,
            models.TrafficObservation.metric_key.in_(["monthly_visits", "global_rank"]),
        )
        .order_by(models.TrafficObservation.period_start.asc(), models.TrafficObservation.retrieved_at.asc())
        .all()
    )
    period_rows: dict[tuple[str, date], dict[str, models.TrafficObservation]] = {}
    for row in rows:
        key = (row.provider, row.period_start)
        current = period_rows.setdefault(key, {})
        previous = current.get(row.metric_key)
        if previous is None or row.retrieved_at >= previous.retrieved_at:
            current[row.metric_key] = row

    estimator_rows: list[EstimatorTrafficObservation] = []
    display_rows: list[dict[str, Any]] = []
    for (provider, period), metrics in sorted(period_rows.items(), key=lambda item: item[0][1]):
        visits_row = metrics.get("monthly_visits")
        rank_row = metrics.get("global_rank")
        newest = max(
            (row for row in (visits_row, rank_row) if row is not None),
            key=lambda row: row.retrieved_at,
        )
        visit_retrieved_at = visits_row.retrieved_at if visits_row else newest.retrieved_at
        estimator_rows.append(
            EstimatorTrafficObservation(
                period=period.strftime("%Y-%m"),
                visits=visits_row.value_numeric if visits_row else None,
                retrieved_at=visit_retrieved_at,
                provider=provider,
                fetch_status=visits_row.status if visits_row else newest.status,
                global_rank=int(rank_row.value_numeric) if rank_row and rank_row.value_numeric is not None else None,
            )
        )
        display_rows.append(
            {
                "period": period.strftime("%Y-%m"),
                "visits": float(visits_row.value_numeric) if visits_row and visits_row.value_numeric is not None else None,
                "global_rank": int(rank_row.value_numeric) if rank_row and rank_row.value_numeric is not None else None,
                "status": visits_row.status if visits_row else newest.status,
                "source": provider,
                "observed_at": visit_retrieved_at,
            }
        )
    return estimator_rows, display_rows, rows


def _latest_product_rows(
    db: Session,
    store: models.Store,
) -> list[tuple[models.Product, models.ProductSnapshot | None, list[models.ProductSnapshot]]]:
    products = (
        db.query(models.Product)
        .filter(models.Product.workspace_id == store.workspace_id, models.Product.store_id == store.id)
        .order_by(models.Product.created_at.asc())
        .all()
    )
    latest_store_snapshot = (
        db.query(models.StoreSnapshot)
        .filter(models.StoreSnapshot.store_id == store.id)
        .order_by(models.StoreSnapshot.fetched_at.desc())
        .first()
    )
    if latest_store_snapshot:
        current_products = [
            product
            for product in products
            if product.last_seen_at >= latest_store_snapshot.fetched_at
        ]
        if current_products:
            products = current_products
    result = []
    for product in products:
        snapshots = (
            db.query(models.ProductSnapshot)
            .filter(models.ProductSnapshot.product_id == product.id)
            .order_by(models.ProductSnapshot.fetched_at.asc())
            .all()
        )
        result.append((product, snapshots[-1] if snapshots else None, snapshots))
    return result


def _representative_product_price(snapshot: models.ProductSnapshot | None) -> Decimal | None:
    """Prefer a median observed variant price over a cheapest-variant anchor."""

    if not snapshot:
        return None
    variants = (snapshot.raw_extracted_json or {}).get("variants") or []
    prices: list[Decimal] = []
    for variant in variants:
        if not isinstance(variant, dict) or variant.get("price") is None:
            continue
        try:
            price = Decimal(str(variant["price"]))
        except Exception:
            continue
        if price.is_finite() and price > 0:
            prices.append(price)
    if prices:
        prices.sort()
        middle = len(prices) // 2
        return (
            prices[middle]
            if len(prices) % 2
            else (prices[middle - 1] + prices[middle]) / Decimal("2")
        )
    if snapshot.price_min is not None and snapshot.price_max is not None:
        return (Decimal(str(snapshot.price_min)) + Decimal(str(snapshot.price_max))) / Decimal("2")
    if snapshot.price_min is not None:
        return Decimal(str(snapshot.price_min))
    return None


def _product_kind_from_public_url(product: models.Product) -> str | None:
    path = (urlparse(product.canonical_url).path or "").lower()
    if "free-gift" in path or "free_gift" in path:
        return "free_gift"
    if any(marker in path for marker in ("shipping-protection", "package-protection", "shipping-insurance")):
        return "shipping_protection"
    if "warranty" in path:
        return "warranty"
    if "gift-card" in path:
        return "gift_card"
    return None


def _display_product_title(
    product: models.Product,
    snapshots: list[models.ProductSnapshot],
    store_profile: models.StoreProfile | None,
) -> str:
    candidates = [product.title, *(snapshot.title for snapshot in snapshots if snapshot.title)]
    cleaned: list[str] = []
    for candidate in candidates:
        value = re.split(r"\s*[\n\r]+\s*|\s+[—–]\s+", candidate, maxsplit=1)[0].strip()
        if value and value not in cleaned:
            cleaned.append(value)
    if not cleaned:
        return product.title
    prefers_latin = bool(store_profile and (store_profile.language or "").lower().startswith("en"))

    def score(value: str) -> tuple[float, int]:
        letters = [character for character in value if character.isalpha()]
        latin = sum(
            ("a" <= character.lower() <= "z")
            or "\u00c0" <= character <= "\u024f"
            for character in letters
        )
        latin_ratio = latin / len(letters) if letters else 0
        return (latin_ratio if prefers_latin else 0.5, -len(value))

    return max(cleaned, key=score)


def _related_ads(db: Session, product_id: int, workspace_id: int) -> list[models.Ad]:
    return (
        db.query(models.Ad)
        .join(models.AdLandingEdge, models.AdLandingEdge.ad_id == models.Ad.id)
        .join(
            models.LandingProductEdge,
            models.LandingProductEdge.landing_url_id == models.AdLandingEdge.url_id,
        )
        .filter(models.Ad.workspace_id == workspace_id, models.LandingProductEdge.product_id == product_id)
        .distinct()
        .all()
    )


def _is_homepage_featured(db: Session, product_id: int, workspace_id: int) -> tuple[bool, datetime | None]:
    row = (
        db.query(models.LandingPageSnapshot)
        .join(
            models.LandingProductEdge,
            models.LandingProductEdge.landing_url_id == models.LandingPageSnapshot.url_id,
        )
        .join(models.SourceUrl, models.SourceUrl.id == models.LandingPageSnapshot.url_id)
        .filter(
            models.LandingProductEdge.product_id == product_id,
            models.SourceUrl.workspace_id == workspace_id,
            models.SourceUrl.type == models.SourceUrlType.store,
        )
        .order_by(models.LandingPageSnapshot.fetched_at.desc())
        .first()
    )
    return (row is not None, row.fetched_at if row else None)


def _product_momentum_evidence(
    db: Session,
    *,
    store: models.Store,
    product: models.Product,
    snapshots: list[models.ProductSnapshot],
    related_ads: list[models.Ad],
) -> tuple[list[Evidence], list[str]]:
    evidence: list[Evidence] = []
    reasons: list[str] = []
    featured, featured_at = _is_homepage_featured(db, product.id, store.workspace_id)
    if featured:
        evidence.append(
            Evidence(
                evidence_type="homepage_product_placement",
                value=Decimal("0.65"),
                source="store_homepage",
                independence_group="merchandising",
                observed_at=featured_at,
                reliability=Decimal("0.70"),
                unit="normalized_strength",
                details="Product URL was linked from the collected homepage.",
            )
        )
        reasons.append("Linked from the collected homepage")
    if related_ads:
        strength = Decimal(str(min(1.0, math.log1p(len(related_ads)) / math.log(6))))
        observed_at = max((ad.last_seen_at for ad in related_ads), default=None)
        providers = sorted({ad.data_provider for ad in related_ads})
        evidence_source = providers[0] if len(providers) == 1 else "mixed_ad_sources"
        evidence.append(
            Evidence(
                evidence_type="related_imported_ads",
                value=strength,
                source=evidence_source,
                independence_group="advertising",
                observed_at=observed_at,
                reliability=Decimal("0.62"),
                unit="normalized_strength",
                details=(
                    f"related_collected_ads={len(related_ads)}; providers={','.join(providers)}; "
                    "current_activity_not_verified"
                ),
            )
        )
        reasons.append(f"{len(related_ads)} collected ad record(s) link through an associated landing page")
    ordered_snapshots = sorted(snapshots, key=lambda snapshot: snapshot.fetched_at)
    observations_by_day: dict[date, models.ProductSnapshot] = {}
    for snapshot in ordered_snapshots:
        observations_by_day[snapshot.fetched_at.date()] = snapshot
    observation_snapshots = list(observations_by_day.values())
    if len(observation_snapshots) >= 3:
        first, latest = observation_snapshots[0], observation_snapshots[-1]
        span = max(0, (latest.fetched_at - first.fetched_at).days)
        if span >= 30:
            evidence.append(
                Evidence(
                    evidence_type="product_persistence",
                    value=Decimal(str(min(1.0, span / 180))),
                    source="store_catalog",
                    independence_group="persistence",
                    observed_at=latest.fetched_at,
                    reliability=Decimal("0.50"),
                    unit="normalized_strength",
                    details=(
                        f"distinct_observation_days={len(observation_snapshots)}; "
                        f"distinct_content_hashes={len({item.content_hash for item in observation_snapshots})}; "
                        f"span_days={span}"
                    ),
                )
            )
            reasons.append(f"Persisted across {span} days of distinct observations")
        if store.platform_guess == models.PlatformGuess.shopify:
            values = [snapshot.available for snapshot in observation_snapshots if snapshot.available is not None]
            if any(previous is False and current is True for previous, current in zip(values, values[1:])):
                evidence.append(
                    Evidence(
                        evidence_type="observed_restock",
                        value=Decimal("0.55"),
                        source="shopify_product_page",
                        independence_group="inventory",
                        observed_at=latest.fetched_at,
                        reliability=Decimal("0.55"),
                        unit="normalized_strength",
                        details="An unavailable-to-available transition was observed.",
                    )
                )
                reasons.append("A public restock transition was observed")
    return evidence, reasons


def _matched_store_ads(
    db: Session,
    store: models.Store,
) -> tuple[list[models.Ad], str | None, float]:
    ads = db.query(models.Ad).filter(models.Ad.workspace_id == store.workspace_id).all()
    domain = store.domain.removeprefix("www.")
    landing_matches = [
        ad
        for ad in ads
        if ad.landing_url
        and (urlparse(ad.landing_url).hostname or "").lower().removeprefix("www.") == domain
    ]
    confirmed = (
        db.query(models.StoreIdentity)
        .filter(
            models.StoreIdentity.store_id == store.id,
            models.StoreIdentity.is_confirmed.is_(True),
            models.StoreIdentity.identity_type.in_(["meta_page", "meta_advertiser"]),
        )
        .all()
    )
    identity_values = {item.normalized_value for item in confirmed}
    identity_matches = []
    for ad in ads:
        if ad.data_provider != "meta_ad_library":
            continue
        candidates = {
            re.sub(r"[^a-z0-9]+", "", (ad.advertiser_id or "").lower()),
            re.sub(r"[^a-z0-9]+", "", (ad.advertiser_name or "").lower()),
        }
        if identity_values & candidates:
            identity_matches.append(ad)
    combined = {ad.id: ad for ad in (*landing_matches, *identity_matches)}
    if identity_matches:
        return list(combined.values()), "confirmed Meta advertiser identity", 0.82
    if landing_matches:
        return list(combined.values()), "matching landing-page domain", 0.68
    return [], None, 0.0


def _advertising_report(
    db: Session,
    store: models.Store,
    calculated_at: datetime,
) -> tuple[InsightResult, dict[str, Any]]:
    ads, match, match_confidence = _matched_store_ads(db, store)
    if not ads:
        result = unsupported_result(
            "advertising_status",
            missing=("confirmed_meta_advertiser_identity", "successful_store_scoped_ad_search"),
            explanation=(
                "Advertising status is unknown because no collected ad can be responsibly matched to this store. "
                "No match is not treated as proof of inactivity."
            ),
            version="advertising-status-v1",
        )
        return (
            result,
            {
                "status": "unknown",
                "active_count": None,
                "historical_count": None,
                "distinct_creatives": None,
                "earliest_delivery_start": None,
                "longest_running_days": None,
                "matched_identity": None,
                "match_confidence": "insufficient_data",
                "explanation": result.explanation,
                "missing_signals": list(result.missing_signals),
            },
        )
    definitely_historical = [
        ad for ad in ads if ad.delivery_stop_time is not None and ad.delivery_stop_time < calculated_at
    ]
    starts = [ad.delivery_start_time for ad in ads if ad.delivery_start_time]
    longest = max(
        (
            (ad.delivery_stop_time - ad.delivery_start_time).days
            for ad in ads
            if ad.delivery_start_time and ad.delivery_stop_time
        ),
        default=None,
    )
    creative_keys = {
        json.dumps(ad.creative_urls_json or [], sort_keys=True)
        + "|"
        + (ad.headline or "")
        + "|"
        + (ad.ad_text or "")
        for ad in ads
    }
    providers = sorted({ad.data_provider for ad in ads})
    evidence_source = providers[0] if len(providers) == 1 else "mixed_ad_sources"
    evidence = Evidence(
        evidence_type="matched_ad_records",
        value=len(ads),
        source=evidence_source,
        independence_group="advertising_activity",
        observed_at=max((ad.last_seen_at for ad in ads), default=None),
        reliability=Decimal(str(match_confidence)),
        unit="ads",
        details=(
            f"match_method={match}; matched_records={len(ads)}; providers={','.join(providers)}; "
            "current_activity_requires_recent_scoped_search_coverage"
        ),
    )
    result = unsupported_result(
        "advertising_status",
        missing=(
            "recent_successful_store_scoped_active_ad_search",
            "ad_observation_status_history",
            "ad_performance",
            "spend",
            "impressions",
        ),
        explanation=(
            f"{len(ads)} collected ad record(s) match by {match}, but current advertising status is unknown. "
            "A missing delivery-stop date is not treated as proof that an ad is active."
        ),
        evidence=(evidence,),
        version="advertising-status-v1",
    )
    return (
        result,
        {
            "status": "matched_records_activity_unknown",
            "active_count": None,
            "historical_count": len(definitely_historical),
            "distinct_creatives": len(creative_keys),
            "earliest_delivery_start": min(starts) if starts else None,
            "longest_running_days": longest,
            "matched_identity": match,
            "match_confidence": _confidence_label(match_confidence),
            "data_sources": providers,
            "explanation": result.explanation,
            "missing_signals": list(result.missing_signals),
        },
    )


def _store_momentum(traffic: InsightResult) -> InsightResult:
    if traffic.status == "available" and traffic.classification in {"growing", "stable", "declining"}:
        result = InsightResult(
            metric="store_momentum",
            status="available",
            classification=traffic.classification.title(),
            confidence_score=traffic.confidence_score,
            confidence_label=traffic.confidence_label,
            evidence=traffic.evidence,
            assumptions=traffic.assumptions,
            missing_signals=tuple(dict.fromkeys((*traffic.missing_signals, "independent_demand_signal"))),
            explanation=(
                "Store momentum currently follows the multi-month provider traffic direction. "
                "Catalog and advertising changes are not counted as sales unless independently corroborated."
            ),
            estimator_version="store-momentum-v1",
        )
        return result
    return unsupported_result(
        "store_momentum",
        missing=("three_consecutive_months_of_traffic", "independent_demand_signal"),
        explanation="Store momentum needs at least three comparable traffic periods or another supported demand trend.",
        evidence=traffic.evidence,
        version="store-momentum-v1",
    )


@lru_cache(maxsize=256)
def _reanalyze_saved_homepage(
    snapshot_dir: str,
    homepage_url: str,
    html_hash: str,
) -> tuple[dict[str, Any], ...]:
    domain = (urlparse(homepage_url).hostname or "").lower()
    path = Path(snapshot_dir) / "html" / domain / f"{html_hash}.html"
    try:
        html = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ()
    analysis = analyze_store_homepage(homepage_url, html)
    return tuple(analysis.as_payload().get("technologies") or [])


def _saved_homepage_technologies(
    db: Session,
    profile: models.StoreProfile | None,
) -> list[dict[str, Any]]:
    if not profile or not profile.homepage_url:
        return []
    homepage = profile.homepage_url
    variants = {homepage, homepage.rstrip("/"), f"{homepage.rstrip('/')}/"}
    source_ids = [
        item[0]
        for item in db.query(models.SourceUrl.id)
        .filter(
            models.SourceUrl.workspace_id == profile.workspace_id,
            models.SourceUrl.url.in_(variants),
        )
        .all()
    ]
    if not source_ids:
        return []
    snapshot = (
        db.query(models.LandingPageSnapshot)
        .filter(models.LandingPageSnapshot.url_id.in_(source_ids))
        .order_by(desc(models.LandingPageSnapshot.fetched_at))
        .first()
    )
    if not snapshot or not snapshot.html_hash:
        return []
    return list(
        _reanalyze_saved_homepage(
            str(Path(settings.snapshot_dir).resolve()),
            homepage,
            snapshot.html_hash,
        )
    )


@lru_cache(maxsize=2048)
def _reanalyze_saved_product_page(
    snapshot_dir: str,
    page_url: str,
    content_hash: str,
) -> tuple[dict[str, Any], ...]:
    domain = (urlparse(page_url).hostname or "").lower()
    path = Path(snapshot_dir) / "html" / domain / f"{content_hash}.html"
    try:
        html = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ()
    return tuple(
        {
            **item.__dict__,
            "source": "product_page",
            "source_url": page_url,
        }
        for item in detect_storefront_technologies(page_url, html, source="product_page")
    )


def _saved_product_technologies(
    product_rows: list[tuple[models.Product, models.ProductSnapshot | None, list[models.ProductSnapshot]]],
    *,
    limit: int = 24,
) -> tuple[list[dict[str, Any]], int]:
    technologies: dict[str, dict[str, Any]] = {}
    pages_scanned = 0
    snapshot_dir = str(Path(settings.snapshot_dir).resolve())
    for product, latest, _ in product_rows[:limit]:
        if not latest or not latest.content_hash:
            continue
        pages_scanned += 1
        for item in _reanalyze_saved_product_page(
            snapshot_dir,
            product.canonical_url,
            latest.content_hash,
        ):
            enriched = {**item, "observed_at": latest.fetched_at}
            technologies.setdefault(str(item.get("key") or item.get("label")), enriched)
    return list(technologies.values()), pages_scanned


@lru_cache(maxsize=256)
def _reanalyze_saved_theme(
    snapshot_dir: str,
    homepage_url: str,
    html_hash: str,
) -> dict[str, Any] | None:
    domain = (urlparse(homepage_url).hostname or "").lower()
    path = Path(snapshot_dir) / "html" / domain / f"{html_hash}.html"
    try:
        html = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return analyze_store_homepage(homepage_url, html).theme


def _saved_homepage_theme(
    db: Session,
    profile: models.StoreProfile | None,
) -> dict[str, Any] | None:
    stored = (
        profile.attributes_json.get("theme")
        if profile and isinstance(profile.attributes_json, dict)
        else None
    )
    if stored:
        return stored
    if not profile or not profile.homepage_url:
        return None
    homepage = profile.homepage_url
    variants = {homepage, homepage.rstrip("/"), f"{homepage.rstrip('/')}/"}
    source_ids = [
        item[0]
        for item in db.query(models.SourceUrl.id)
        .filter(
            models.SourceUrl.workspace_id == profile.workspace_id,
            models.SourceUrl.url.in_(variants),
        )
        .all()
    ]
    snapshot = (
        db.query(models.LandingPageSnapshot)
        .filter(models.LandingPageSnapshot.url_id.in_(source_ids))
        .order_by(desc(models.LandingPageSnapshot.fetched_at))
        .first()
        if source_ids
        else None
    )
    if not snapshot or not snapshot.html_hash:
        return None
    return _reanalyze_saved_theme(
        str(Path(settings.snapshot_dir).resolve()),
        homepage,
        snapshot.html_hash,
    )


def _profile_sections(
    profile: models.StoreProfile | None,
    refreshed_technologies: list[dict[str, Any]] | None = None,
    *,
    pages_scanned: int = 1,
) -> tuple[dict[str, Any], dict[str, Any]]:
    attributes = profile.attributes_json if profile and profile.attributes_json else {}
    offers = attributes.get("offers") or []
    offer_payloads = []
    for item in offers:
        confidence = float(item.get("confidence") or 0)
        evidence = {
            "type": "homepage_offer_text",
            "label": "Homepage Offer Text",
            "value": item.get("evidence"),
            "source": "store_homepage",
            "observed_at": profile.last_observed_at if profile else None,
            "source_url": profile.homepage_url if profile else None,
            "reliability": confidence,
            "independence_group": "catalog_pricing_offer",
            "detail": item.get("text"),
        }
        offer_payloads.append(
            {
                "type": item.get("offer_type") or "unknown",
                "text": item.get("text") or "Offer text detected",
                "effective_discount": item.get("discount_percent"),
                "minimum_spend": item.get("minimum_spend"),
                "currency": item.get("currency"),
                "scope": "homepage",
                "persistence": "unknown",
                "confidence_label": _confidence_label(confidence),
                "evidence": [evidence],
            }
        )
    funnel_payloads = []
    for item in attributes.get("funnel_elements") or []:
        confidence = float(item.get("confidence") or 0)
        funnel_payloads.append(
            {
                "element": item.get("label") or item.get("key") or "Detected element",
                "page_type": "homepage",
                "confidence_label": _confidence_label(confidence),
                "evidence": [
                    {
                        "type": item.get("key") or "funnel_element",
                        "label": item.get("label") or "Funnel Element",
                        "value": True,
                        "source": item.get("source") or "store_homepage",
                        "observed_at": item.get("observed_at") or (profile.last_observed_at if profile else None),
                        "source_url": item.get("source_url") or (profile.homepage_url if profile else None),
                        "reliability": confidence,
                        "independence_group": "landing_page_conversion",
                        "detail": f"Public pattern: {item.get('evidence')}",
                    }
                ],
            }
        )
    offers_report = {
        "status": "available" if offer_payloads or funnel_payloads else "insufficient_data",
        "primary_offer": offer_payloads[0] if offer_payloads else None,
        "offers": offer_payloads,
        "funnel_elements": funnel_payloads,
        "strengths": [f"Detected {item['element']}" for item in funnel_payloads[:4]],
        "weaknesses": [],
        "missing_signals": (
            ["product_page_analysis", "cart_analysis", "offer_persistence_history"]
            if profile
            else ["homepage_scan", "product_page_analysis", "cart_analysis"]
        ),
    }
    why = {
        "commerce_platform": "Defines the storefront and collection paths Northstar can inspect.",
        "reviews": "Review tooling may provide product-level social-proof signals in later scans.",
        "reviews_loyalty": "Reviews and loyalty can support retention and product validation research.",
        "email": "Email capture and lifecycle marketing can support repeat purchases.",
        "email_sms": "Email and SMS tools indicate lifecycle and retention infrastructure.",
        "sms": "SMS tooling indicates direct-response retention infrastructure.",
        "subscriptions": "Subscriptions can increase repeat-purchase potential and AOV.",
        "customer_service": "Support tooling can indicate operational maturity.",
        "analytics": "Analytics tooling indicates measurement capability, not traffic volume.",
        "advertising_measurement": "Pixels indicate measurement intent, not active or successful advertising.",
        "behavior_analytics": "Session analytics can support conversion optimization.",
        "buy_now_pay_later": "Installment payments may reduce price friction for higher-ticket products.",
        "bundles_upsells": "Bundle tooling can shape offer structure, basket size, and merchandising strategy.",
        "page_builder": "Page-building software can indicate customized landing and merchandising experiences.",
        "sizing": "Sizing guidance can reduce fit uncertainty and return risk for relevant products.",
        "sales_channel": "Sales-channel tooling connects storefront activity with an external commerce or advertising surface.",
        "seo": "SEO tooling can automate storefront metadata and search-discovery work.",
        "localization": "Geolocation tooling can adapt market, language, currency, or regional experiences.",
        "conversion_optimization": "Conversion tooling can shape urgency, merchandising, or purchase flow behavior.",
        "unclassified_integration": "A third-party storefront resource was observed, but its commercial product identity is not yet resolved.",
        "shopify_app": "A public Shopify theme extension reveals an installed storefront capability.",
    }
    technology_items = list(attributes.get("technologies") or [])
    technology_by_key = {
        item.get("key") or item.get("label"): item
        for item in technology_items
        if isinstance(item, dict)
    }
    for item in refreshed_technologies or []:
        if isinstance(item, dict):
            technology_by_key[item.get("key") or item.get("label")] = item
    technologies = []
    for item in technology_by_key.values():
        confidence = float(item.get("confidence") or 0)
        category = item.get("category") or "other"
        technology_key = str(item.get("key") or "")
        evidence_value = str(item.get("evidence") or "")
        evidence_host = (urlparse(evidence_value).hostname or "").lower()
        icon_domain = TECHNOLOGY_ICON_DOMAINS.get(technology_key) or evidence_host or None
        technologies.append(
            {
                "name": item.get("label") or item.get("key") or "Unknown technology",
                "category": category,
                "icon_url": (
                    f"https://icons.duckduckgo.com/ip3/{icon_domain}.ico"
                    if icon_domain
                    else None
                ),
                "why_it_matters": why.get(category, "Public technology detection provides operational context."),
                "confidence_label": _confidence_label(confidence),
                "evidence": [
                    {
                        "type": "technology_pattern",
                        "label": "Public Technology Pattern",
                        "value": item.get("evidence"),
                        "source": "store_homepage",
                        "observed_at": profile.last_observed_at if profile else None,
                        "source_url": profile.homepage_url if profile else None,
                        "reliability": confidence,
                        "independence_group": "store_technology",
                        "detail": None,
                    }
                ],
            }
        )
    technology_report = {
        "status": "available" if technologies else "insufficient_data",
        "detections": technologies,
        "missing_signals": [] if technologies else ["homepage_technology_scan"],
        "pages_scanned": pages_scanned,
        "coverage_notice": (
            f"Aggregated public technology evidence across {pages_scanned} saved storefront page(s). "
            "Server-side, authenticated, disabled, or fully obfuscated apps may remain unavailable."
        ),
    }
    return offers_report, technology_report


def _input_fingerprint(
    db: Session,
    store: models.Store,
    profile: models.EstimationProfile,
    store_profile: models.StoreProfile | None,
    product_rows: list[tuple[models.Product, models.ProductSnapshot | None, list[models.ProductSnapshot]]],
    traffic_rows: list[models.TrafficObservation],
    ads: list[models.Ad],
    calculated_at: datetime,
) -> str:
    identities = (
        db.query(models.StoreIdentity)
        .filter(models.StoreIdentity.store_id == store.id)
        .order_by(models.StoreIdentity.id.asc())
        .all()
    )
    product_ids = [product.id for product, _, _ in product_rows]
    landing_edges = (
        db.query(models.LandingProductEdge)
        .filter(models.LandingProductEdge.product_id.in_(product_ids))
        .order_by(models.LandingProductEdge.id.asc())
        .all()
        if product_ids
        else []
    )
    landing_url_ids = [edge.landing_url_id for edge in landing_edges]
    ad_edges = (
        db.query(models.AdLandingEdge)
        .filter(models.AdLandingEdge.url_id.in_(landing_url_ids))
        .order_by(models.AdLandingEdge.id.asc())
        .all()
        if landing_url_ids
        else []
    )
    payload = {
        "store": [store.id, store.last_seen_at.isoformat()],
        "store_profile": (
            [
                store_profile.id,
                store_profile.profile_version,
                store_profile.last_observed_at.isoformat(),
                store_profile.attributes_json,
            ]
            if store_profile
            else None
        ),
        "identities": [
            [
                item.id,
                item.identity_type,
                item.normalized_value,
                item.is_confirmed,
                str(item.confidence_score),
                item.last_seen_at.isoformat(),
            ]
            for item in identities
        ],
        "profile": profile_payload(profile),
        "products": [
            [
                product.id,
                product.last_seen_at.isoformat(),
                [
                    [snapshot.id, snapshot.content_hash, snapshot.fetched_at.isoformat()]
                    for snapshot in snapshots
                ],
            ]
            for product, _, snapshots in product_rows
        ],
        "traffic": [row.id for row in traffic_rows],
        "ads": [
            [
                ad.id,
                ad.last_seen_at.isoformat(),
                ad.delivery_start_time.isoformat() if ad.delivery_start_time else None,
                ad.delivery_stop_time.isoformat() if ad.delivery_stop_time else None,
            ]
            for ad in ads
        ],
        "landing_product_edges": [[edge.id, edge.landing_url_id, edge.product_id] for edge in landing_edges],
        "ad_landing_edges": [[edge.id, edge.ad_id, edge.url_id] for edge in ad_edges],
        "report_version": REPORT_VERSION,
        "estimator_versions": [
            TRAFFIC_ESTIMATOR_VERSION,
            AOV_ESTIMATOR_VERSION,
            ORDERS_ESTIMATOR_VERSION,
            REVENUE_ESTIMATOR_VERSION,
            PRODUCT_MOMENTUM_ESTIMATOR_VERSION,
        ],
        "freshness_as_of": calculated_at.date().isoformat(),
    }
    return sha256_text(json.dumps(_json_safe(payload), sort_keys=True))


def _persist_insight(
    db: Session,
    *,
    run: models.AnalysisRun,
    store: models.Store,
    result: InsightResult,
    subject_key: str,
    product_id: int | None = None,
) -> models.DerivedInsight:
    insight = (
        db.query(models.DerivedInsight)
        .filter(
            models.DerivedInsight.analysis_run_id == run.id,
            models.DerivedInsight.subject_key == subject_key,
            models.DerivedInsight.metric_key == result.metric,
        )
        .first()
    )
    if not insight:
        insight = models.DerivedInsight(
            analysis_run_id=run.id,
            store_id=store.id,
            product_id=product_id,
            subject_key=subject_key,
            metric_key=result.metric,
        )
        db.add(insight)
    insight.value_kind = (
        "insufficient_data"
        if result.status == "insufficient_data"
        else "range"
        if result.low is not None or result.high is not None
        else "score"
        if result.score is not None
        else "classification"
    )
    insight.estimate_low = result.low
    insight.estimate_central = result.central
    insight.estimate_high = result.high
    insight.value_text = result.classification
    insight.value_json = {"status": result.status, "score": _json_safe(result.score), "explanation": result.explanation}
    insight.unit = result.unit
    insight.currency = result.currency
    insight.confidence_score = result.confidence_score
    insight.confidence_label = result.confidence_label
    insight.estimator_version = result.estimator_version
    insight.assumptions_json = _json_safe(dict(result.assumptions))
    insight.missing_signals_json = list(result.missing_signals)
    insight.calculated_at = datetime.utcnow()
    db.flush()
    db.query(models.InsightEvidence).filter(models.InsightEvidence.insight_id == insight.id).delete()

    for evidence in result.evidence:
        traffic_observation = None
        if evidence.source == "similarweb" and evidence.details:
            period_match = re.search(r"period=(\d{4}-\d{2})", evidence.details)
            if period_match:
                period_start = datetime.strptime(period_match.group(1), "%Y-%m").date()
                traffic_observation = (
                    db.query(models.TrafficObservation)
                    .filter(
                        models.TrafficObservation.store_id == store.id,
                        models.TrafficObservation.provider == evidence.source,
                        models.TrafficObservation.period_start == period_start,
                        models.TrafficObservation.metric_key == (
                            "global_rank"
                            if evidence.evidence_type == "global_rank"
                            else "monthly_visits"
                        ),
                    )
                    .order_by(models.TrafficObservation.retrieved_at.desc())
                    .first()
                )
        product_record = db.get(models.Product, product_id) if product_id else None
        source_record = None
        if product_record:
            source_record = (
                db.query(models.SourceUrl)
                .filter(
                    models.SourceUrl.workspace_id == store.workspace_id,
                    models.SourceUrl.url == product_record.canonical_url,
                )
                .first()
            )
        key_payload = "|".join(
            (
                str(store.workspace_id),
                str(store.id),
                str(product_id or ""),
                evidence.evidence_type,
                evidence.source,
                evidence.independence_group,
                str(evidence.value),
                str(evidence.observed_at or ""),
                str(evidence.reliability),
                str(evidence.details or ""),
                str(evidence.unit or ""),
                str(traffic_observation.id if traffic_observation else ""),
                str(source_record.id if source_record else ""),
                result.estimator_version,
                EVIDENCE_COLLECTOR_VERSION,
            )
        )
        evidence_key = sha256_text(key_payload)
        record = (
            db.query(models.EvidenceRecord)
            .filter(
                models.EvidenceRecord.workspace_id == store.workspace_id,
                models.EvidenceRecord.evidence_key == evidence_key,
            )
            .first()
        )
        if not record:
            source_type = {
                "similarweb": "provider_estimate",
                "meta_ad_library": "official_provider_record",
                "northstar_manual": "manual_public_import",
                "mixed_ad_sources": "mixed_ad_records",
                "northstar_calculation": "derived_calculation",
                "store_catalog": "public_store_observation",
                "store_homepage": "public_store_observation",
                "shopify_product_page": "public_store_observation",
            }.get(evidence.source, "public_observation")
            record = models.EvidenceRecord(
                workspace_id=store.workspace_id,
                store_id=store.id,
                product_id=product_id,
                source_url_id=source_record.id if source_record else None,
                traffic_snapshot_id=(
                    traffic_observation.traffic_snapshot_id if traffic_observation else None
                ),
                traffic_observation_id=traffic_observation.id if traffic_observation else None,
                evidence_key=evidence_key,
                evidence_type=evidence.evidence_type,
                independence_group=evidence.independence_group,
                details=evidence.details,
                source_type=source_type,
                source_name=evidence.source,
                source_url=product_record.canonical_url if product_record else None,
                unit=evidence.unit,
                confidence_score=evidence.reliability,
                is_contradictory=False,
                collector_version=EVIDENCE_COLLECTOR_VERSION,
            )
            db.add(record)
            if isinstance(evidence.value, bool):
                record.value_text = str(evidence.value).lower()
            elif isinstance(evidence.value, (Decimal, int, float)):
                record.value_numeric = Decimal(str(evidence.value))
            else:
                record.value_text = str(evidence.value)
            if isinstance(evidence.observed_at, datetime):
                record.observed_at = (
                    evidence.observed_at.replace(tzinfo=None)
                    if evidence.observed_at.tzinfo
                    else evidence.observed_at
                )
            elif isinstance(evidence.observed_at, date):
                record.observed_at = datetime.combine(evidence.observed_at, datetime.min.time())
            record.retrieved_at = (
                traffic_observation.retrieved_at
                if traffic_observation
                else record.observed_at
                if record.observed_at
                else datetime.utcnow()
            )
            record.freshness_expires_at = None
            db.flush()
        db.add(models.InsightEvidence(insight_id=insight.id, evidence_id=record.id, role="supporting"))
    return insight


def build_store_report(
    db: Session,
    *,
    workspace_id: int,
    store_id: int,
    force_recompute: bool = False,
) -> dict[str, Any] | None:
    store = (
        db.query(models.Store)
        .filter(models.Store.workspace_id == workspace_id, models.Store.id == store_id)
        .first()
    )
    if not store:
        return None
    calculated_at = datetime.utcnow()
    store_profile = db.query(models.StoreProfile).filter(models.StoreProfile.store_id == store.id).first()
    estimation_profile = get_or_create_default_profile(
        db,
        workspace_id,
        store_profile.primary_category if store_profile and store_profile.primary_category else GENERAL_CATEGORY,
    )
    assumptions = assumptions_from_profile(estimation_profile)
    estimator_traffic_rows, traffic_periods, traffic_db_rows = _normalized_traffic(db, store)
    traffic_result = estimate_traffic(estimator_traffic_rows, as_of=calculated_at, assumptions=assumptions)
    selected_traffic_provider = next(
        (
            item.source
            for item in traffic_result.evidence
            if item.evidence_type == "monthly_visits"
        ),
        next((item.source for item in traffic_result.evidence if item.evidence_type == "global_rank"), None),
    )
    if selected_traffic_provider:
        traffic_periods = [
            period for period in traffic_periods if period["source"] == selected_traffic_provider
        ]
    product_rows = _latest_product_rows(db, store)
    merchandise = [
        MerchandiseObservation(
            title=_display_product_title(product, snapshots, store_profile),
            price=_representative_product_price(latest),
            currency=product.currency or (store_profile.currency if store_profile else None),
            product_id=product.id,
            product_kind=_product_kind_from_public_url(product),
            observed_at=latest.fetched_at if latest else product.last_seen_at,
        )
        for product, latest, snapshots in product_rows
    ]
    merchandise_classifications = [
        classify_sellable_merchandise(observation) for observation in merchandise
    ]
    # Keep every collected page and snapshot in storage, but do not let obvious
    # checkout add-ons or free gifts dominate the decision-focused product table.
    # Unknown classifications remain visible so a missing price cannot silently
    # remove a potentially real product.
    intelligence_product_rows = [
        row
        for row, classification in zip(product_rows, merchandise_classifications)
        if classification.is_sellable or classification.classification == "unknown"
    ]
    auxiliary_product_count = len(product_rows) - len(intelligence_product_rows)
    aov_result = estimate_aov(merchandise, assumptions=assumptions)
    currency_fallback_count = sum(
        product.currency is None and store_profile is not None and bool(store_profile.currency)
        for product, _, _ in product_rows
    )
    if aov_result.status == "available" and currency_fallback_count and store_profile:
        currency_evidence = Evidence(
            evidence_type="storefront_currency_fallback",
            value=store_profile.currency or "unknown",
            source="store_homepage",
            independence_group="catalog_pricing_offer",
            observed_at=store_profile.last_observed_at,
            reliability=Decimal("0.75"),
            unit="currency_code",
            details=(
                f"Applied the homepage/storefront currency to {currency_fallback_count} "
                "product record(s) whose parser did not return a product-level currency."
            ),
        )
        fallback_confidence = min(aov_result.confidence_score, Decimal("0.33"))
        aov_result = replace(
            aov_result,
            confidence_score=fallback_confidence,
            confidence_label=_confidence_label(fallback_confidence),
            evidence=(*aov_result.evidence, currency_evidence),
            assumptions={
                **aov_result.assumptions,
                "storefront_currency_fallback_products": currency_fallback_count,
            },
            missing_signals=tuple(
                dict.fromkeys(
                    (*aov_result.missing_signals, "product_level_currency_for_all_products")
                )
            ),
            explanation=(
                aov_result.explanation
                + " The public storefront currency was used for products missing a product-level currency, so confidence was reduced."
            ),
        )
    orders_result = estimate_orders(traffic_result, assumptions=assumptions)
    revenue_result = estimate_gross_revenue(orders_result, aov_result)
    advertising_result, ads_report = _advertising_report(db, store, calculated_at)
    advertising_insight = insight_payload(advertising_result, calculated_at)
    matched_ads, _, _ = _matched_store_ads(db, store)
    fingerprint = _input_fingerprint(
        db,
        store,
        estimation_profile,
        store_profile,
        product_rows,
        traffic_db_rows,
        matched_ads,
        calculated_at,
    )
    # Analysis runs are immutable snapshots. Reopening a report creates a new
    # run instead of rewriting a completed historical calculation as evidence
    # freshness changes over time.
    run = models.AnalysisRun(
        workspace_id=workspace_id,
        store_id=store.id,
        estimation_profile_id=estimation_profile.id,
        status="running",
        analysis_version=REPORT_VERSION,
        input_fingerprint=fingerprint,
        started_at=calculated_at,
    )
    db.add(run)
    db.flush()

    product_reports: list[tuple[dict[str, Any], InsightResult, int]] = []
    for product, latest, snapshots in intelligence_product_rows:
        related_ads = _related_ads(db, product.id, workspace_id)
        evidence, reasons = _product_momentum_evidence(
            db,
            store=store,
            product=product,
            snapshots=snapshots,
            related_ads=related_ads,
        )
        momentum = estimate_product_momentum(
            evidence,
            first_observed_at=min((snapshot.fetched_at for snapshot in snapshots), default=product.created_at),
            latest_observed_at=max((snapshot.fetched_at for snapshot in snapshots), default=product.last_seen_at),
            as_of=calculated_at,
            assumptions=assumptions,
        )
        if related_ads:
            ads_evidence = tuple(item for item in evidence if item.independence_group == "advertising")
            related_result = unsupported_result(
                "active_related_ads",
                missing=("recent_product_scoped_active_ad_search", "ad_status_observations"),
                explanation=(
                    f"{len(related_ads)} imported ad record(s) are associated through collected landing-page links, "
                    "but their current active status is not verified."
                ),
                evidence=ads_evidence,
                version="ad-product-association-v1",
            )
            active_ads_payload = insight_payload(related_result, calculated_at)
        else:
            related_result = unsupported_result(
                "active_related_ads",
                missing=("confirmed_ad_product_association", "successful_ad_search_coverage"),
                explanation="No responsible ad count is available for this product; an empty local result is not proof of zero ads.",
                version="ad-product-association-v1",
            )
            active_ads_payload = insight_payload(related_result, calculated_at)
        review_result = unsupported_result(
            "review_signal",
            missing=("review_count", "review_velocity"),
            explanation="Review count and growth have not been collected for this product.",
        )
        sales_contribution_result = unsupported_result(
            "estimated_sales_contribution",
            missing=("store_order_range", "product_level_demand_share"),
            explanation="Sales contribution is withheld without a store order range and product-level demand share evidence.",
            evidence=momentum.evidence,
        )
        saturation_result = unsupported_result(
            "product_saturation",
            missing=("product_cluster", "competitor_corpus", "advertising_coverage"),
            explanation="No product-similarity corpus exists yet, so zero matches cannot be interpreted as low saturation.",
        )
        supplier_result = unsupported_result(
            "supplier_match",
            missing=("supplier_search", "image_or_model_match"),
            explanation="No supplier search has produced a plausible public listing match.",
        )
        margin_result = unsupported_result(
            "estimated_gross_margin",
            missing=("supplier_cost_range",),
            explanation="Margin is withheld until a plausible supplier cost range exists.",
        )
        image = product_image_url(product.canonical_url, latest)
        uncertainties = list(momentum.missing_signals)
        row = {
            "rank": 0,
            "id": product.id,
            "title": _display_product_title(product, snapshots, store_profile),
            "url": product.canonical_url,
            "image_url": image,
            "current_price": float(latest.price_min) if latest and latest.price_min is not None else None,
            "currency": product.currency or (store_profile.currency if store_profile else None),
            "first_seen_at": product.created_at,
            "momentum": insight_payload(momentum, calculated_at),
            "active_related_ads": active_ads_payload,
            "review_signal": insight_payload(review_result, calculated_at),
            "sales_contribution": insight_payload(sales_contribution_result, calculated_at),
            "saturation": insight_payload(saturation_result, calculated_at),
            "supplier_match": insight_payload(supplier_result, calculated_at),
            "estimated_margin": insight_payload(margin_result, calculated_at),
            "reasons": reasons,
            "uncertainties": uncertainties,
            "confidence": momentum.confidence_label,
        }
        sort_score = float(momentum.score or 0)
        product_reports.append((row, momentum, int(sort_score * 1000)))
        for product_result in (
            momentum,
            related_result,
            review_result,
            sales_contribution_result,
            saturation_result,
            supplier_result,
            margin_result,
        ):
            _persist_insight(
                db,
                run=run,
                store=store,
                result=product_result,
                subject_key=f"product:{product.id}",
                product_id=product.id,
            )

    product_reports.sort(key=lambda item: (item[1].status == "available", item[2]), reverse=True)
    for rank, (row, _, _) in enumerate(product_reports, start=1):
        row["rank"] = rank

    store_momentum_result = _store_momentum(traffic_result)
    store_momentum_payload = insight_payload(store_momentum_result, calculated_at)
    dropshipping_result = unsupported_result(
        "dropshipping_likelihood",
        missing=(
            "supplier_image_matches",
            "shipping_origin_and_window",
            "original_brand_counter_signals",
            "cross_store_product_clusters",
        ),
        explanation="Dropshipping likelihood remains unknown until both supporting signals and counter-signals are collected.",
        version="dropshipping-likelihood-v1",
    )
    dropshipping_payload = insight_payload(dropshipping_result, calculated_at)
    primary_results = (
        traffic_result,
        aov_result,
        orders_result,
        revenue_result,
        store_momentum_result,
        advertising_result,
        dropshipping_result,
    )
    for result in primary_results:
        _persist_insight(db, run=run, store=store, result=result, subject_key=f"store:{store.id}")
    traffic_available = traffic_result.status == "available"
    any_product_momentum = any(result.status == "available" for _, result, _ in product_reports)
    advertising_available = advertising_result.status == "available"
    traffic_confident = traffic_available and traffic_result.confidence_score >= Decimal("0.50")
    product_confident = any(
        result.status == "available" and result.confidence_score >= Decimal("0.50")
        for _, result, _ in product_reports
    )
    if traffic_confident and product_confident:
        verdict = "Worth studying, with product-level validation still required"
    elif traffic_available and traffic_result.confidence_score >= Decimal("0.25"):
        verdict = "Traffic evidence exists, but product demand is not yet verified"
    elif advertising_available:
        verdict = "Advertising activity exists, but meaningful demand is still unverified"
    else:
        verdict = "Little evidence of meaningful demand"
    if traffic_available:
        strongest = (
            f"Similarweb estimated {float(traffic_result.central or 0):,.0f} monthly visits for the latest available period."
        )
    elif advertising_available:
        strongest = f"{ads_report['active_count']} matched ad record(s) appear active by provider delivery dates."
    elif intelligence_product_rows:
        strongest = (
            f"{len(intelligence_product_rows)} merchandise product page(s) were collected, but catalog presence alone is not sales evidence."
        )
    else:
        strongest = "No reliable demand signal has been collected yet."
    if not traffic_available:
        largest_uncertainty = "Monthly traffic is unavailable, so orders and gross revenue cannot be estimated."
        next_step = "Connect Similarweb and collect visits, then rescan over time and confirm the store's Meta identity."
    elif not any_product_momentum:
        largest_uncertainty = "Product-level demand evidence is too sparse to identify likely sellers."
        next_step = "Collect at least 14 days of product history and associate confirmed ads or review velocity with products."
    else:
        largest_uncertainty = "Public conversion and basket assumptions remain uncalibrated for this store."
        next_step = "Validate the top-ranked product with competitor, supplier-cost, review, and creative evidence."
    product_confidence = max(
        (float(result.confidence_score) for _, result, _ in product_reports),
        default=0.0,
    )
    overall_score = min(
        0.74,
        float(traffic_result.confidence_score) * 0.45
        + float(aov_result.confidence_score) * 0.25
        + product_confidence * 0.20
        + float(advertising_result.confidence_score) * 0.10,
    )
    overall_confidence = _confidence_label(overall_score, required=True)

    product_technologies, product_technology_pages = _saved_product_technologies(product_rows)
    homepage_technologies = _saved_homepage_technologies(db, store_profile)
    offers_report, technology_report = _profile_sections(
        store_profile,
        [*product_technologies, *homepage_technologies],
        pages_scanned=product_technology_pages + (1 if homepage_technologies else 0),
    )
    source_rows = db.query(models.SourceUrl).filter(models.SourceUrl.workspace_id == workspace_id).all()
    store_sources = [
        source
        for source in source_rows
        if (urlparse(source.url).hostname or "").lower().removeprefix("www.")
        == store.domain.lower().removeprefix("www.")
    ]
    jobs = [job for job in recent_jobs(50) if store.domain.lower() in str(job.get("label", "")).lower()]
    all_evidence = []
    seen_evidence = set()
    for result in primary_results:
        for item in result.evidence:
            key = (item.evidence_type, item.source, str(item.value), str(item.observed_at))
            if key not in seen_evidence:
                seen_evidence.add(key)
                all_evidence.append(_evidence_payload(item))
    all_missing = list(
        dict.fromkeys(
            signal
            for result in primary_results
            for signal in result.missing_signals
        )
    )
    profile_assumptions = {
        "conversion_rate": [
            float(estimation_profile.conversion_rate_low),
            float(estimation_profile.conversion_rate_central) if estimation_profile.conversion_rate_central is not None else None,
            float(estimation_profile.conversion_rate_high),
        ],
        "items_per_order": [
            float(estimation_profile.basket_multiplier_low),
            float(estimation_profile.basket_multiplier_central) if estimation_profile.basket_multiplier_central is not None else None,
            float(estimation_profile.basket_multiplier_high),
        ],
        "traffic_reliability_envelope": [
            float(estimation_profile.traffic_reliability_low),
            float(estimation_profile.traffic_reliability_high),
        ],
        "freshness_days": estimation_profile.freshness_limit_days,
        "minimum_evidence_groups": estimation_profile.minimum_evidence_count,
        "score_weights": estimation_profile.score_weights_json or {},
        "thresholds": estimation_profile.thresholds_json or {},
    }
    run.status = "completed"
    run.completed_at = datetime.utcnow()
    run.warnings_json = all_missing
    run.errors_json = []
    db.commit()

    return {
        "report_version": REPORT_VERSION,
        "generated_at": calculated_at,
        "store": {
            "id": store.id,
            "domain": store.domain,
            "brand_name": store_profile.brand_name if store_profile else None,
            "platform": _enum_value(store.platform_guess),
            "category": store_profile.primary_category if store_profile else None,
            "market": store_profile.primary_country if store_profile else None,
            "logo_url": store_profile.logo_url if store_profile else None,
            "first_seen_at": store.first_seen_at,
            "last_seen_at": store.last_seen_at,
            "product_count": len(intelligence_product_rows),
            "theme": _saved_homepage_theme(db, store_profile),
        },
        "executive_summary": {
            "verdict": verdict,
            "strongest_evidence": strongest,
            "largest_uncertainty": largest_uncertainty,
            "next_step": next_step,
            "overall_confidence": overall_confidence,
            "metrics": {
                "monthly_visits": insight_payload(traffic_result, calculated_at),
                "monthly_orders": insight_payload(orders_result, calculated_at),
                "monthly_revenue": insight_payload(revenue_result, calculated_at),
                "aov": insight_payload(aov_result, calculated_at),
                "store_momentum": store_momentum_payload,
                "advertising_status": advertising_insight,
                "dropshipping_likelihood": dropshipping_payload,
            },
        },
        "traffic": {
            "status": traffic_result.status,
            "provider": traffic_periods[-1]["source"] if traffic_periods else None,
            "periods": traffic_periods,
            "trend": store_momentum_payload,
            "unavailable_metrics": [
                "country_rank",
                "category_rank",
                "top_countries",
                "traffic_channels",
                "visit_duration",
                "pages_per_visit",
                "bounce_rate",
            ],
            "source_notice": TRAFFIC_DATA_NOTICE,
            "reporting_date": traffic_periods[-1]["observed_at"] if traffic_periods else None,
        },
        "products": [row for row, _, _ in product_reports],
        "ads": ads_report,
        "offers_and_funnel": offers_report,
        "technology": technology_report,
        "evidence_and_assumptions": {
            "profile_id": estimation_profile.id,
            "profile_name": estimation_profile.name,
            "category_key": estimation_profile.category_key,
            "assumptions": profile_assumptions,
            "evidence": all_evidence,
            "missing_signals": all_missing,
            "analysis_version": REPORT_VERSION,
        },
        "diagnostics": {
            "source_count": len(store_sources),
            "fetched_source_count": sum(source.fetch_status == "fetched" for source in store_sources),
            "failed_source_count": sum(source.fetch_status == "failed" for source in store_sources),
            "product_snapshot_count": sum(len(snapshots) for _, _, snapshots in product_rows),
            "store_snapshot_count": db.query(models.StoreSnapshot).filter(models.StoreSnapshot.store_id == store.id).count(),
            "auxiliary_product_count": auxiliary_product_count,
            "sources": [
                {
                    "id": source.id,
                    "url": source.url,
                    "type": _enum_value(source.type),
                    "status": source.fetch_status,
                    "http_status": source.last_http_status,
                    "fetched_at": source.last_fetched_at,
                }
                for source in sorted(store_sources, key=lambda item: item.created_at, reverse=True)
            ],
            "recent_jobs": [
                {
                    "id": job["id"],
                    "label": job["label"],
                    "status": job["status"],
                    "created_at": job["created_at"],
                    "error": job.get("error"),
                }
                for job in jobs
            ],
        },
    }
