"""User-adjustable planning priors used by the first estimator versions."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class EstimatorAssumptions:
    """Defaults are disclosed planning priors, not claimed merchant facts."""

    conversion_rate_low: Decimal = Decimal("0.005")
    conversion_rate_central: Decimal = Decimal("0.012")
    conversion_rate_high: Decimal = Decimal("0.025")
    items_per_order_low: Decimal = Decimal("1")
    items_per_order_central: Decimal = Decimal("1.15")
    items_per_order_high: Decimal = Decimal("1.5")
    traffic_envelope_low: Decimal = Decimal("0.70")
    traffic_envelope_high: Decimal = Decimal("1.40")
    freshness_days: int = 45
    minimum_sellable_products: int = 5
    traffic_monthly_direction_threshold: Decimal = Decimal("0.05")
    traffic_endpoint_direction_threshold: Decimal = Decimal("0.10")
    momentum_minimum_groups: int = 2
    momentum_minimum_span_days: int = 14
    momentum_weights: tuple[tuple[str, Decimal], ...] = (
        ("advertising", Decimal("0.30")),
        ("reviews", Decimal("0.25")),
        ("merchandising", Decimal("0.15")),
        ("inventory", Decimal("0.15")),
        ("persistence", Decimal("0.10")),
        ("offer_page", Decimal("0.05")),
    )

    def __post_init__(self) -> None:
        ordered_ranges = (
            (
                self.conversion_rate_low,
                self.conversion_rate_central,
                self.conversion_rate_high,
            ),
            (
                self.items_per_order_low,
                self.items_per_order_central,
                self.items_per_order_high,
            ),
        )
        if any(not low <= central <= high for low, central, high in ordered_ranges):
            raise ValueError("Estimator ranges must be ordered low <= central <= high")
        if self.traffic_envelope_low <= 0 or self.traffic_envelope_high < 1:
            raise ValueError("Traffic envelope must have positive low and high >= 1")
        if self.freshness_days < 1:
            raise ValueError("freshness_days must be positive")
        if self.minimum_sellable_products < 1:
            raise ValueError("minimum_sellable_products must be positive")
        weights = dict(self.momentum_weights)
        if len(weights) != len(self.momentum_weights):
            raise ValueError("Momentum evidence groups must be unique")
        if any(weight < 0 for weight in weights.values()) or sum(weights.values()) != Decimal("1"):
            raise ValueError("Momentum weights must be non-negative and sum to 1")

    @property
    def momentum_weight_map(self) -> dict[str, Decimal]:
        return dict(self.momentum_weights)


DEFAULT_ASSUMPTIONS = EstimatorAssumptions()
