import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base


portable_json_type = JSON().with_variant(JSONB(astext_type=Text()), "postgresql")


def utcnow() -> datetime:
    return datetime.utcnow()


class SourceUrlType(str, enum.Enum):
    ad = "ad"
    landing_page = "landing_page"
    product = "product"
    store = "store"
    collection = "collection"
    sitemap = "sitemap"


class PlatformGuess(str, enum.Enum):
    shopify = "shopify"
    woocommerce = "woocommerce"
    custom = "custom"
    unknown = "unknown"


class AdPlatform(str, enum.Enum):
    meta = "meta"
    tiktok = "tiktok"
    google = "google"
    manual = "manual"


class CreativeType(str, enum.Enum):
    image = "image"
    video = "video"
    carousel = "carousel"
    unknown = "unknown"


class TagEntityType(str, enum.Enum):
    ad = "ad"
    product = "product"
    store = "store"


class SignalEntityType(str, enum.Enum):
    ad = "ad"
    product = "product"
    store = "store"


class ScoreType(str, enum.Enum):
    winner = "winner"
    momentum = "momentum"
    longevity_proxy = "longevity_proxy"


class AlertRuleType(str, enum.Enum):
    price_drop = "price_drop"
    back_in_stock = "back_in_stock"
    new_variant = "new_variant"
    new_product_on_store = "new_product_on_store"
    score_spike = "score_spike"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=True, index=True)
    password_hash = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    workspaces = relationship("Workspace", back_populates="owner")


class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    owner = relationship("User", back_populates="workspaces")


