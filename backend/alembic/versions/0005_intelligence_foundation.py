"""add normalized intelligence and evidence foundation

Revision ID: 0005_intelligence_foundation
Revises: 0004_add_meta_ad_details
Create Date: 2026-07-10 22:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0005_intelligence_foundation"
down_revision = "0004_add_meta_ad_details"
branch_labels = None
depends_on = None


json_type = sa.JSON().with_variant(
    postgresql.JSONB(astext_type=sa.Text()),
    "postgresql",
)


def upgrade() -> None:
    op.create_table(
        "store_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("store_id", sa.Integer(), sa.ForeignKey("stores.id"), nullable=False),
        sa.Column("brand_name", sa.String(length=255), nullable=True),
        sa.Column("primary_category", sa.String(length=100), nullable=True),
        sa.Column("primary_country", sa.String(length=2), nullable=True),
        sa.Column("homepage_url", sa.Text(), nullable=True),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=True),
        sa.Column("language", sa.String(length=20), nullable=True),
        sa.Column("attributes_json", json_type, nullable=True),
        sa.Column("profile_version", sa.String(length=64), nullable=False),
        sa.Column("first_observed_at", sa.DateTime(), nullable=False),
        sa.Column("last_observed_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("store_id", name="uq_store_profile_store"),
    )
    op.create_index("ix_store_profile_workspace", "store_profiles", ["workspace_id"])

    op.create_table(
        "store_identities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("store_id", sa.Integer(), sa.ForeignKey("stores.id"), nullable=False),
        sa.Column("identity_type", sa.String(length=50), nullable=False),
        sa.Column("display_value", sa.Text(), nullable=False),
        sa.Column("normalized_value", sa.String(length=500), nullable=False),
        sa.Column("source_type", sa.String(length=100), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("confidence_score", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("is_confirmed", sa.Boolean(), nullable=False),
        sa.Column("evidence_json", json_type, nullable=True),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 1",
            name="ck_store_identity_confidence",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "store_id",
            "identity_type",
            "normalized_value",
            name="uq_store_identity_value",
        ),
    )
    op.create_index(
        "ix_store_identity_store_type",
        "store_identities",
        ["store_id", "identity_type"],
    )
    op.create_index(
        "ix_store_identity_lookup",
        "store_identities",
        ["identity_type", "normalized_value"],
    )

    op.create_table(
        "estimation_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("category_key", sa.String(length=100), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("conversion_rate_low", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column("conversion_rate_central", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("conversion_rate_high", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column("basket_multiplier_low", sa.Numeric(precision=9, scale=4), nullable=False),
        sa.Column("basket_multiplier_central", sa.Numeric(precision=9, scale=4), nullable=True),
        sa.Column("basket_multiplier_high", sa.Numeric(precision=9, scale=4), nullable=False),
        sa.Column("traffic_reliability_low", sa.Numeric(precision=9, scale=4), nullable=False),
        sa.Column("traffic_reliability_central", sa.Numeric(precision=9, scale=4), nullable=True),
        sa.Column("traffic_reliability_high", sa.Numeric(precision=9, scale=4), nullable=False),
        sa.Column("minimum_evidence_count", sa.Integer(), nullable=False),
        sa.Column("freshness_limit_days", sa.Integer(), nullable=False),
        sa.Column("score_weights_json", json_type, nullable=True),
        sa.Column("thresholds_json", json_type, nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "conversion_rate_low >= 0 AND conversion_rate_high <= 1 "
            "AND conversion_rate_low <= conversion_rate_high",
            name="ck_estimation_profile_conversion_bounds",
        ),
        sa.CheckConstraint(
            "conversion_rate_central IS NULL OR "
            "(conversion_rate_central >= conversion_rate_low "
            "AND conversion_rate_central <= conversion_rate_high)",
            name="ck_estimation_profile_conversion_central",
        ),
        sa.CheckConstraint(
            "basket_multiplier_low >= 0 "
            "AND basket_multiplier_low <= basket_multiplier_high",
            name="ck_estimation_profile_basket_bounds",
        ),
        sa.CheckConstraint(
            "basket_multiplier_central IS NULL OR "
            "(basket_multiplier_central >= basket_multiplier_low "
            "AND basket_multiplier_central <= basket_multiplier_high)",
            name="ck_estimation_profile_basket_central",
        ),
        sa.CheckConstraint(
            "traffic_reliability_low >= 0 "
            "AND traffic_reliability_low <= traffic_reliability_high",
            name="ck_estimation_profile_traffic_bounds",
        ),
        sa.CheckConstraint(
            "traffic_reliability_central IS NULL OR "
            "(traffic_reliability_central >= traffic_reliability_low "
            "AND traffic_reliability_central <= traffic_reliability_high)",
            name="ck_estimation_profile_traffic_central",
        ),
        sa.CheckConstraint(
            "minimum_evidence_count >= 1",
            name="ck_estimation_profile_min_evidence",
        ),
        sa.CheckConstraint(
            "freshness_limit_days >= 1",
            name="ck_estimation_profile_freshness",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "name",
            "category_key",
            "version",
            name="uq_estimation_profile_version",
        ),
    )
    op.create_index(
        "ix_estimation_profile_workspace_default",
        "estimation_profiles",
        ["workspace_id", "is_default"],
    )

    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("store_id", sa.Integer(), sa.ForeignKey("stores.id"), nullable=False),
        sa.Column(
            "estimation_profile_id",
            sa.Integer(),
            sa.ForeignKey("estimation_profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("analysis_version", sa.String(length=64), nullable=False),
        sa.Column("input_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("warnings_json", json_type, nullable=True),
        sa.Column("errors_json", json_type, nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_analysis_run_store_time",
        "analysis_runs",
        ["store_id", "created_at"],
    )
    op.create_index(
        "ix_analysis_run_workspace_status",
        "analysis_runs",
        ["workspace_id", "status"],
    )
    op.create_index(
        "ix_analysis_run_input",
        "analysis_runs",
        ["workspace_id", "store_id", "analysis_version", "input_fingerprint"],
    )

    op.create_table(
        "traffic_observations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("store_id", sa.Integer(), sa.ForeignKey("stores.id"), nullable=True),
        sa.Column(
            "traffic_snapshot_id",
            sa.Integer(),
            sa.ForeignKey("traffic_snapshots.id"),
            nullable=True,
        ),
        sa.Column("observation_key", sa.String(length=64), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("metric_key", sa.String(length=100), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("country", sa.String(length=10), nullable=False),
        sa.Column("dimension_type", sa.String(length=50), nullable=False),
        sa.Column("dimension_value", sa.String(length=255), nullable=False),
        sa.Column("value_numeric", sa.Numeric(precision=24, scale=6), nullable=True),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("unit", sa.String(length=50), nullable=True),
        sa.Column("data_kind", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("confidence_score", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("observed_at", sa.DateTime(), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(), nullable=False),
        sa.Column("provider_last_updated_at", sa.DateTime(), nullable=True),
        sa.Column("source_payload_json", json_type, nullable=True),
        sa.CheckConstraint(
            "period_end >= period_start",
            name="ck_traffic_observation_period",
        ),
        sa.CheckConstraint(
            "confidence_score IS NULL OR "
            "(confidence_score >= 0 AND confidence_score <= 1)",
            name="ck_traffic_observation_confidence",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "observation_key",
            name="uq_traffic_observation_key",
        ),
    )
    op.create_index(
        "ix_traffic_observation_store_metric_period",
        "traffic_observations",
        ["store_id", "metric_key", "period_start"],
    )
    op.create_index(
        "ix_traffic_observation_domain_metric_period",
        "traffic_observations",
        ["workspace_id", "domain", "metric_key", "period_start"],
    )

    op.create_table(
        "derived_insights",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "analysis_run_id",
            sa.Integer(),
            sa.ForeignKey("analysis_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("store_id", sa.Integer(), sa.ForeignKey("stores.id"), nullable=False),
        sa.Column(
            "product_id",
            sa.Integer(),
            sa.ForeignKey("products.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("subject_key", sa.String(length=300), nullable=False),
        sa.Column("metric_key", sa.String(length=100), nullable=False),
        sa.Column("value_kind", sa.String(length=30), nullable=False),
        sa.Column("estimate_low", sa.Numeric(precision=24, scale=6), nullable=True),
        sa.Column("estimate_central", sa.Numeric(precision=24, scale=6), nullable=True),
        sa.Column("estimate_high", sa.Numeric(precision=24, scale=6), nullable=True),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("value_json", json_type, nullable=True),
        sa.Column("unit", sa.String(length=50), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=True),
        sa.Column("confidence_score", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("confidence_label", sa.String(length=30), nullable=False),
        sa.Column("estimator_version", sa.String(length=64), nullable=False),
        sa.Column("assumptions_json", json_type, nullable=True),
        sa.Column("missing_signals_json", json_type, nullable=True),
        sa.Column("calculated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 1",
            name="ck_derived_insight_confidence",
        ),
        sa.CheckConstraint(
            "estimate_low IS NULL OR estimate_high IS NULL "
            "OR estimate_low <= estimate_high",
            name="ck_derived_insight_range",
        ),
        sa.CheckConstraint(
            "estimate_central IS NULL OR "
            "((estimate_low IS NULL OR estimate_central >= estimate_low) "
            "AND (estimate_high IS NULL OR estimate_central <= estimate_high))",
            name="ck_derived_insight_central",
        ),
        sa.UniqueConstraint(
            "analysis_run_id",
            "subject_key",
            "metric_key",
            name="uq_derived_insight_metric",
        ),
    )
    op.create_index(
        "ix_derived_insight_store_metric",
        "derived_insights",
        ["store_id", "metric_key"],
    )
    op.create_index(
        "ix_derived_insight_product_metric",
        "derived_insights",
        ["product_id", "metric_key"],
    )

    op.create_table(
        "evidence_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("store_id", sa.Integer(), sa.ForeignKey("stores.id"), nullable=False),
        sa.Column(
            "product_id",
            sa.Integer(),
            sa.ForeignKey("products.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "ad_id",
            sa.Integer(),
            sa.ForeignKey("ads.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "source_url_id",
            sa.Integer(),
            sa.ForeignKey("source_urls.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "product_snapshot_id",
            sa.Integer(),
            sa.ForeignKey("product_snapshots.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "traffic_snapshot_id",
            sa.Integer(),
            sa.ForeignKey("traffic_snapshots.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "traffic_observation_id",
            sa.Integer(),
            sa.ForeignKey("traffic_observations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("evidence_key", sa.String(length=64), nullable=False),
        sa.Column("evidence_type", sa.String(length=100), nullable=False),
        sa.Column("independence_group", sa.String(length=100), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(length=100), nullable=False),
        sa.Column("source_name", sa.String(length=100), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("value_numeric", sa.Numeric(precision=24, scale=6), nullable=True),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("value_json", json_type, nullable=True),
        sa.Column("unit", sa.String(length=50), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=True),
        sa.Column("confidence_score", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("is_contradictory", sa.Boolean(), nullable=False),
        sa.Column("observed_at", sa.DateTime(), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(), nullable=False),
        sa.Column("freshness_expires_at", sa.DateTime(), nullable=True),
        sa.Column("collector_version", sa.String(length=64), nullable=False),
        sa.CheckConstraint(
            "confidence_score IS NULL OR "
            "(confidence_score >= 0 AND confidence_score <= 1)",
            name="ck_evidence_record_confidence",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "evidence_key",
            name="uq_evidence_record_key",
        ),
    )
    op.create_index(
        "ix_evidence_record_store_type_time",
        "evidence_records",
        ["store_id", "evidence_type", "observed_at"],
    )
    op.create_index(
        "ix_evidence_record_product_type",
        "evidence_records",
        ["product_id", "evidence_type"],
    )

    op.create_table(
        "insight_evidence",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "insight_id",
            sa.Integer(),
            sa.ForeignKey("derived_insights.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "evidence_id",
            sa.Integer(),
            sa.ForeignKey("evidence_records.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=30), nullable=False),
        sa.Column("weight", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "insight_id",
            "evidence_id",
            name="uq_insight_evidence_pair",
        ),
    )
    op.create_index(
        "ix_insight_evidence_evidence",
        "insight_evidence",
        ["evidence_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_insight_evidence_evidence", table_name="insight_evidence")
    op.drop_table("insight_evidence")

    op.drop_index("ix_evidence_record_product_type", table_name="evidence_records")
    op.drop_index("ix_evidence_record_store_type_time", table_name="evidence_records")
    op.drop_table("evidence_records")

    op.drop_index("ix_derived_insight_product_metric", table_name="derived_insights")
    op.drop_index("ix_derived_insight_store_metric", table_name="derived_insights")
    op.drop_table("derived_insights")

    op.drop_index(
        "ix_traffic_observation_domain_metric_period",
        table_name="traffic_observations",
    )
    op.drop_index(
        "ix_traffic_observation_store_metric_period",
        table_name="traffic_observations",
    )
    op.drop_table("traffic_observations")

    op.drop_index("ix_analysis_run_input", table_name="analysis_runs")
    op.drop_index("ix_analysis_run_workspace_status", table_name="analysis_runs")
    op.drop_index("ix_analysis_run_store_time", table_name="analysis_runs")
    op.drop_table("analysis_runs")

    op.drop_index(
        "ix_estimation_profile_workspace_default",
        table_name="estimation_profiles",
    )
    op.drop_table("estimation_profiles")

    op.drop_index("ix_store_identity_lookup", table_name="store_identities")
    op.drop_index("ix_store_identity_store_type", table_name="store_identities")
    op.drop_table("store_identities")

    op.drop_index("ix_store_profile_workspace", table_name="store_profiles")
    op.drop_table("store_profiles")
