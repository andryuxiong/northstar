from datetime import date, datetime
from decimal import Decimal
import re
from typing import List, Literal, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

from app.services.similarweb import default_month, normalize_domain
from app.utils.urls import normalize_public_url


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    email: Optional[str]
    created_at: datetime


class UrlIngest(BaseModel):
    url: str
    optional_tag_names: Optional[List[str]] = None

    @field_validator("url", mode="before")
    @classmethod
    def normalize_url(cls, value: str) -> str:
        return normalize_public_url(value)


class AdMetricIn(BaseModel):
    metric_key: str = Field(min_length=1, max_length=100)
    value_kind: Literal[
        "exact",
        "reported_value",
        "range",
        "percentile",
        "classification",
        "unavailable",
    ]
    value_numeric: Optional[Decimal] = Field(default=None, ge=0)
    range_low: Optional[Decimal] = Field(default=None, ge=0)
    range_high: Optional[Decimal] = Field(default=None, ge=0)
    value_text: Optional[str] = Field(default=None, max_length=1000)
    unit: Optional[str] = Field(default=None, max_length=50)
    provider: str = Field(default="manual_public_source", min_length=1, max_length=100)
    source_type: str = Field(default="manual_public_capture", min_length=1, max_length=100)
    geography: Optional[str] = Field(default=None, max_length=100)
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    confidence_score: Optional[Decimal] = Field(default=None, ge=0, le=1)
    observed_at: Optional[datetime] = None
    metadata: Optional[dict] = None

    @field_validator("metric_key", mode="before")
    @classmethod
    def normalize_metric_key(cls, value: str) -> str:
        normalized = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,99}", normalized):
            raise ValueError("Metric keys must use lowercase letters, numbers, and underscores")
        return normalized

    @field_validator("provider", "source_type", mode="before")
    @classmethod
    def normalize_metric_source(cls, value: str) -> str:
        return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")

    @model_validator(mode="after")
    def validate_metric_value(self):
        if self.period_start and self.period_end and self.period_end < self.period_start:
            raise ValueError("period_end cannot be earlier than period_start")
        if self.value_kind == "exact" and self.value_numeric is None:
            raise ValueError("Exact metrics require value_numeric")
        if self.value_kind == "range":
            if self.range_low is None or self.range_high is None:
                raise ValueError("Range metrics require range_low and range_high")
            if self.range_high < self.range_low:
                raise ValueError("range_high cannot be lower than range_low")
        if self.value_kind in {"reported_value", "percentile", "classification", "unavailable"}:
            if self.value_numeric is None and not (self.value_text or "").strip():
                raise ValueError(f"{self.value_kind} metrics require a numeric or text value")
        return self


class AdMetricOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ad_id: int
    metric_key: str
    value_kind: str
    value_numeric: Optional[Decimal] = None
    range_low: Optional[Decimal] = None
    range_high: Optional[Decimal] = None
    value_text: Optional[str] = None
    unit: Optional[str] = None
    provider: str
    source_type: str
    source_url: Optional[str] = None
    geography: Optional[str] = None
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    confidence_score: Optional[Decimal] = None
    observed_at: datetime
    retrieved_at: datetime
    metadata: Optional[dict] = Field(default=None, validation_alias="metadata_json")


class AdCaptureMetadata(BaseModel):
    adapter_id: str = Field(min_length=1, max_length=100)
    adapter_version: str = Field(min_length=1, max_length=100)
    confidence: Literal["low", "medium", "high"]
    warnings: List[str] = Field(default_factory=list, max_length=25)
    captured_fields: List[str] = Field(default_factory=list, max_length=25)

    @field_validator("warnings", "captured_fields")
    @classmethod
    def limit_capture_metadata_strings(cls, value: List[str]) -> List[str]:
        return [str(item).strip()[:500] for item in value if str(item).strip()]