class SourceUrl(Base):
    __tablename__ = "source_urls"

    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    url = Column(Text, nullable=False)
    type = Column(Enum(SourceUrlType), nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    last_fetched_at = Column(DateTime, nullable=True)
    fetch_status = Column(String(50), nullable=True)
    last_http_status = Column(Integer, nullable=True)

    __table_args__ = (UniqueConstraint("workspace_id", "url", name="uq_sourceurl_workspace_url"),)


class Store(Base):
    __tablename__ = "stores"

    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    domain = Column(String(255), nullable=False)
    platform_guess = Column(Enum(PlatformGuess), default=PlatformGuess.unknown, nullable=False)
    first_seen_at = Column(DateTime, default=utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=utcnow, nullable=False)

    products = relationship("Product", back_populates="store")
    traffic_snapshots = relationship("TrafficSnapshot", back_populates="store")

    __table_args__ = (
        UniqueConstraint("workspace_id", "domain", name="uq_store_workspace_domain"),
        Index("ix_store_domain", "domain"),
    )


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    canonical_url = Column(Text, nullable=False)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    currency = Column(String(10), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=utcnow, nullable=False)

    store = relationship("Store", back_populates="products")
    variants = relationship("ProductVariant", back_populates="product")

    __table_args__ = (
        UniqueConstraint("workspace_id", "canonical_url", name="uq_product_workspace_canonical_url"),
        Index("ix_product_title", "title"),
    )


class ProductVariant(Base):
    __tablename__ = "product_variants"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    sku = Column(String(255), nullable=True)
    title = Column(String(255), nullable=False)
    price = Column(Float, nullable=True)
    compare_at_price = Column(Float, nullable=True)
    available = Column(Boolean, default=True, nullable=False)
    last_seen_at = Column(DateTime, default=utcnow, nullable=False)

    product = relationship("Product", back_populates="variants")


class ProductSnapshot(Base):
    __tablename__ = "product_snapshots"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    fetched_at = Column(DateTime, default=utcnow, nullable=False)
    title = Column(Text, nullable=True)
    price_min = Column(Float, nullable=True)
    price_max = Column(Float, nullable=True)
    available = Column(Boolean, nullable=True)
    variant_count = Column(Integer, nullable=True)
    images_json = Column(JSON, nullable=True)
    raw_extracted_json = Column(JSON, nullable=True)
    content_hash = Column(String(64), nullable=False)

    __table_args__ = (
        Index("ix_product_snapshot_time", "product_id", "fetched_at"),
    )


class ProductEconomicsScenario(Base):
    """Immutable revision of user-entered test economics assumptions."""

    __tablename__ = "product_economics_scenarios"

    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    scenario_key = Column(String(64), nullable=False)
    revision = Column(Integer, nullable=False)
    supersedes_id = Column(Integer, ForeignKey("product_economics_scenarios.id", ondelete="SET NULL"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    name = Column(String(120), nullable=False)
    version = Column(String(64), nullable=False)
    input_source = Column(String(50), nullable=False)
    currency = Column(String(10), nullable=False)
    selling_price = Column(Numeric(18, 4), nullable=False)
    product_cost_low = Column(Numeric(18, 4), nullable=False)
    product_cost_high = Column(Numeric(18, 4), nullable=False)
    shipping_cost_low = Column(Numeric(18, 4), nullable=False)
    shipping_cost_high = Column(Numeric(18, 4), nullable=False)
    fulfillment_cost_low = Column(Numeric(18, 4), nullable=False)
    fulfillment_cost_high = Column(Numeric(18, 4), nullable=False)
    other_variable_cost_low = Column(Numeric(18, 4), nullable=False)
    other_variable_cost_high = Column(Numeric(18, 4), nullable=False)
    payment_fee_rate = Column(Numeric(9, 6), nullable=False)
    payment_fee_fixed = Column(Numeric(18, 4), nullable=False)
    refund_allowance_rate = Column(Numeric(9, 6), nullable=False)
    target_profit_margin = Column(Numeric(9, 6), nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("workspace_id", "scenario_key", "revision", name="uq_product_economics_revision"),
        CheckConstraint("revision >= 1", name="ck_product_economics_revision"),
        CheckConstraint("selling_price > 0", name="ck_product_economics_price"),
        CheckConstraint("product_cost_low >= 0 AND shipping_cost_low >= 0 AND fulfillment_cost_low >= 0 AND other_variable_cost_low >= 0", name="ck_product_economics_nonnegative_costs"),
        CheckConstraint("payment_fee_fixed >= 0", name="ck_product_economics_fixed_fee"),
        CheckConstraint("product_cost_low <= product_cost_high", name="ck_product_economics_product_cost"),
        CheckConstraint("shipping_cost_low <= shipping_cost_high", name="ck_product_economics_shipping_cost"),
        CheckConstraint("fulfillment_cost_low <= fulfillment_cost_high", name="ck_product_economics_fulfillment_cost"),
        CheckConstraint("other_variable_cost_low <= other_variable_cost_high", name="ck_product_economics_other_cost"),
        CheckConstraint("payment_fee_rate >= 0 AND payment_fee_rate <= 1", name="ck_product_economics_payment_rate"),
        CheckConstraint("refund_allowance_rate >= 0 AND refund_allowance_rate <= 1", name="ck_product_economics_refund_rate"),
        CheckConstraint("target_profit_margin >= 0 AND target_profit_margin < 1", name="ck_product_economics_target_margin"),
        Index("ix_product_economics_product_active", "product_id", "is_active"),
        Index("ix_product_economics_workspace_key", "workspace_id", "scenario_key"),
    )


class StoreSnapshot(Base):
    __tablename__ = "store_snapshots"

    id = Column(Integer, primary_key=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    fetched_at = Column(DateTime, default=utcnow, nullable=False)
    product_count = Column(Integer, nullable=True)
    collections_count = Column(Integer, nullable=True)
    raw_extracted_json = Column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_store_snapshot_time", "store_id", "fetched_at"),
    )


class TrafficSnapshot(Base):
    """A provider response captured as-is, including partial/unavailable results.

    Similarweb traffic is estimated provider data, not first-party analytics.
    Nullable metrics are intentional: a provider plan may grant one endpoint
    while withholding another, and Northstar never substitutes made-up values.
    """

    __tablename__ = "traffic_snapshots"

    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=True)
    domain = Column(String(255), nullable=False)
    provider = Column(String(50), default="similarweb", nullable=False)
    fetched_at = Column(DateTime, default=utcnow, nullable=False)
    period_start = Column(String(7), nullable=False)
    period_end = Column(String(7), nullable=False)
    country = Column(String(10), default="world", nullable=False)
    granularity = Column(String(20), default="monthly", nullable=False)
    main_domain_only = Column(Boolean, default=True, nullable=False)
    total_visits = Column(Float, nullable=True)
    global_rank = Column(Integer, nullable=True)
    visits_series_json = Column(JSON, nullable=True)
    global_rank_series_json = Column(JSON, nullable=True)
    metric_status_json = Column(JSON, nullable=True)
    fetch_status = Column(String(30), nullable=False)
    provider_last_updated = Column(String(30), nullable=True)

    store = relationship("Store", back_populates="traffic_snapshots")

    __table_args__ = (
        Index("ix_traffic_snapshot_store_time", "store_id", "fetched_at"),
        Index("ix_traffic_snapshot_domain_time", "workspace_id", "domain", "fetched_at"),
    )


class Ad(Base):
    __tablename__ = "ads"

    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    external_ad_id = Column(String(255), nullable=True)
    data_provider = Column(String(50), default="northstar_manual", nullable=False)
    source_type = Column(String(50), default="manual_import", nullable=False)
    provider_record_id = Column(String(255), nullable=True)
    source_url = Column(Text, nullable=True)
    provider_metadata_json = Column(JSON, nullable=True)
    platform = Column(Enum(AdPlatform), nullable=False)
    advertiser_name = Column(String(255), nullable=True)
    advertiser_id = Column(String(255), nullable=True)
    ad_text = Column(Text, nullable=True)
    headline = Column(Text, nullable=True)
    cta = Column(String(255), nullable=True)
    # Provider-reported dates are distinct from Northstar's own observation
    # timestamps below.  Keeping both prevents "first seen" from being
    # mistaken for an ad's actual delivery start.
    ad_creation_time = Column(DateTime, nullable=True)
    delivery_start_time = Column(DateTime, nullable=True)
    delivery_stop_time = Column(DateTime, nullable=True)
    first_seen_at = Column(DateTime, default=utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=utcnow, nullable=False)
    creative_type = Column(Enum(CreativeType), default=CreativeType.unknown, nullable=False)
    creative_urls_json = Column(JSON, nullable=True)
    ad_snapshot_url = Column(Text, nullable=True)
    publisher_platforms_json = Column(JSON, nullable=True)
    landing_url = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_ad_advertiser", "advertiser_name"),
        Index(
            "ix_ad_workspace_provider_record",
            "workspace_id",
            "data_provider",
            "provider_record_id",
            unique=True,
        ),
        Index("ix_ad_workspace_platform_external", "workspace_id", "platform", "external_ad_id"),
    )


class AdWatch(Base):
    """An explicitly enabled, repeatable public-ad collection target."""

    __tablename__ = "ad_watches"

    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    store_id = Column(Integer, ForeignKey("stores.id", ondelete="SET NULL"), nullable=True)
    name = Column(String(255), nullable=False)
    provider = Column(String(50), default="meta_ad_library", nullable=False)
    search_terms = Column(String(100), nullable=True)
    advertiser_id = Column(String(255), nullable=True)
    countries_json = Column(portable_json_type, nullable=False)
    interval_hours = Column(Integer, default=24, nullable=False)
    result_limit = Column(Integer, default=50, nullable=False)
    is_enabled = Column(Boolean, default=True, nullable=False)
    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True)
    last_status = Column(String(30), default="never_run", nullable=False)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, nullable=False)

    store = relationship("Store")

    __table_args__ = (
        CheckConstraint("interval_hours >= 1", name="ck_ad_watch_interval"),
        CheckConstraint("result_limit >= 1 AND result_limit <= 500", name="ck_ad_watch_limit"),
        Index("ix_ad_watch_workspace_due", "workspace_id", "is_enabled", "next_run_at"),
    )


