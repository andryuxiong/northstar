"""Typed, persistence-agnostic results for Northstar intelligence estimators."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal, Mapping, TypeAlias


InsightStatus: TypeAlias = Literal["available", "insufficient_data"]
ConfidenceLabel: TypeAlias = Literal["high", "medium", "low", "insufficient_data"]
EvidenceValue: TypeAlias = Decimal | int | str | bool
AssumptionValue: TypeAlias = Decimal | int | str | bool
ObservedAt: TypeAlias = date | datetime | None


@dataclass(frozen=True)
class Evidence:
    """One disclosed input to an insight.

    ``independence_group`` is intentionally first-class. Estimators aggregate
    correlated facts (for example ad count and ad longevity) inside their
    group before calculating confidence.
    """

    evidence_type: str
    value: EvidenceValue
    source: str
    independence_group: str
    observed_at: ObservedAt = None
    reliability: Decimal = Decimal("1")
    unit: str | None = None
    details: str | None = None

    def __post_init__(self) -> None:
        reliability = Decimal(str(self.reliability))
        if reliability < 0 or reliability > 1:
            raise ValueError("Evidence reliability must be between 0 and 1")
        object.__setattr__(self, "reliability", reliability)


@dataclass(frozen=True)
class InsightResult:
    """Consistent output shared by every versioned estimator."""

    metric: str
    status: InsightStatus
    low: Decimal | None = None
    central: Decimal | None = None
    high: Decimal | None = None
    classification: str | None = None
    score: Decimal | None = None
    unit: str | None = None
    currency: str | None = None
    confidence_score: Decimal = Decimal("0")
    confidence_label: ConfidenceLabel = "insufficient_data"
    evidence: tuple[Evidence, ...] = field(default_factory=tuple)
    assumptions: Mapping[str, AssumptionValue] = field(default_factory=dict)
    missing_signals: tuple[str, ...] = field(default_factory=tuple)
    explanation: str = ""
    estimator_version: str = ""

    def __post_init__(self) -> None:
        confidence = Decimal(str(self.confidence_score))
        if confidence < 0 or confidence > 1:
            raise ValueError("Confidence must be between 0 and 1")
        object.__setattr__(self, "confidence_score", confidence)

        bounds = tuple(
            Decimal(str(value)) if value is not None else None
            for value in (self.low, self.central, self.high)
        )
        object.__setattr__(self, "low", bounds[0])
        object.__setattr__(self, "central", bounds[1])
        object.__setattr__(self, "high", bounds[2])
        if all(value is not None for value in bounds):
            low, central, high = bounds
            if not low <= central <= high:  # type: ignore[operator]
                raise ValueError("Insight ranges must satisfy low <= central <= high")

        if self.score is not None:
            score = Decimal(str(self.score))
            if score < 0 or score > 100:
                raise ValueError("Insight score must be between 0 and 100")
            object.__setattr__(self, "score", score)

        object.__setattr__(self, "evidence", tuple(self.evidence))
        object.__setattr__(self, "missing_signals", tuple(dict.fromkeys(self.missing_signals)))
        object.__setattr__(self, "assumptions", dict(self.assumptions))

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready structure while retaining decimal precision."""

        def encode(value: Any) -> Any:
            if isinstance(value, Decimal):
                return str(value)
            if isinstance(value, (date, datetime)):
                return value.isoformat()
            if isinstance(value, Evidence):
                return {
                    "type": value.evidence_type,
                    "value": encode(value.value),
                    "source": value.source,
                    "independence_group": value.independence_group,
                    "observed_at": encode(value.observed_at),
                    "reliability": encode(value.reliability),
                    "unit": value.unit,
                    "details": value.details,
                }
            if isinstance(value, Mapping):
                return {key: encode(item) for key, item in value.items()}
            if isinstance(value, tuple):
                return [encode(item) for item in value]
            return value

        return {
            "metric": self.metric,
            "status": self.status,
            "low": encode(self.low),
            "central": encode(self.central),
            "high": encode(self.high),
            "classification": self.classification,
            "score": encode(self.score),
            "unit": self.unit,
            "currency": self.currency,
            "confidence_score": encode(self.confidence_score),
            "confidence_label": self.confidence_label,
            "evidence": encode(self.evidence),
            "assumptions": encode(self.assumptions),
            "missing_signals": list(self.missing_signals),
            "explanation": self.explanation,
            "estimator_version": self.estimator_version,
        }
