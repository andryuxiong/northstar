from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.services.intelligence import (
    AOV_ESTIMATOR_VERSION,
    ORDERS_ESTIMATOR_VERSION,
    PRODUCT_MOMENTUM_ESTIMATOR_VERSION,
    REVENUE_ESTIMATOR_VERSION,
    TRAFFIC_ESTIMATOR_VERSION,
    Evidence,
    MerchandiseObservation,
    TrafficObservation,
    classify_sellable_merchandise,
    estimate_aov,
    estimate_gross_revenue,
    estimate_orders,
    estimate_product_momentum,
    estimate_traffic,
)


AS_OF = date(2026, 7, 10)


def _traffic_series(values, *, status="success", retrieved_at=AS_OF):
    return [
        TrafficObservation(
            period=f"2026-{month:02d}",
            visits=value,
            retrieved_at=retrieved_at,
            fetch_status=status,
        )
        for month, value in enumerate(values, start=1)
    ]


def _merchandise(prices, *, currency="USD"):
    return [
        MerchandiseObservation(
            title=f"Primary product {index}",
            price=price,
            currency=currency,
            product_id=index,
            observed_at=AS_OF,
        )
        for index, price in enumerate(prices, start=1)
    ]


def test_traffic_complete_series_returns_envelope_mom_and_direction():
    result = estimate_traffic(
        _traffic_series([100_000, 120_000, 150_000]),
        as_of=AS_OF,
    )

    assert result.status == "available"
    assert result.estimator_version == TRAFFIC_ESTIMATOR_VERSION
    assert (result.low, result.central, result.high) == (
        Decimal("105000.00"),
        Decimal("150000"),
        Decimal("210000.00"),
    )
    assert result.classification == "growing"
    assert result.assumptions["traffic_envelope_low_multiplier"] == Decimal("0.70")
    assert result.assumptions["traffic_envelope_high_multiplier"] == Decimal("1.40")
    assert result.assumptions["freshness_days"] == 45
    mom = next(item for item in result.evidence if item.evidence_type == "month_over_month_change")
    assert mom.value == Decimal("0.25")
    assert result.low <= result.central <= result.high


@pytest.mark.parametrize(
    ("values", "direction"),
    [
        ([100_000, 102_000, 101_000], "stable"),
        ([120_000, 100_000, 80_000], "declining"),
    ],
)
def test_traffic_three_month_direction_classification(values, direction):
    result = estimate_traffic(_traffic_series(values), as_of=AS_OF)
    assert result.classification == direction


def test_partial_traffic_stays_available_but_discloses_missing_provider_data():
    result = estimate_traffic(
        _traffic_series([42_000], status="partial"),
        as_of=AS_OF,
    )

    assert result.status == "available"
    assert result.classification == "insufficient_history"
    assert "complete_provider_traffic_response" in result.missing_signals
    assert "three_consecutive_months_of_traffic" in result.missing_signals
    assert result.confidence_score <= Decimal("0.50")


def test_global_rank_without_visits_is_insufficient_and_is_not_converted():
    result = estimate_traffic(
        [
            TrafficObservation(
                period="2026-06",
                visits=None,
                global_rank=1234,
                retrieved_at=AS_OF,
            )
        ],
        as_of=AS_OF,
    )

    assert result.status == "insufficient_data"
    assert result.low is result.central is result.high is None
    assert "estimated_monthly_visits" in result.missing_signals
    assert "not converted into visits" in result.explanation
    assert any(item.evidence_type == "global_rank" for item in result.evidence)


def test_stale_traffic_degrades_confidence_without_changing_provider_point():
    fresh = estimate_traffic(_traffic_series([100_000]), as_of=AS_OF)
    stale = estimate_traffic(
        _traffic_series([100_000], retrieved_at=AS_OF - timedelta(days=90)),
        as_of=AS_OF,
    )

    assert fresh.central == stale.central == Decimal("100000")
    assert stale.confidence_score < fresh.confidence_score
    assert "fresh_traffic_observation" in stale.missing_signals