class AdCollectionRun(Base):
    """Durable audit record for one provider request made by a watch."""

    __tablename__ = "ad_collection_runs"

    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    watch_id = Column(Integer, ForeignKey("ad_watches.id", ondelete="CASCADE"), nullable=False)
    provider = Column(String(50), nullable=False)
    trigger = Column(String(30), nullable=False)
    status = Column(String(30), nullable=False)
    started_at = Column(DateTime, default=utcnow, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    fetched_count = Column(Integer, default=0, nullable=False)
    inserted_count = Column(Integer, default=0, nullable=False)
    updated_count = Column(Integer, default=0, nullable=False)
    recurring_count = Column(Integer, default=0, nullable=False)
    error_code = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)

    watch = relationship("AdWatch")

    __table_args__ = (
        Index("ix_ad_collection_run_watch_time", "watch_id", "started_at"),
        Index("ix_ad_collection_run_workspace_status", "workspace_id", "status"),
    )


class AdWatchObservation(Base):
    """Recurrence and retention state for an ad observed by a watch."""

    __tablename__ = "ad_watch_observations"

    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    watch_id = Column(Integer, ForeignKey("ad_watches.id", ondelete="CASCADE"), nullable=False)
    ad_id = Column(Integer, ForeignKey("ads.id", ondelete="CASCADE"), nullable=False)
    first_seen_at = Column(DateTime, default=utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=utcnow, nullable=False)
    observation_count = Column(Integer, default=1, nullable=False)
    consecutive_misses = Column(Integer, default=0, nullable=False)
    current_status = Column(String(30), default="observed", nullable=False)
    retention_tier = Column(String(30), default="metadata", nullable=False)
    retention_reason = Column(Text, nullable=True)

    watch = relationship("AdWatch")
    ad = relationship("Ad")

    __table_args__ = (
        UniqueConstraint("watch_id", "ad_id", name="uq_ad_watch_observation"),
        Index("ix_ad_watch_observation_watch_status", "watch_id", "current_status"),
        Index("ix_ad_watch_observation_ad", "ad_id"),
    )