class AdIngest(BaseModel):
    platform: Literal["meta", "tiktok", "google", "manual"]
    source_url: Optional[str] = None
    ad_text: Optional[str] = None
    headline: Optional[str] = None
    cta: Optional[str] = None
    creative_type: Literal["image", "video", "carousel", "unknown"] = "unknown"
    creative_urls: Optional[List[str]] = None
    landing_url: Optional[str] = None
    advertiser_name: Optional[str] = None
    metrics: List[AdMetricIn] = Field(default_factory=list, max_length=25)
    capture_metadata: Optional[AdCaptureMetadata] = None

    @field_validator("source_url", "landing_url", mode="before")
    @classmethod
    def normalize_optional_ad_url(cls, value: Optional[str]) -> Optional[str]:
        if value is None or not str(value).strip():
            return None
        return normalize_public_url(str(value))

    @field_validator("creative_urls", mode="before")
    @classmethod
    def normalize_ad_media_urls(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        if value is None:
            return None
        urls = [normalize_public_url(str(item)) for item in value if str(item).strip()]
        return list(dict.fromkeys(urls)) or None

    @model_validator(mode="after")
    def require_public_ad_evidence(self):
        if not self.source_url and not self.creative_urls and not self.landing_url:
            raise ValueError("Provide a public ad source URL, creative URL, or landing URL")
        return self


class MetaAdsSearchIngest(BaseModel):
    search_terms: Optional[str] = Field(default=None, max_length=100)
    search_page_ids: Optional[List[str]] = None
    ad_reached_countries: List[str] = Field(min_length=1, max_length=25)
    ad_type: str = "ALL"
    ad_active_status: Optional[str] = None
    ad_delivery_date_min: Optional[str] = None
    ad_delivery_date_max: Optional[str] = None
    fields: Optional[str] = Field(default=None, max_length=2000)
    limit: int = Field(default=50, ge=1, le=500)

    @field_validator("search_terms", mode="before")
    @classmethod
    def normalize_search_terms(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return str(value).strip() or None

    @field_validator("search_page_ids", mode="before")
    @classmethod
    def normalize_page_ids(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        if value is None:
            return None
        page_ids = [str(item).strip() for item in value if str(item).strip()]
        if any(not item.isdigit() for item in page_ids):
            raise ValueError("Meta page IDs must be numeric")
        return list(dict.fromkeys(page_ids)) or None

    @field_validator("ad_reached_countries", mode="before")
    @classmethod
    def normalize_countries(cls, value: List[str]) -> List[str]:
        countries = [str(item).strip().upper() for item in (value or [])]
        countries = list(dict.fromkeys(item for item in countries if item))
        if not countries or any(item != "ALL" and (len(item) != 2 or not item.isalpha()) for item in countries):
            raise ValueError("Use two-letter country codes such as US, or ALL")
        return countries

    @field_validator("ad_type", mode="before")
    @classmethod
    def normalize_ad_type(cls, value: Optional[str]) -> str:
        return str(value or "ALL").strip().upper()

    @field_validator("ad_active_status", mode="before")
    @classmethod
    def normalize_active_status(cls, value: Optional[str]) -> Optional[str]:
        if value is None or not str(value).strip():
            return None
        status = str(value).strip().upper()
        if status not in {"ACTIVE", "INACTIVE", "ALL"}:
            raise ValueError("ad_active_status must be ACTIVE, INACTIVE, or ALL")
        return status

    @field_validator("ad_delivery_date_min", "ad_delivery_date_max")
    @classmethod
    def validate_delivery_date(cls, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError("Meta delivery dates must use YYYY-MM-DD") from exc
        return value

    @model_validator(mode="after")
    def validate_meta_query(self):
        if not self.search_terms and not self.search_page_ids:
            raise ValueError("Provide search_terms or at least one search_page_id")
        if (
            self.ad_delivery_date_min
            and self.ad_delivery_date_max
            and self.ad_delivery_date_max < self.ad_delivery_date_min
        ):
            raise ValueError("ad_delivery_date_max cannot be earlier than ad_delivery_date_min")
        return self


class StoreIngest(BaseModel):
    domain: str

    @field_validator("domain", mode="before")
    @classmethod
    def normalize_domain(cls, value: str) -> str:
        return urlparse(normalize_public_url(value)).netloc


class ProductOut(BaseModel):
    id: int
    canonical_url: str
    title: str
    currency: Optional[str]
    last_seen_at: datetime


class ProductDetail(ProductOut):
    description: Optional[str]
    store_id: int


class ScoreOut(BaseModel):
    score_type: str
    score_value: float
    confidence: float
    components_json: Optional[dict]


class SignalOut(BaseModel):
    signal_type: str
    value_json: Optional[dict]
    computed_at: datetime


class ProductHistoryPoint(BaseModel):
    fetched_at: datetime
    price_min: Optional[float]
    price_max: Optional[float]
    available: Optional[bool]
    variant_count: Optional[int]


class AdOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    external_ad_id: Optional[str] = None
    data_provider: str = "northstar_manual"
    source_type: str = "manual_import"
    provider_record_id: Optional[str] = None
    source_url: Optional[str] = None
    provider_metadata: Optional[dict] = Field(
        default=None,
        validation_alias="provider_metadata_json",
    )
    platform: str
    advertiser_name: Optional[str] = None
    advertiser_id: Optional[str] = None
    ad_text: Optional[str] = None
    headline: Optional[str] = None
    cta: Optional[str] = None
    ad_creation_time: Optional[datetime] = None
    delivery_start_time: Optional[datetime] = None
    delivery_stop_time: Optional[datetime] = None
    ad_snapshot_url: Optional[str] = None
    publisher_platforms: Optional[List[str]] = Field(
        default=None,
        validation_alias="publisher_platforms_json",
    )
    creative_type: str
    creative_urls: Optional[List[str]] = Field(default=None, validation_alias="creative_urls_json")
    landing_url: Optional[str] = None
    first_seen_at: datetime
    last_seen_at: datetime


class AdAutopsyProductOut(BaseModel):
    id: int
    title: str
    canonical_url: str
    currency: Optional[str] = None
    store_id: int
    store_domain: str


class AdAutopsyLandingOut(BaseModel):
    source_url_id: int
    url: str
    fetch_status: Optional[str] = None
    last_http_status: Optional[int] = None
    last_fetched_at: Optional[datetime] = None
    final_url: Optional[str] = None
    snapshot_fetched_at: Optional[datetime] = None
    products: List[AdAutopsyProductOut] = Field(default_factory=list)


class AdAutopsyStoreOut(BaseModel):
    id: int
    domain: str
    platform: str
    last_seen_at: datetime


class AdAutopsyRelatedOut(BaseModel):
    ad: AdOut
    reasons: List[str]


class AdAutopsyConclusionOut(BaseModel):
    status: Literal["investigate", "weak_evidence", "insufficient_data"]
    label: str
    explanation: str
    next_step: str


class AdAutopsyCreativeAnalysisOut(BaseModel):
    asset_count: int
    media_state: Literal["available", "not_saved"]
    transcript_status: Literal["not_collected"] = "not_collected"
    ocr_status: Literal["not_collected"] = "not_collected"
    notice: str


class AdAutopsyOut(BaseModel):
    ad: AdOut
    analytics: dict
    creative_analysis: AdAutopsyCreativeAnalysisOut
    landing_pages: List[AdAutopsyLandingOut] = Field(default_factory=list)
    store: Optional[AdAutopsyStoreOut] = None
    products: List[AdAutopsyProductOut] = Field(default_factory=list)
    related_ads: List[AdAutopsyRelatedOut] = Field(default_factory=list)
    conclusion: AdAutopsyConclusionOut


class MetaAdsStatusOut(BaseModel):
    provider: str = "meta_ad_library"
    source: str = "official_meta_graph_api"
    configured: bool
    graph_version: str
    requires_access_token: bool = True


class MetaAdsErrorOut(BaseModel):
    code: str
    message: str
    upstream_http_status: Optional[int] = None
    provider_code: Optional[int | str] = None
    provider_subcode: Optional[int | str] = None
    provider_type: Optional[str] = None
    trace_id: Optional[str] = None


class MetaAdsSearchOut(BaseModel):
    provider: str = "meta_ad_library"
    source: str = "official_meta_graph_api"
    configured: bool
    status: str
    graph_version: str
    requested_limit: int
    fetched_count: int = 0
    inserted_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    effective_fields: List[str]
    ads: List[AdOut] = Field(default_factory=list)
    error: Optional[MetaAdsErrorOut] = None


class MetaAdsConfigIn(BaseModel):
    access_token: SecretStr = Field(min_length=1, max_length=4000)

    @field_validator("access_token", mode="before")
    @classmethod
    def strip_access_token(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("A Meta access token is required")
        return value.strip()


class GetHookdConfigIn(BaseModel):
    api_token: SecretStr = Field(min_length=1, max_length=4000)

    @field_validator("api_token", mode="before")
    @classmethod
    def strip_api_token(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("A GetHookd API token is required")
        return value.strip()


class GetHookdExploreIn(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    limit: int = Field(default=20, ge=1, le=100)
    page: int = Field(default=1, ge=1, le=1000)
    platform: Optional[Literal["facebook", "instagram", "tiktok", "google"]] = None
    status: Optional[Literal["active", "inactive"]] = None
    ad_format: Optional[Literal["image", "video", "carousels"]] = None
    minimum_days_active: Optional[int] = Field(default=None, ge=1, le=3650)
    sort_column: Literal["created_at", "start_date", "days_active", "used_count", "popularity"] = (
        "days_active"
    )
    sort_direction: Literal["asc", "desc"] = "desc"

    @field_validator("query", mode="before")
    @classmethod
    def strip_query(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("An ad search query is required")
        return value.strip()


class StoreOut(BaseModel):
    id: int
    domain: str
    platform_guess: str
    last_seen_at: datetime


class SimilarwebConfigIn(BaseModel):
    api_key: SecretStr = Field(min_length=1, max_length=1000)

    @field_validator("api_key", mode="before")
    @classmethod
    def strip_api_key(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("A Similarweb API key is required")
        return value.strip()


class TrafficRefreshIn(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    country: str = "world"
    main_domain_only: bool = True
    force: bool = False

    @field_validator("country", mode="before")
    @classmethod
    def normalize_country(cls, value: str) -> str:
        value = (value or "world").strip().lower()
        if value != "world" and (len(value) != 2 or not value.isalpha()):
            raise ValueError("Country must be 'world' or a two-letter country code")
        return value

    @model_validator(mode="after")
    def validate_period(self):
        self.start_date = self.start_date or default_month()
        self.end_date = self.end_date or self.start_date
        try:
            start = datetime.strptime(self.start_date, "%Y-%m")
            end = datetime.strptime(self.end_date, "%Y-%m")
        except ValueError as exc:
            raise ValueError("start_date and end_date must use YYYY-MM") from exc
        if end < start:
            raise ValueError("end_date cannot be earlier than start_date")
        months = (end.year - start.year) * 12 + end.month - start.month + 1
        if months > 12:
            raise ValueError("A refresh is limited to 12 months to control Similarweb credit use")
        return self


class SimilarwebTestIn(TrafficRefreshIn):
    domain: str

    @field_validator("domain", mode="before")
    @classmethod
    def normalize_test_domain(cls, value: str) -> str:
        return normalize_domain(value)
