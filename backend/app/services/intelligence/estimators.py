"""Transparent, deterministic intelligence estimators.

These functions do not read the database or call external providers. Callers
must pass normalized observations, which makes every calculation repeatable
and straightforward to test and version.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP
from statistics import median
import re
from typing import Iterable, Sequence

from .assumptions import DEFAULT_ASSUMPTIONS, EstimatorAssumptions
from .types import ConfidenceLabel, Evidence, InsightResult


TRAFFIC_ESTIMATOR_VERSION = "traffic-trend-v1"
AOV_ESTIMATOR_VERSION = "aov-v1"
ORDERS_ESTIMATOR_VERSION = "orders-v1"
REVENUE_ESTIMATOR_VERSION = "revenue-v1"
PRODUCT_MOMENTUM_ESTIMATOR_VERSION = "product-momentum-v1"


@dataclass(frozen=True)
class TrafficObservation:
    period: str | date
    visits: Decimal | int | float | str | None
    retrieved_at: date | datetime | None
    provider: str = "similarweb"
    fetch_status: str = "success"
    global_rank: int | None = None


@dataclass(frozen=True)
class MerchandiseObservation:
    title: str
    price: Decimal | int | float | str | None
    currency: str | None
    product_id: int | str | None = None
    product_kind: str | None = None
    observed_at: date | datetime | None = None


@dataclass(frozen=True)
class MerchandiseClassification:
    is_sellable: bool
    classification: str
    reasons: tuple[str, ...]


_EXCLUDED_KINDS = {
    "add_on",
    "donation",
    "free_gift",
    "gift_card",
    "service",
    "shipping_protection",
    "tip",
    "warranty",
}
_TITLE_EXCLUSIONS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("free_gift", re.compile(r"\bfree\s+gift\b|\(free\s+gift\)", re.IGNORECASE)),
    (
        "shipping_protection",
        re.compile(r"\b(shipping|package|order|delivery)\s+(protection|insurance)\b", re.IGNORECASE),
    ),
    ("warranty", re.compile(r"\b(extended\s+)?warranty\b", re.IGNORECASE)),
    ("donation", re.compile(r"\b(donation|tip)\b", re.IGNORECASE)),
    ("gift_card", re.compile(r"\bgift\s+card\b", re.IGNORECASE)),
)


def _decimal(value: Decimal | int | float | str | None) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() else None


def _as_date(value: date | datetime | None) -> date | None:
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value.date()
    return value


def _today(value: date | datetime | None) -> date:
    return _as_date(value) or datetime.now(timezone.utc).date()


def _period_key(value: str | date) -> tuple[int, int] | None:
    if isinstance(value, date):
        return value.year, value.month
    try:
        parsed = datetime.strptime(value, "%Y-%m")
    except (TypeError, ValueError):
        return None
    return parsed.year, parsed.month


def _period_text(key: tuple[int, int]) -> str:
    return f"{key[0]:04d}-{key[1]:02d}"


def _month_distance(earlier: tuple[int, int], later: tuple[int, int]) -> int:
    return (later[0] - earlier[0]) * 12 + later[1] - earlier[1]


def _confidence_label(score: Decimal) -> ConfidenceLabel:
    if score >= Decimal("0.75"):
        return "high"
    if score >= Decimal("0.50"):
        return "medium"
    if score >= Decimal("0.25"):
        return "low"
    return "insufficient_data"


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _ratio_text(value: Decimal) -> str:
    return f"{(value * 100).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)}%"


def _traffic_assumptions(config: EstimatorAssumptions) -> dict[str, Decimal | int | str]:
    return {
        "traffic_envelope_low_multiplier": config.traffic_envelope_low,
        "traffic_envelope_high_multiplier": config.traffic_envelope_high,
        "freshness_days": config.freshness_days,
        "direction_minimum_months": 3,
        "direction_monthly_threshold": config.traffic_monthly_direction_threshold,
        "direction_endpoint_threshold": config.traffic_endpoint_direction_threshold,
        "range_kind": "northstar_planning_envelope_not_provider_confidence_interval",
    }


def estimate_traffic(
    observations: Sequence[TrafficObservation],
    *,
    as_of: date | datetime | None = None,
    assumptions: EstimatorAssumptions = DEFAULT_ASSUMPTIONS,
) -> InsightResult:
    """Estimate a monthly traffic envelope and classify a 3+ month trend.

    Global rank is retained as context evidence only. It is never converted to
    visits and cannot make an otherwise unavailable result available.
    """

    today = _today(as_of)
    config = _traffic_assumptions(assumptions)
    normalized: dict[tuple[str, tuple[int, int]], tuple[TrafficObservation, Decimal]] = {}
    rank_evidence: list[Evidence] = []

    for observation in observations:
        key = _period_key(observation.period)
        if key is None:
            continue
        provider = observation.provider.strip().lower() or "unknown"
        if observation.global_rank is not None and observation.global_rank >= 0:
            rank_evidence.append(
                Evidence(
                    evidence_type="global_rank",
                    value=observation.global_rank,
                    source=provider,
                    independence_group=f"{provider}_traffic",
                    observed_at=observation.retrieved_at,
                    reliability=Decimal("0.60"),
                    unit="rank",
                    details=f"period={_period_text(key)}; not converted to visits",
                )
            )
        visits = _decimal(observation.visits)
        status = observation.fetch_status.strip().lower()
        if visits is None or visits < 0 or status in {"unavailable", "failed", "error", "no_data"}:
            continue
        compound_key = (provider, key)
        previous = normalized.get(compound_key)
        previous_date = _as_date(previous[0].retrieved_at) if previous else None
        candidate_date = _as_date(observation.retrieved_at)
        if previous is None or (candidate_date or date.min) >= (previous_date or date.min):
            normalized[compound_key] = (observation, visits)

    if not normalized:
        return InsightResult(
            metric="estimated_monthly_visits",
            status="insufficient_data",
            confidence_score=Decimal("0.05") if rank_evidence else Decimal("0"),
            confidence_label="insufficient_data",
            evidence=tuple(rank_evidence),
            assumptions=config,
            missing_signals=("estimated_monthly_visits",),
            explanation=(
                "No provider visit estimate is available. Global rank is not converted into visits."
                if rank_evidence
                else "No provider visit estimate is available."
            ),
            estimator_version=TRAFFIC_ESTIMATOR_VERSION,
        )

    # Use one provider series. Mixing providers would create a false trend.
    latest_provider, _ = max(normalized, key=lambda item: item[1])
    provider_rows = [
        (key, observation, visits)
        for (provider, key), (observation, visits) in normalized.items()
        if provider == latest_provider
    ]
    provider_rows.sort(key=lambda row: row[0])
    latest_key, latest_observation, latest_visits = provider_rows[-1]

    trailing = [provider_rows[-1]]
    for row in reversed(provider_rows[:-1]):
        if _month_distance(row[0], trailing[0][0]) != 1:
            break
        trailing.insert(0, row)
    trailing = trailing[-6:]

    evidence: list[Evidence] = []
    for key, observation, visits in provider_rows:
        reliability = Decimal("0.50") if observation.fetch_status.lower() == "partial" else Decimal("0.65")
        evidence.append(
            Evidence(
                evidence_type="monthly_visits",
                value=visits,
                source=latest_provider,
                independence_group=f"{latest_provider}_traffic",
                observed_at=observation.retrieved_at,
                reliability=reliability,
                unit="visits_per_month",
                details=f"period={_period_text(key)}",
            )
        )

    mom: Decimal | None = None
    if len(trailing) >= 2 and trailing[-2][2] > 0:
        mom = trailing[-1][2] / trailing[-2][2] - Decimal("1")
        evidence.append(
            Evidence(
                evidence_type="month_over_month_change",
                value=mom,
                source="northstar_calculation",
                independence_group=f"{latest_provider}_traffic",
                observed_at=latest_observation.retrieved_at,
                reliability=Decimal("0.60"),
                unit="ratio",
                details=f"{_period_text(trailing[-2][0])} to {_period_text(latest_key)}",
            )
        )

    classification = "insufficient_history"
    direction_rate: Decimal | None = None
    endpoint_change: Decimal | None = None
    if len(trailing) >= 3:
        changes = [
            current[2] / previous[2] - Decimal("1")
            for previous, current in zip(trailing, trailing[1:])
            if previous[2] > 0
        ]
        if len(changes) >= 2 and trailing[0][2] > 0:
            direction_rate = Decimal(str(median(changes)))
            endpoint_change = trailing[-1][2] / trailing[0][2] - Decimal("1")
            if (
                direction_rate > assumptions.traffic_monthly_direction_threshold
                and endpoint_change > assumptions.traffic_endpoint_direction_threshold
            ):
                classification = "growing"
            elif (
                direction_rate < -assumptions.traffic_monthly_direction_threshold
                and endpoint_change < -assumptions.traffic_endpoint_direction_threshold
            ):
                classification = "declining"
            else:
                classification = "stable"
            evidence.append(
                Evidence(
                    evidence_type="median_monthly_traffic_change",
                    value=direction_rate,
                    source="northstar_calculation",
                    independence_group=f"{latest_provider}_traffic",
                    observed_at=latest_observation.retrieved_at,
                    reliability=Decimal("0.65"),
                    unit="ratio",
                    details=f"trailing_months={len(trailing)}; endpoint_change={endpoint_change}",
                )
            )

    retrieved = _as_date(latest_observation.retrieved_at)
    age_days = max(0, (today - retrieved).days) if retrieved else None
    stale = age_days is None or age_days > assumptions.freshness_days
    partial = latest_observation.fetch_status.strip().lower() == "partial"
    confidence = Decimal("0.50") if partial else Decimal("0.65")
    if len(trailing) >= 3:
        confidence += Decimal("0.05")
    if len(trailing) >= 6:
        confidence += Decimal("0.05")
    if stale:
        confidence *= Decimal("0.55")
    confidence = min(confidence, Decimal("0.75")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    missing: list[str] = []
    if classification == "insufficient_history":
        missing.append("three_consecutive_months_of_traffic")
    if partial:
        missing.append("complete_provider_traffic_response")
    if stale:
        missing.append("fresh_traffic_observation")

    low = latest_visits * assumptions.traffic_envelope_low
    high = latest_visits * assumptions.traffic_envelope_high
    trend_text = (
        f" MoM is {_ratio_text(mom)} and the 3+ month direction is {classification}."
        if mom is not None
        else " More history is needed for month-over-month direction."
    )
    stale_text = " The latest retrieval is stale or undated." if stale else ""
    return InsightResult(
        metric="estimated_monthly_visits",
        status="available",
        low=low,
        central=latest_visits,
        high=high,
        classification=classification,
        unit="visits_per_month",
        confidence_score=confidence,
        confidence_label=_confidence_label(confidence),
        evidence=tuple(evidence),
        assumptions=config,
        missing_signals=tuple(missing),
        explanation=(
            f"The provider estimate for {_period_text(latest_key)} is {latest_visits}. "
            "The low/high values are a disclosed Northstar planning envelope, not a provider confidence interval."
            f"{trend_text}{stale_text}"
        ),
        estimator_version=TRAFFIC_ESTIMATOR_VERSION,
    )


def classify_sellable_merchandise(observation: MerchandiseObservation) -> MerchandiseClassification:
    """Separate likely merchandise from zero-value gifts and checkout add-ons."""

    price = _decimal(observation.price)
    kind = (observation.product_kind or "").strip().lower()
    if kind in _EXCLUDED_KINDS:
        return MerchandiseClassification(False, kind, (f"explicit_product_kind:{kind}",))
    if price is None:
        return MerchandiseClassification(False, "unknown", ("missing_or_invalid_price",))
    if price <= 0:
        return MerchandiseClassification(False, "free_or_zero_price", ("non_positive_price",))
    for classification, pattern in _TITLE_EXCLUSIONS:
        if pattern.search(observation.title or ""):
            return MerchandiseClassification(False, classification, (f"title_pattern:{classification}",))
    if not (observation.currency or "").strip():
        return MerchandiseClassification(False, "unknown", ("missing_currency",))
    return MerchandiseClassification(True, "sellable_merchandise", ("positive_price", "no_add_on_pattern"))


def _percentile(values: Sequence[Decimal], quantile: Decimal) -> Decimal:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("At least one value is required")
    if len(ordered) == 1:
        return ordered[0]
    position = Decimal(len(ordered) - 1) * quantile
    lower_index = int(position.to_integral_value(rounding=ROUND_FLOOR))
    upper_index = int(position.to_integral_value(rounding=ROUND_CEILING))
    if lower_index == upper_index:
        return ordered[lower_index]
    fraction = position - Decimal(lower_index)
    return ordered[lower_index] + (ordered[upper_index] - ordered[lower_index]) * fraction


def _aov_assumptions(config: EstimatorAssumptions) -> dict[str, Decimal | int | str]:
    return {
        "items_per_order_low": config.items_per_order_low,
        "items_per_order_central": config.items_per_order_central,
        "items_per_order_high": config.items_per_order_high,
        "price_anchor_low": "eligible_catalog_p25",
        "price_anchor_central": "eligible_catalog_median",
        "price_anchor_high": "eligible_catalog_p75",
        "minimum_sellable_products": config.minimum_sellable_products,
        "exclude_non_merchandise": True,
    }


def estimate_aov(
    products: Sequence[MerchandiseObservation],
    *,
    assumptions: EstimatorAssumptions = DEFAULT_ASSUMPTIONS,
) -> InsightResult:
    """Estimate AOV from eligible catalog quantiles and disclosed basket priors."""

    config = _aov_assumptions(assumptions)
    eligible: list[tuple[MerchandiseObservation, Decimal]] = []
    excluded: list[MerchandiseClassification] = []
    for product in products:
        classification = classify_sellable_merchandise(product)
        price = _decimal(product.price)
        if classification.is_sellable and price is not None:
            eligible.append((product, price))
        else:
            excluded.append(classification)

    currencies = {(product.currency or "").strip().upper() for product, _ in eligible}
    evidence: list[Evidence] = []
    if eligible:
        evidence.append(
            Evidence(
                evidence_type="eligible_catalog_product_count",
                value=len(eligible),
                source="store_catalog",
                independence_group="catalog_pricing_offer",
                observed_at=max(
                    (_as_date(product.observed_at) for product, _ in eligible if product.observed_at),
                    default=None,
                ),
                reliability=Decimal("0.45"),
                unit="products",
                details=f"excluded_non_merchandise={len(excluded)}",
            )
        )

    missing: list[str] = []
    if len(eligible) < assumptions.minimum_sellable_products:
        missing.append(f"at_least_{assumptions.minimum_sellable_products}_sellable_products")
    if len(currencies) != 1:
        missing.append("single_catalog_currency")
    if missing:
        return InsightResult(
            metric="estimated_average_order_value",
            status="insufficient_data",
            confidence_score=Decimal("0.10") if eligible else Decimal("0"),
            confidence_label="insufficient_data",
            evidence=tuple(evidence),
            assumptions=config,
            missing_signals=tuple(missing + ["observed_basket_value"]),
            explanation=(
                "AOV is withheld because the catalog does not contain enough eligible merchandise in one currency. "
                "Free gifts, protection products, warranties, tips, donations, and zero-price items are excluded."
            ),
            estimator_version=AOV_ESTIMATOR_VERSION,
        )

    prices = [price for _, price in eligible]
    p25 = _percentile(prices, Decimal("0.25"))
    p50 = _percentile(prices, Decimal("0.50"))
    p75 = _percentile(prices, Decimal("0.75"))
    currency = next(iter(currencies))
    evidence.append(
        Evidence(
            evidence_type="eligible_catalog_price_distribution",
            value=p50,
            source="store_catalog",
            independence_group="catalog_pricing_offer",
            observed_at=evidence[0].observed_at,
            reliability=Decimal("0.45"),
            unit=currency,
            details=f"p25={p25}; median={p50}; p75={p75}; count={len(prices)}",
        )
    )
    low = _money(p25 * assumptions.items_per_order_low)
    central = _money(p50 * assumptions.items_per_order_central)
    high = _money(p75 * assumptions.items_per_order_high)
    confidence = min(
        Decimal("0.49"),
        Decimal("0.35") + Decimal(min(max(len(prices) - 5, 0), 10)) * Decimal("0.01"),
    )
    return InsightResult(
        metric="estimated_average_order_value",
        status="available",
        low=low,
        central=central,
        high=high,
        unit="currency_per_order",
        currency=currency,
        confidence_score=confidence,
        confidence_label=_confidence_label(confidence),
        evidence=tuple(evidence),
        assumptions=config,
        missing_signals=("observed_basket_value", "product_sales_mix", "bundle_take_rate"),
        explanation=(
            "AOV uses the 25th/50th/75th percentiles of likely sellable merchandise multiplied by disclosed "
            "items-per-order planning priors. Catalog prices are not observed basket values, so confidence is capped low."
        ),
        estimator_version=AOV_ESTIMATOR_VERSION,
    )


def _merge_assumptions(*results: InsightResult) -> dict[str, object]:
    merged: dict[str, object] = {}
    for result in results:
        merged.update(result.assumptions)
    return merged


def _unique_evidence(items: Iterable[Evidence]) -> tuple[Evidence, ...]:
    unique: list[Evidence] = []
    keys: set[tuple[object, ...]] = set()
    for item in items:
        key = (
            item.evidence_type,
            str(item.value),
            item.source,
            item.independence_group,
            str(item.observed_at),
        )
        if key not in keys:
            keys.add(key)
            unique.append(item)
    return tuple(unique)


def estimate_orders(
    traffic: InsightResult,
    *,
    assumptions: EstimatorAssumptions = DEFAULT_ASSUMPTIONS,
) -> InsightResult:
    """Estimate monthly orders only when a visit range is available."""

    config = _merge_assumptions(traffic)
    config.update(
        {
            "conversion_rate_low": assumptions.conversion_rate_low,
            "conversion_rate_central": assumptions.conversion_rate_central,
            "conversion_rate_high": assumptions.conversion_rate_high,
            "conversion_prior_kind": "uncategorized_user_adjustable_planning_prior",
        }
    )
    if (
        traffic.status != "available"
        or traffic.low is None
        or traffic.central is None
        or traffic.high is None
        or traffic.metric != "estimated_monthly_visits"
    ):
        return InsightResult(
            metric="estimated_monthly_orders",
            status="insufficient_data",
            confidence_score=Decimal("0"),
            confidence_label="insufficient_data",
            evidence=traffic.evidence,
            assumptions=config,
            missing_signals=tuple((*traffic.missing_signals, "estimated_monthly_visits")),
            explanation="Orders are withheld because a monthly visit range is required; rank is not converted to visits.",
            estimator_version=ORDERS_ESTIMATOR_VERSION,
        )

    low = (traffic.low * assumptions.conversion_rate_low).to_integral_value(rounding=ROUND_FLOOR)
    central = (traffic.central * assumptions.conversion_rate_central).to_integral_value(rounding=ROUND_HALF_UP)
    high = (traffic.high * assumptions.conversion_rate_high).to_integral_value(rounding=ROUND_CEILING)
    confidence = min(traffic.confidence_score, Decimal("0.45"))
    return InsightResult(
        metric="estimated_monthly_orders",
        status="available",
        low=low,
        central=central,
        high=high,
        unit="orders_per_month",
        confidence_score=confidence,
        confidence_label=_confidence_label(confidence),
        evidence=traffic.evidence,
        assumptions=config,
        missing_signals=tuple((*traffic.missing_signals, "observed_conversion_rate", "checkout_orders")),
        explanation=(
            "Monthly orders equal the traffic range multiplied by the disclosed uncategorized conversion-rate prior. "
            "Advertising activity is not used as a conversion multiplier. Confidence is capped low while conversion is generic."
        ),
        estimator_version=ORDERS_ESTIMATOR_VERSION,
    )


def estimate_gross_revenue(orders: InsightResult, aov: InsightResult) -> InsightResult:
    """Estimate gross monthly store revenue; never estimate profit here."""

    config = _merge_assumptions(orders, aov)
    config["revenue_kind"] = "gross_store_revenue_not_profit"
    if (
        orders.status != "available"
        or aov.status != "available"
        or any(value is None for value in (orders.low, orders.central, orders.high, aov.low, aov.central, aov.high))
        or not aov.currency
    ):
        missing = tuple(
            dict.fromkeys((*orders.missing_signals, *aov.missing_signals, "monthly_orders_and_aov"))
        )
        return InsightResult(
            metric="estimated_monthly_gross_revenue",
            status="insufficient_data",
            confidence_score=Decimal("0"),
            confidence_label="insufficient_data",
            evidence=_unique_evidence((*orders.evidence, *aov.evidence)),
            assumptions=config,
            missing_signals=missing,
            explanation="Gross revenue is withheld because both monthly order and AOV ranges are required.",
            estimator_version=REVENUE_ESTIMATOR_VERSION,
        )

    low = _money(orders.low * aov.low)  # type: ignore[operator]
    central = _money(orders.central * aov.central)  # type: ignore[operator]
    high = _money(orders.high * aov.high)  # type: ignore[operator]
    confidence = min(orders.confidence_score, aov.confidence_score, Decimal("0.45"))
    return InsightResult(
        metric="estimated_monthly_gross_revenue",
        status="available",
        low=low,
        central=central,
        high=high,
        unit="currency_per_month",
        currency=aov.currency,
        confidence_score=confidence,
        confidence_label=_confidence_label(confidence),
        evidence=_unique_evidence((*orders.evidence, *aov.evidence)),
        assumptions=config,
        missing_signals=tuple(
            dict.fromkeys((*orders.missing_signals, *aov.missing_signals, "first_party_revenue"))
        ),
        explanation=(
            "Estimated gross monthly revenue is the order range multiplied by the AOV range. "
            "It is not profit and does not subtract product, advertising, fulfillment, payment, or operating costs."
        ),
        estimator_version=REVENUE_ESTIMATOR_VERSION,
    )


def _momentum_assumptions(config: EstimatorAssumptions) -> dict[str, Decimal | int | str]:
    values: dict[str, Decimal | int | str] = {
        "minimum_independent_groups": config.momentum_minimum_groups,
        "minimum_observation_span_days": config.momentum_minimum_span_days,
        "freshness_days": config.freshness_days,
        "group_aggregation": "maximum_effective_signal_within_correlated_group",
        "score_kind": "evidence_score_not_calibrated_sales_probability",
    }
    for group, weight in config.momentum_weights:
        values[f"weight_{group}"] = weight
    return values


def estimate_product_momentum(
    evidence: Sequence[Evidence],
    *,
    first_observed_at: date | datetime | None = None,
    latest_observed_at: date | datetime | None = None,
    as_of: date | datetime | None = None,
    assumptions: EstimatorAssumptions = DEFAULT_ASSUMPTIONS,
) -> InsightResult:
    """Score product demand evidence after independence and history gates."""

    today = _today(as_of)
    weights = assumptions.momentum_weight_map
    config = _momentum_assumptions(assumptions)
    dated = [_as_date(item.observed_at) for item in evidence if _as_date(item.observed_at)]
    first = _as_date(first_observed_at) or (min(dated) if dated else None)
    latest = _as_date(latest_observed_at) or (max(dated) if dated else None)
    span_days = max(0, (latest - first).days) if first and latest else 0

    best_by_group: dict[str, tuple[Decimal, Decimal]] = {}
    accepted_evidence: list[Evidence] = []
    any_fresh = False
    for item in evidence:
        group = item.independence_group
        if group not in weights:
            continue
        strength = _decimal(item.value)
        if strength is None or strength < 0 or strength > 1:
            continue
        observed = _as_date(item.observed_at)
        is_fresh = observed is not None and max(0, (today - observed).days) <= assumptions.freshness_days
        any_fresh = any_fresh or is_fresh
        freshness_factor = Decimal("1") if is_fresh else Decimal("0.50")
        effective_reliability = item.reliability * freshness_factor
        effective_strength = strength * effective_reliability
        current = best_by_group.get(group)
        if current is None or effective_strength > current[0]:
            best_by_group[group] = (effective_strength, effective_reliability)
        accepted_evidence.append(item)

    missing: list[str] = []
    if len(best_by_group) < assumptions.momentum_minimum_groups:
        missing.append(f"at_least_{assumptions.momentum_minimum_groups}_independent_evidence_groups")
    if span_days < assumptions.momentum_minimum_span_days:
        missing.append(f"at_least_{assumptions.momentum_minimum_span_days}_days_of_observation_history")
    if not any_fresh:
        missing.append("fresh_product_evidence")
    if missing and (
        len(best_by_group) < assumptions.momentum_minimum_groups
        or span_days < assumptions.momentum_minimum_span_days
    ):
        return InsightResult(
            metric="product_momentum",
            status="insufficient_data",
            unit="score_0_100",
            confidence_score=Decimal("0.10") if best_by_group else Decimal("0"),
            confidence_label="insufficient_data",
            evidence=tuple(accepted_evidence),
            assumptions=config,
            missing_signals=tuple(missing),
            explanation=(
                "Product momentum is withheld until at least two independent evidence groups and 14 days of history exist. "
                "Multiple facts from one correlated group do not satisfy the gate."
            ),
            estimator_version=PRODUCT_MOMENTUM_ESTIMATOR_VERSION,
        )

    available_weight = sum((weights[group] for group in best_by_group), Decimal("0"))
    weighted_strength = sum(
        (weights[group] * values[0] for group, values in best_by_group.items()),
        Decimal("0"),
    )
    score = (
        weighted_strength / available_weight * Decimal("100")
        if available_weight > 0
        else Decimal("0")
    ).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    weighted_reliability = sum(
        (weights[group] * values[1] for group, values in best_by_group.items()),
        Decimal("0"),
    ) / available_weight
    span_factor = min(Decimal("1"), Decimal(span_days) / Decimal("30"))
    confidence = min(
        Decimal("0.74"),
        available_weight * weighted_reliability * span_factor,
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    classification = "strong" if score >= 70 else "moderate" if score >= 40 else "weak"
    missing_groups = [f"{group}_evidence" for group in weights if group not in best_by_group]
    if not any_fresh:
        missing_groups.append("fresh_product_evidence")
    return InsightResult(
        metric="product_momentum",
        status="available",
        classification=classification,
        score=score,
        unit="score_0_100",
        confidence_score=confidence,
        confidence_label=_confidence_label(confidence),
        evidence=tuple(accepted_evidence),
        assumptions=config,
        missing_signals=tuple(missing_groups),
        explanation=(
            f"The score aggregates {len(best_by_group)} independent evidence groups across {span_days} observed days. "
            "Correlated facts are collapsed to the strongest effective signal in each group. "
            "This is an evidence score, not a calibrated probability of sales."
        ),
        estimator_version=PRODUCT_MOMENTUM_ESTIMATOR_VERSION,
    )