class AdMetricObservation(Base):
    """A source-scoped ad metric; exact values, ranges and percentiles stay distinct."""

    __tablename__ = "ad_metric_observations"

    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    ad_id = Column(Integer, ForeignKey("ads.id", ondelete="CASCADE"), nullable=False)
    observation_key = Column(String(64), nullable=False)
    metric_key = Column(String(100), nullable=False)
    value_kind = Column(String(30), nullable=False)
    value_numeric = Column(Numeric(24, 6), nullable=True)
    range_low = Column(Numeric(24, 6), nullable=True)
    range_high = Column(Numeric(24, 6), nullable=True)
    value_text = Column(Text, nullable=True)
    unit = Column(String(50), nullable=True)
    provider = Column(String(100), nullable=False)
    source_type = Column(String(100), nullable=False)
    source_url = Column(Text, nullable=True)
    geography = Column(String(100), nullable=True)
    period_start = Column(Date, nullable=True)
    period_end = Column(Date, nullable=True)
    confidence_score = Column(Numeric(5, 4), nullable=True)
    observed_at = Column(DateTime, default=utcnow, nullable=False)
    retrieved_at = Column(DateTime, default=utcnow, nullable=False)
    metadata_json = Column(portable_json_type, nullable=True)

    ad = relationship("Ad")

    __table_args__ = (
        UniqueConstraint("workspace_id", "observation_key", name="uq_ad_metric_observation_key"),
        CheckConstraint(
            "range_low IS NULL OR range_high IS NULL OR range_low <= range_high",
            name="ck_ad_metric_range",
        ),
        CheckConstraint(
            "period_start IS NULL OR period_end IS NULL OR period_start <= period_end",
            name="ck_ad_metric_period",
        ),
        CheckConstraint(
            "confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)",
            name="ck_ad_metric_confidence",
        ),
        Index("ix_ad_metric_ad_key_time", "ad_id", "metric_key", "observed_at"),
        Index("ix_ad_metric_workspace_provider", "workspace_id", "provider"),
    )


class LandingPageSnapshot(Base):
    __tablename__ = "landing_page_snapshots"

    id = Column(Integer, primary_key=True)
    url_id = Column(Integer, ForeignKey("source_urls.id"), nullable=False)
    fetched_at = Column(DateTime, default=utcnow, nullable=False)
    final_url = Column(Text, nullable=True)
    html_hash = Column(String(64), nullable=False)
    extracted_product_urls_json = Column(JSON, nullable=True)


class AdLandingEdge(Base):
    __tablename__ = "ad_landing_edges"

    id = Column(Integer, primary_key=True)
    ad_id = Column(Integer, ForeignKey("ads.id"), nullable=False)
    url_id = Column(Integer, ForeignKey("source_urls.id"), nullable=False)


class LandingProductEdge(Base):
    __tablename__ = "landing_product_edges"

    id = Column(Integer, primary_key=True)
    landing_url_id = Column(Integer, ForeignKey("source_urls.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    name = Column(String(100), nullable=False)

    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_tag_workspace_name"),)


class TagAssignment(Base):
    __tablename__ = "tag_assignments"

    id = Column(Integer, primary_key=True)
    entity_type = Column(Enum(TagEntityType), nullable=False)
    entity_id = Column(Integer, nullable=False)
    tag_id = Column(Integer, ForeignKey("tags.id"), nullable=False)


class Signal(Base):
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True)
    entity_type = Column(Enum(SignalEntityType), nullable=False)
    entity_id = Column(Integer, nullable=False)
    signal_type = Column(String(100), nullable=False)
    value_json = Column(JSON, nullable=True)
    computed_at = Column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        Index("ix_signal_entity", "entity_type", "entity_id"),
    )