def test_sellable_classifier_excludes_free_gifts_and_checkout_services():
    free_gift = classify_sellable_merchandise(
        MerchandiseObservation("Tripod (Free Gift)", 0, "USD")
    )
    protection = classify_sellable_merchandise(
        MerchandiseObservation("Shipping Protection", "2.99", "USD")
    )
    product = classify_sellable_merchandise(
        MerchandiseObservation("Portable Projector", "89.99", "USD")
    )

    assert (free_gift.is_sellable, free_gift.classification) == (False, "free_or_zero_price")
    assert (protection.is_sellable, protection.classification) == (False, "shipping_protection")
    assert (product.is_sellable, product.classification) == (True, "sellable_merchandise")


def test_aov_uses_eligible_quantiles_and_disclosed_items_per_order_priors():
    products = _merchandise([10, 20, 30, 40, 50]) + [
        MerchandiseObservation("Bonus Wallpapers (Free Gift)", 0, "USD"),
        MerchandiseObservation("Shipping Protection", "2.99", "USD"),
    ]
    result = estimate_aov(products)

    assert result.status == "available"
    assert result.estimator_version == AOV_ESTIMATOR_VERSION
    assert (result.low, result.central, result.high) == (
        Decimal("20.00"),
        Decimal("34.50"),
        Decimal("60.00"),
    )
    assert result.currency == "USD"
    assert result.confidence_label == "low"
    assert result.assumptions["items_per_order_low"] == Decimal("1")
    assert result.assumptions["items_per_order_central"] == Decimal("1.15")
    assert result.assumptions["items_per_order_high"] == Decimal("1.5")
    assert "observed_basket_value" in result.missing_signals


def test_aov_requires_at_least_five_sellable_products():
    result = estimate_aov(_merchandise([10, 20, 30, 40]))
    assert result.status == "insufficient_data"
    assert "at_least_5_sellable_products" in result.missing_signals


def test_aov_rejects_mixed_currency_catalog_instead_of_summing_currencies():
    products = _merchandise([10, 20, 30, 40, 50]) + [
        MerchandiseObservation("European product", 60, "EUR")
    ]
    result = estimate_aov(products)

    assert result.status == "insufficient_data"
    assert "single_catalog_currency" in result.missing_signals
    assert result.currency is None


def test_orders_require_visits_and_use_generic_conversion_range_with_low_confidence_cap():
    traffic = estimate_traffic(
        _traffic_series([100_000, 120_000, 150_000]),
        as_of=AS_OF,
    )
    result = estimate_orders(traffic)

    assert result.status == "available"
    assert result.estimator_version == ORDERS_ESTIMATOR_VERSION
    assert (result.low, result.central, result.high) == (
        Decimal("525"),
        Decimal("1800"),
        Decimal("5250"),
    )
    assert result.low <= result.central <= result.high
    assert result.confidence_score <= Decimal("0.49")
    assert result.confidence_label == "low"
    assert result.assumptions["conversion_rate_low"] == Decimal("0.005")
    assert result.assumptions["conversion_rate_central"] == Decimal("0.012")
    assert result.assumptions["conversion_rate_high"] == Decimal("0.025")


def test_orders_remain_unavailable_when_only_rank_exists():
    rank_only = estimate_traffic(
        [TrafficObservation("2026-06", None, AS_OF, global_rank=1000)],
        as_of=AS_OF,
    )
    result = estimate_orders(rank_only)
    assert result.status == "insufficient_data"
    assert result.low is result.central is result.high is None


