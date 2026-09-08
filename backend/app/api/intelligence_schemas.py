"""Typed API contracts for decision-oriented Northstar intelligence.

The response deliberately uses one insight shape for ranges, scores, and
classifications.  A missing value is represented by ``insufficient_data`` and
an explicit list of missing signals, never by a made-up zero.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


InsightStatus = Literal["available", "insufficient_data"]
ConfidenceLabel = Literal["high", "medium", "low", "insufficient_data"]


class EvidenceItemOut(BaseModel):
    id: int | None = None
    type: str
    label: str
    value: Any = None
    source: str
    observed_at: datetime | str | None = None
    source_url: str | None = None
    reliability: float | None = Field(default=None, ge=0, le=1)
    independence_group: str | None = None
    detail: str | None = None


class InsightOut(BaseModel):
    metric: str
    status: InsightStatus
    low: float | None = None
    central: float | None = None
    high: float | None = None
    value: str | float | bool | None = None
    score: float | None = Field(default=None, ge=0, le=100)
    unit: str | None = None
    currency: str | None = None
    confidence_score: float = Field(ge=0, le=1)
    confidence_label: ConfidenceLabel
    evidence: list[EvidenceItemOut] = Field(default_factory=list)
    assumptions: dict[str, Any] = Field(default_factory=dict)
    missing_signals: list[str] = Field(default_factory=list)
    explanation: str
    estimator_version: str
    calculated_at: datetime

    @model_validator(mode="after")
    def validate_range_and_status(self):
        values = [value for value in (self.low, self.central, self.high) if value is not None]
        if len(values) >= 2 and values != sorted(values):
            raise ValueError("insight range must be ordered low <= central <= high")
        if self.status == "insufficient_data" and not self.missing_signals:
            raise ValueError("insufficient insights must identify missing signals")
        has_any_range = any(value is not None for value in (self.low, self.central, self.high))
        has_complete_range = all(value is not None for value in (self.low, self.central, self.high))
        has_scalar = self.value is not None or self.score is not None
        if self.status == "available" and not (has_complete_range or has_scalar):
            raise ValueError("available insights must carry a complete range, classification, or score")
        if self.status == "available" and has_any_range and not has_complete_range:
            raise ValueError("available range insights must include low, central, and high")
        if self.status == "insufficient_data" and (has_any_range or has_scalar):
            raise ValueError("insufficient insights cannot carry estimate values")
        if self.status == "insufficient_data" and self.confidence_label != "insufficient_data":
            raise ValueError("insufficient insights must use the insufficient_data confidence label")
        return self


class StoreReportIdentityOut(BaseModel):
    id: int
    domain: str
    brand_name: str | None = None
    platform: str
    category: str | None = None
    market: str | None = None
    logo_url: str | None = None
    first_seen_at: datetime
    last_seen_at: datetime
    product_count: int
    theme: dict[str, Any] | None = None


class ExecutiveMetricsOut(BaseModel):
    monthly_visits: InsightOut
    monthly_orders: InsightOut
    monthly_revenue: InsightOut
    aov: InsightOut
    store_momentum: InsightOut
    advertising_status: InsightOut
    dropshipping_likelihood: InsightOut


class ExecutiveSummaryOut(BaseModel):
    verdict: str
    strongest_evidence: str
    largest_uncertainty: str
    next_step: str
    overall_confidence: ConfidenceLabel
    metrics: ExecutiveMetricsOut


class TrafficPeriodOut(BaseModel):
    period: str
    visits: float | None = None
    global_rank: int | None = None
    status: str
    source: str
    observed_at: datetime | str | None = None


class TrafficReportOut(BaseModel):
    status: str
    provider: str | None = None
    periods: list[TrafficPeriodOut] = Field(default_factory=list)
    trend: InsightOut
    unavailable_metrics: list[str] = Field(default_factory=list)
    source_notice: str
    reporting_date: datetime | str | None = None


class ProductReportOut(BaseModel):
    rank: int
    id: int
    title: str
    url: str
    image_url: str | None = None
    current_price: float | None = None
    currency: str | None = None
    first_seen_at: datetime
    momentum: InsightOut
    active_related_ads: InsightOut
    review_signal: InsightOut
    sales_contribution: InsightOut
    saturation: InsightOut
    supplier_match: InsightOut
    estimated_margin: InsightOut
    reasons: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    confidence: ConfidenceLabel


class AdsReportOut(BaseModel):
    status: str
    active_count: int | None = None
    historical_count: int | None = None
    distinct_creatives: int | None = None
    earliest_delivery_start: datetime | None = None
    longest_running_days: int | None = None
    matched_identity: str | None = None
    match_confidence: ConfidenceLabel = "insufficient_data"
    explanation: str
    missing_signals: list[str] = Field(default_factory=list)


class OfferOut(BaseModel):
    type: str
    text: str
    effective_discount: float | None = None
    minimum_spend: float | None = None
    currency: str | None = None
    scope: str | None = None
    persistence: str | None = None
    confidence_label: ConfidenceLabel
    evidence: list[EvidenceItemOut] = Field(default_factory=list)


class FunnelElementOut(BaseModel):
    element: str
    page_type: str
    confidence_label: ConfidenceLabel
    evidence: list[EvidenceItemOut] = Field(default_factory=list)


class OffersFunnelReportOut(BaseModel):
    status: str
    primary_offer: OfferOut | None = None
    offers: list[OfferOut] = Field(default_factory=list)
    funnel_elements: list[FunnelElementOut] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    missing_signals: list[str] = Field(default_factory=list)


class TechnologyOut(BaseModel):
    name: str
    category: str
    icon_url: str | None = None
    why_it_matters: str
    confidence_label: ConfidenceLabel
    evidence: list[EvidenceItemOut] = Field(default_factory=list)


class TechnologyReportOut(BaseModel):
    status: str
    detections: list[TechnologyOut] = Field(default_factory=list)
    missing_signals: list[str] = Field(default_factory=list)
    pages_scanned: int = 0
    coverage_notice: str | None = None


class EvidenceAssumptionsOut(BaseModel):
    profile_id: int | None = None
    profile_name: str
    category_key: str
    assumptions: dict[str, Any]
    evidence: list[EvidenceItemOut] = Field(default_factory=list)
    missing_signals: list[str] = Field(default_factory=list)
    analysis_version: str


class DiagnosticSourceOut(BaseModel):
    id: int
    url: str
    type: str
    status: str | None = None
    http_status: int | None = None
    fetched_at: datetime | None = None


class DiagnosticJobOut(BaseModel):
    id: str
    label: str
    status: str
    created_at: str
    error: str | None = None


class DiagnosticsOut(BaseModel):
    source_count: int
    fetched_source_count: int
    failed_source_count: int
    product_snapshot_count: int
    store_snapshot_count: int
    auxiliary_product_count: int = 0
    sources: list[DiagnosticSourceOut] = Field(default_factory=list)
    recent_jobs: list[DiagnosticJobOut] = Field(default_factory=list)


class StoreIntelligenceReportOut(BaseModel):
    report_version: str
    generated_at: datetime
    store: StoreReportIdentityOut
    executive_summary: ExecutiveSummaryOut
    traffic: TrafficReportOut
    products: list[ProductReportOut]
    ads: AdsReportOut
    offers_and_funnel: OffersFunnelReportOut
    technology: TechnologyReportOut
    evidence_and_assumptions: EvidenceAssumptionsOut
    diagnostics: DiagnosticsOut


class EstimationProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category_key: str
    is_default: bool
    version: str
    conversion_rate_low: float
    conversion_rate_central: float | None
    conversion_rate_high: float
    basket_multiplier_low: float
    basket_multiplier_central: float | None
    basket_multiplier_high: float
    traffic_reliability_low: float
    traffic_reliability_central: float | None
    traffic_reliability_high: float
    freshness_limit_days: int
    minimum_evidence_count: int
    score_weights: dict[str, float]
    thresholds: dict[str, Any]
    updated_at: datetime


class EstimationProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    conversion_rate_low: float | None = Field(default=None, ge=0, le=1)
    conversion_rate_central: float | None = Field(default=None, ge=0, le=1)
    conversion_rate_high: float | None = Field(default=None, ge=0, le=1)
    basket_multiplier_low: float | None = Field(default=None, gt=0, le=20)
    basket_multiplier_central: float | None = Field(default=None, gt=0, le=20)
    basket_multiplier_high: float | None = Field(default=None, gt=0, le=20)
    traffic_reliability_low: float | None = Field(default=None, gt=0, le=5)
    traffic_reliability_central: float | None = Field(default=None, gt=0, le=5)
    traffic_reliability_high: float | None = Field(default=None, gt=0, le=5)
    freshness_limit_days: int | None = Field(default=None, ge=1, le=365)
    minimum_evidence_count: int | None = Field(default=None, ge=1, le=6)
    score_weights: dict[str, float] | None = None
    thresholds: dict[str, float] | None = None

    @model_validator(mode="after")
    def validate_ranges(self):
        for prefix in ("conversion_rate", "basket_multiplier", "traffic_reliability"):
            values = [getattr(self, f"{prefix}_{part}") for part in ("low", "central", "high")]
            known = [value for value in values if value is not None]
            if len(known) == 3 and known != sorted(known):
                raise ValueError(f"{prefix} must be ordered low <= central <= high")
        if self.score_weights is not None:
            expected = {
                "advertising",
                "reviews",
                "merchandising",
                "inventory",
                "persistence",
                "offer_page",
            }
            if set(self.score_weights) != expected:
                raise ValueError(
                    "score weights must include exactly advertising, reviews, merchandising, inventory, persistence, and offer_page"
                )
            if any(weight < 0 or weight > 1 for weight in self.score_weights.values()):
                raise ValueError("product weights must be between 0 and 1")
            if abs(sum(self.score_weights.values()) - 1) > 0.000001:
                raise ValueError("product weights must sum to 1")
            if (
                self.minimum_evidence_count is not None
                and self.minimum_evidence_count
                > sum(weight > 0 for weight in self.score_weights.values())
            ):
                raise ValueError("minimum evidence cannot exceed enabled weight groups")
        if self.thresholds is not None:
            allowed = {
                "minimum_sellable_products",
                "traffic_monthly_direction",
                "traffic_endpoint_direction",
                "momentum_minimum_span_days",
            }
            unknown = set(self.thresholds) - allowed
            if unknown:
                raise ValueError(f"unknown estimator thresholds: {', '.join(sorted(unknown))}")
            for key in ("minimum_sellable_products", "momentum_minimum_span_days"):
                value = self.thresholds.get(key)
                if value is not None and (value != int(value) or value < 1 or value > 365):
                    raise ValueError(f"{key} must be a whole number between 1 and 365")
            for key in ("traffic_monthly_direction", "traffic_endpoint_direction"):
                value = self.thresholds.get(key)
                if value is not None and (value < 0 or value > 2):
                    raise ValueError(f"{key} must be between 0 and 2")
        return self