class Score(Base):
    __tablename__ = "scores"

    id = Column(Integer, primary_key=True)
    entity_type = Column(Enum(SignalEntityType), nullable=False)
    entity_id = Column(Integer, nullable=False)
    score_type = Column(Enum(ScoreType), nullable=False)
    score_value = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False)
    components_json = Column(JSON, nullable=True)
    computed_at = Column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        Index("ix_score_entity", "entity_type", "entity_id"),
    )


class AlertRule(Base):
    __tablename__ = "alert_rules"

    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    entity_type = Column(Enum(SignalEntityType), nullable=False)
    entity_id = Column(Integer, nullable=False)
    rule_type = Column(Enum(AlertRuleType), nullable=False)
    threshold_json = Column(JSON, nullable=True)
    is_enabled = Column(Boolean, default=True, nullable=False)


class AlertEvent(Base):
    __tablename__ = "alert_events"

    id = Column(Integer, primary_key=True)
    alert_rule_id = Column(Integer, ForeignKey("alert_rules.id"), nullable=False)
    fired_at = Column(DateTime, default=utcnow, nullable=False)
    message = Column(Text, nullable=False)
    payload_json = Column(JSON, nullable=True)
    is_read = Column(Boolean, default=False, nullable=False)


class StoreProfile(Base):
    """Latest normalized public profile for a store.

    Source-specific and historical material remains in snapshots/evidence.  This
    table is deliberately a compact current profile used to identify a store in
    reports, not a place for derived sales claims.
    """

    __tablename__ = "store_profiles"

    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    brand_name = Column(String(255), nullable=True)
    primary_category = Column(String(100), nullable=True)
    primary_country = Column(String(2), nullable=True)
    homepage_url = Column(Text, nullable=True)
    logo_url = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    currency = Column(String(10), nullable=True)
    language = Column(String(20), nullable=True)
    attributes_json = Column(portable_json_type, nullable=True)
    profile_version = Column(String(64), default="store-profile-v1", nullable=False)
    first_observed_at = Column(DateTime, default=utcnow, nullable=False)
    last_observed_at = Column(DateTime, default=utcnow, nullable=False)

    store = relationship("Store")

    __table_args__ = (
        UniqueConstraint("store_id", name="uq_store_profile_store"),
        Index("ix_store_profile_workspace", "workspace_id"),
    )


class StoreIdentity(Base):
    """A candidate or confirmed public identity associated with a store."""

    __tablename__ = "store_identities"

    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    identity_type = Column(String(50), nullable=False)
    display_value = Column(Text, nullable=False)
    normalized_value = Column(String(500), nullable=False)
    source_type = Column(String(100), nullable=False)
    source_url = Column(Text, nullable=True)
    confidence_score = Column(Numeric(5, 4), nullable=False)
    is_confirmed = Column(Boolean, default=False, nullable=False)
    evidence_json = Column(portable_json_type, nullable=True)
    first_seen_at = Column(DateTime, default=utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=utcnow, nullable=False)
    confirmed_at = Column(DateTime, nullable=True)

    store = relationship("Store")

    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "store_id",
            "identity_type",
            "normalized_value",
            name="uq_store_identity_value",
        ),
        CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 1",
            name="ck_store_identity_confidence",
        ),
        Index("ix_store_identity_store_type", "store_id", "identity_type"),
        Index("ix_store_identity_lookup", "identity_type", "normalized_value"),
    )