def test_gross_revenue_multiplies_order_and_aov_ranges_and_never_claims_profit():
    traffic = estimate_traffic(
        _traffic_series([100_000, 120_000, 150_000]),
        as_of=AS_OF,
    )
    orders = estimate_orders(traffic)
    aov = estimate_aov(_merchandise([10, 20, 30, 40, 50]))
    result = estimate_gross_revenue(orders, aov)

    assert result.status == "available"
    assert result.estimator_version == REVENUE_ESTIMATOR_VERSION
    assert (result.low, result.central, result.high) == (
        Decimal("10500.00"),
        Decimal("62100.00"),
        Decimal("315000.00"),
    )
    assert result.low <= result.central <= result.high
    assert result.currency == "USD"
    assert result.confidence_label == "low"
    assert result.assumptions["revenue_kind"] == "gross_store_revenue_not_profit"
    assert "not profit" in result.explanation


def test_gross_revenue_is_withheld_when_aov_is_unavailable():
    traffic = estimate_traffic(_traffic_series([100_000]), as_of=AS_OF)
    orders = estimate_orders(traffic)
    unavailable_aov = estimate_aov(_merchandise([10, 20]))
    result = estimate_gross_revenue(orders, unavailable_aov)
    assert result.status == "insufficient_data"
    assert "monthly_orders_and_aov" in result.missing_signals


def _momentum_evidence(group, value, *, observed_at=AS_OF, reliability="0.9", kind=None):
    return Evidence(
        evidence_type=kind or f"{group}_signal",
        value=Decimal(str(value)),
        source="public_observation",
        independence_group=group,
        observed_at=observed_at,
        reliability=Decimal(reliability),
        unit="normalized_strength",
    )


def test_product_momentum_does_not_treat_correlated_ad_facts_as_independent_groups():
    ad_evidence = [
        _momentum_evidence("advertising", value, kind=f"ad_signal_{index}")
        for index, value in enumerate(("0.9", "0.8", "0.7"), start=1)
    ]
    result = estimate_product_momentum(
        ad_evidence,
        first_observed_at=AS_OF - timedelta(days=30),
        latest_observed_at=AS_OF,
        as_of=AS_OF,
    )

    assert result.status == "insufficient_data"
    assert "at_least_2_independent_evidence_groups" in result.missing_signals


def test_product_momentum_requires_fourteen_days_even_with_two_groups():
    result = estimate_product_momentum(
        [
            _momentum_evidence("advertising", "0.9"),
            _momentum_evidence("reviews", "0.8"),
        ],
        first_observed_at=AS_OF - timedelta(days=10),
        latest_observed_at=AS_OF,
        as_of=AS_OF,
    )

    assert result.status == "insufficient_data"
    assert "at_least_14_days_of_observation_history" in result.missing_signals


def test_product_momentum_scores_independent_groups_and_discloses_that_it_is_not_probability():
    base = [
        _momentum_evidence("advertising", "0.9", reliability="0.8"),
        _momentum_evidence("reviews", "0.8", reliability="0.9"),
    ]
    result = estimate_product_momentum(
        base,
        first_observed_at=AS_OF - timedelta(days=30),
        latest_observed_at=AS_OF,
        as_of=AS_OF,
    )

    assert result.status == "available"
    assert result.estimator_version == PRODUCT_MOMENTUM_ESTIMATOR_VERSION
    assert result.score == Decimal("72.0")
    assert result.classification == "strong"
    assert result.assumptions["minimum_independent_groups"] == 2
    assert result.assumptions["minimum_observation_span_days"] == 14
    assert "not a calibrated probability" in result.explanation

    # More facts from the same ad group cannot inflate the score or confidence.
    correlated = estimate_product_momentum(
        [*base, _momentum_evidence("advertising", "0.5"), _momentum_evidence("advertising", "0.4")],
        first_observed_at=AS_OF - timedelta(days=30),
        latest_observed_at=AS_OF,
        as_of=AS_OF,
    )
    assert correlated.score == result.score
    assert correlated.confidence_score == result.confidence_score


def test_insight_result_serializes_decimal_values_without_float_loss():
    result = estimate_aov(_merchandise([10, 20, 30, 40, 50]))
    payload = result.as_dict()
    assert payload["low"] == "20.00"
    assert payload["central"] == "34.50"
    assert payload["confidence_score"] == "0.35"
    assert payload["estimator_version"] == "aov-v1"