class EstimationProfile(Base):
    """Versioned, user-adjustable assumptions for one commerce category."""

    __tablename__ = "estimation_profiles"

    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    name = Column(String(100), nullable=False)
    category_key = Column(String(100), default="general_ecommerce", nullable=False)
    version = Column(String(64), default="estimation-profile-v1", nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)
    conversion_rate_low = Column(Numeric(9, 6), nullable=False)
    conversion_rate_central = Column(Numeric(9, 6), nullable=True)
    conversion_rate_high = Column(Numeric(9, 6), nullable=False)
    basket_multiplier_low = Column(Numeric(9, 4), nullable=False)
    basket_multiplier_central = Column(Numeric(9, 4), nullable=True)
    basket_multiplier_high = Column(Numeric(9, 4), nullable=False)
    traffic_reliability_low = Column(Numeric(9, 4), nullable=False)
    traffic_reliability_central = Column(Numeric(9, 4), nullable=True)
    traffic_reliability_high = Column(Numeric(9, 4), nullable=False)
    minimum_evidence_count = Column(Integer, default=2, nullable=False)
    freshness_limit_days = Column(Integer, default=90, nullable=False)
    score_weights_json = Column(portable_json_type, nullable=True)
    thresholds_json = Column(portable_json_type, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "name",
            "category_key",
            "version",
            name="uq_estimation_profile_version",
        ),
        CheckConstraint(
            "conversion_rate_low >= 0 AND conversion_rate_high <= 1 "
            "AND conversion_rate_low <= conversion_rate_high",
            name="ck_estimation_profile_conversion_bounds",
        ),
        CheckConstraint(
            "conversion_rate_central IS NULL OR "
            "(conversion_rate_central >= conversion_rate_low "
            "AND conversion_rate_central <= conversion_rate_high)",
            name="ck_estimation_profile_conversion_central",
        ),
        CheckConstraint(
            "basket_multiplier_low >= 0 "
            "AND basket_multiplier_low <= basket_multiplier_high",
            name="ck_estimation_profile_basket_bounds",
        ),
        CheckConstraint(
            "basket_multiplier_central IS NULL OR "
            "(basket_multiplier_central >= basket_multiplier_low "
            "AND basket_multiplier_central <= basket_multiplier_high)",
            name="ck_estimation_profile_basket_central",
        ),
        CheckConstraint(
            "traffic_reliability_low >= 0 "
            "AND traffic_reliability_low <= traffic_reliability_high",
            name="ck_estimation_profile_traffic_bounds",
        ),
        CheckConstraint(
            "traffic_reliability_central IS NULL OR "
            "(traffic_reliability_central >= traffic_reliability_low "
            "AND traffic_reliability_central <= traffic_reliability_high)",
            name="ck_estimation_profile_traffic_central",
        ),
        CheckConstraint(
            "minimum_evidence_count >= 1",
            name="ck_estimation_profile_min_evidence",
        ),
        CheckConstraint(
            "freshness_limit_days >= 1",
            name="ck_estimation_profile_freshness",
        ),
        Index("ix_estimation_profile_workspace_default", "workspace_id", "is_default"),
    )


class AnalysisRun(Base):
    """Immutable execution envelope for one versioned store analysis."""

    __tablename__ = "analysis_runs"

    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    estimation_profile_id = Column(
        Integer,
        ForeignKey("estimation_profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    status = Column(String(30), nullable=False)
    analysis_version = Column(String(64), nullable=False)
    input_fingerprint = Column(String(64), nullable=False)
    warnings_json = Column(portable_json_type, nullable=True)
    errors_json = Column(portable_json_type, nullable=True)
    started_at = Column(DateTime, default=utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    store = relationship("Store")
    estimation_profile = relationship("EstimationProfile")

    __table_args__ = (
        Index("ix_analysis_run_store_time", "store_id", "created_at"),
        Index("ix_analysis_run_workspace_status", "workspace_id", "status"),
        Index(
            "ix_analysis_run_input",
            "workspace_id",
            "store_id",
            "analysis_version",
            "input_fingerprint",
        ),
    )


class TrafficObservation(Base):
    """One normalized provider metric for a period and optional dimension."""

    __tablename__ = "traffic_observations"

    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=True)
    traffic_snapshot_id = Column(Integer, ForeignKey("traffic_snapshots.id"), nullable=True)
    observation_key = Column(String(64), nullable=False)
    domain = Column(String(255), nullable=False)
    provider = Column(String(50), nullable=False)
    metric_key = Column(String(100), nullable=False)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    country = Column(String(10), default="world", nullable=False)
    dimension_type = Column(String(50), default="", nullable=False)
    dimension_value = Column(String(255), default="", nullable=False)
    value_numeric = Column(Numeric(24, 6), nullable=True)
    value_text = Column(Text, nullable=True)
    unit = Column(String(50), nullable=True)
    data_kind = Column(String(30), default="estimated", nullable=False)
    status = Column(String(30), nullable=False)
    confidence_score = Column(Numeric(5, 4), nullable=True)
    observed_at = Column(DateTime, nullable=True)
    retrieved_at = Column(DateTime, default=utcnow, nullable=False)
    provider_last_updated_at = Column(DateTime, nullable=True)
    source_payload_json = Column(portable_json_type, nullable=True)

    store = relationship("Store")
    traffic_snapshot = relationship("TrafficSnapshot")

    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "observation_key",
            name="uq_traffic_observation_key",
        ),
        CheckConstraint(
            "period_end >= period_start",
            name="ck_traffic_observation_period",
        ),
        CheckConstraint(
            "confidence_score IS NULL OR "
            "(confidence_score >= 0 AND confidence_score <= 1)",
            name="ck_traffic_observation_confidence",
        ),
        Index(
            "ix_traffic_observation_store_metric_period",
            "store_id",
            "metric_key",
            "period_start",
        ),
        Index(
            "ix_traffic_observation_domain_metric_period",
            "workspace_id",
            "domain",
            "metric_key",
            "period_start",
        ),
    )


class DerivedInsight(Base):
    """A versioned estimate, score, range, or classification from an analysis."""

    __tablename__ = "derived_insights"

    id = Column(Integer, primary_key=True)
    analysis_run_id = Column(
        Integer,
        ForeignKey("analysis_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    subject_key = Column(String(300), nullable=False)
    metric_key = Column(String(100), nullable=False)
    value_kind = Column(String(30), nullable=False)
    estimate_low = Column(Numeric(24, 6), nullable=True)
    estimate_central = Column(Numeric(24, 6), nullable=True)
    estimate_high = Column(Numeric(24, 6), nullable=True)
    value_text = Column(Text, nullable=True)
    value_json = Column(portable_json_type, nullable=True)
    unit = Column(String(50), nullable=True)
    currency = Column(String(10), nullable=True)
    confidence_score = Column(Numeric(5, 4), nullable=False)
    confidence_label = Column(String(30), nullable=False)
    estimator_version = Column(String(64), nullable=False)
    assumptions_json = Column(portable_json_type, nullable=True)
    missing_signals_json = Column(portable_json_type, nullable=True)
    calculated_at = Column(DateTime, default=utcnow, nullable=False)

    analysis_run = relationship("AnalysisRun")
    store = relationship("Store")
    product = relationship("Product")

    __table_args__ = (
        UniqueConstraint(
            "analysis_run_id",
            "subject_key",
            "metric_key",
            name="uq_derived_insight_metric",
        ),
        CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 1",
            name="ck_derived_insight_confidence",
        ),
        CheckConstraint(
            "estimate_low IS NULL OR estimate_high IS NULL "
            "OR estimate_low <= estimate_high",
            name="ck_derived_insight_range",
        ),
        CheckConstraint(
            "estimate_central IS NULL OR "
            "((estimate_low IS NULL OR estimate_central >= estimate_low) "
            "AND (estimate_high IS NULL OR estimate_central <= estimate_high))",
            name="ck_derived_insight_central",
        ),
        Index("ix_derived_insight_store_metric", "store_id", "metric_key"),
        Index("ix_derived_insight_product_metric", "product_id", "metric_key"),
    )


class EvidenceRecord(Base):
    """Normalized evidence with typed links back to collected source records."""

    __tablename__ = "evidence_records"

    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    ad_id = Column(Integer, ForeignKey("ads.id", ondelete="SET NULL"), nullable=True)
    source_url_id = Column(
        Integer,
        ForeignKey("source_urls.id", ondelete="SET NULL"),
        nullable=True,
    )
    product_snapshot_id = Column(
        Integer,
        ForeignKey("product_snapshots.id", ondelete="SET NULL"),
        nullable=True,
    )
    traffic_snapshot_id = Column(
        Integer,
        ForeignKey("traffic_snapshots.id", ondelete="SET NULL"),
        nullable=True,
    )
    traffic_observation_id = Column(
        Integer,
        ForeignKey("traffic_observations.id", ondelete="SET NULL"),
        nullable=True,
    )
    evidence_key = Column(String(64), nullable=False)
    evidence_type = Column(String(100), nullable=False)
    independence_group = Column(String(100), nullable=False)
    details = Column(Text, nullable=True)
    source_type = Column(String(100), nullable=False)
    source_name = Column(String(100), nullable=True)
    source_url = Column(Text, nullable=True)
    value_numeric = Column(Numeric(24, 6), nullable=True)
    value_text = Column(Text, nullable=True)
    value_json = Column(portable_json_type, nullable=True)
    unit = Column(String(50), nullable=True)
    currency = Column(String(10), nullable=True)
    confidence_score = Column(Numeric(5, 4), nullable=True)
    is_contradictory = Column(Boolean, default=False, nullable=False)
    observed_at = Column(DateTime, nullable=True)
    retrieved_at = Column(DateTime, default=utcnow, nullable=False)
    freshness_expires_at = Column(DateTime, nullable=True)
    collector_version = Column(String(64), nullable=False)

    store = relationship("Store")
    product = relationship("Product")
    ad = relationship("Ad")
    source_url_record = relationship("SourceUrl")
    product_snapshot = relationship("ProductSnapshot")
    traffic_snapshot = relationship("TrafficSnapshot")
    traffic_observation = relationship("TrafficObservation")

    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "evidence_key",
            name="uq_evidence_record_key",
        ),
        CheckConstraint(
            "confidence_score IS NULL OR "
            "(confidence_score >= 0 AND confidence_score <= 1)",
            name="ck_evidence_record_confidence",
        ),
        Index(
            "ix_evidence_record_store_type_time",
            "store_id",
            "evidence_type",
            "observed_at",
        ),
        Index(
            "ix_evidence_record_product_type",
            "product_id",
            "evidence_type",
        ),
    )


class InsightEvidence(Base):
    """Many-to-many attribution from an insight to its supporting evidence."""

    __tablename__ = "insight_evidence"

    id = Column(Integer, primary_key=True)
    insight_id = Column(
        Integer,
        ForeignKey("derived_insights.id", ondelete="CASCADE"),
        nullable=False,
    )
    evidence_id = Column(
        Integer,
        ForeignKey("evidence_records.id", ondelete="CASCADE"),
        nullable=False,
    )
    role = Column(String(30), default="supporting", nullable=False)
    weight = Column(Numeric(9, 6), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    insight = relationship("DerivedInsight")
    evidence = relationship("EvidenceRecord")

    __table_args__ = (
        UniqueConstraint("insight_id", "evidence_id", name="uq_insight_evidence_pair"),
        Index("ix_insight_evidence_evidence", "evidence_id"),
    )


class InvestigationItem(Base):
    """A decision-focused shortlist entry linked to a store, product, or ad."""

    __tablename__ = "investigation_items"

    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    entity_type = Column(String(30), nullable=False)
    entity_id = Column(Integer, nullable=False)
    workflow_stage = Column(String(30), default="inbox", nullable=False)
    decision = Column(String(30), default="undecided", nullable=False)
    priority = Column(String(20), default="medium", nullable=False)
    thesis = Column(Text, nullable=True)
    risks = Column(Text, nullable=True)
    next_action = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, nullable=False)

    evidence_links = relationship("InvestigationEvidenceLink", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("workspace_id", "entity_type", "entity_id", name="uq_investigation_entity"),
        CheckConstraint("entity_type IN ('store', 'product', 'ad')", name="ck_investigation_entity_type"),
        CheckConstraint("workflow_stage IN ('inbox', 'researching', 'ready_to_test', 'testing', 'decided', 'archived')", name="ck_investigation_stage"),
        CheckConstraint("decision IN ('undecided', 'investigate', 'test', 'reject')", name="ck_investigation_decision"),
        CheckConstraint("priority IN ('low', 'medium', 'high')", name="ck_investigation_priority"),
        Index("ix_investigation_workspace_stage", "workspace_id", "workflow_stage"),
        Index("ix_investigation_workspace_priority", "workspace_id", "priority"),
    )


class InvestigationEvidenceLink(Base):
    __tablename__ = "investigation_evidence_links"

    id = Column(Integer, primary_key=True)
    investigation_id = Column(Integer, ForeignKey("investigation_items.id", ondelete="CASCADE"), nullable=False)
    evidence_id = Column(Integer, ForeignKey("evidence_records.id", ondelete="CASCADE"), nullable=False)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    evidence = relationship("EvidenceRecord")

    __table_args__ = (
        UniqueConstraint("investigation_id", "evidence_id", name="uq_investigation_evidence"),
        Index("ix_investigation_evidence_evidence", "evidence_id"),
    )
