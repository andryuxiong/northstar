"""add source-scoped ad metric observations

Revision ID: 0007_ad_metric_observations
Revises: 0006_ad_provenance
Create Date: 2026-07-11 17:30:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0007_ad_metric_observations"
down_revision = "0006_ad_provenance"
branch_labels = None
depends_on = None


json_type = sa.JSON().with_variant(
    postgresql.JSONB(astext_type=sa.Text()),
    "postgresql",
)


def upgrade() -> None:
    op.create_table(
        "ad_metric_observations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("ad_id", sa.Integer(), sa.ForeignKey("ads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("observation_key", sa.String(length=64), nullable=False),
        sa.Column("metric_key", sa.String(length=100), nullable=False),
        sa.Column("value_kind", sa.String(length=30), nullable=False),
        sa.Column("value_numeric", sa.Numeric(precision=24, scale=6), nullable=True),
        sa.Column("range_low", sa.Numeric(precision=24, scale=6), nullable=True),
        sa.Column("range_high", sa.Numeric(precision=24, scale=6), nullable=True),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("unit", sa.String(length=50), nullable=True),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("source_type", sa.String(length=100), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("geography", sa.String(length=100), nullable=True),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("confidence_score", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("observed_at", sa.DateTime(), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(), nullable=False),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.CheckConstraint(
            "range_low IS NULL OR range_high IS NULL OR range_low <= range_high",
            name="ck_ad_metric_range",
        ),
        sa.CheckConstraint(
            "period_start IS NULL OR period_end IS NULL OR period_start <= period_end",
            name="ck_ad_metric_period",
        ),
        sa.CheckConstraint(
            "confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)",
            name="ck_ad_metric_confidence",
        ),
        sa.UniqueConstraint("workspace_id", "observation_key", name="uq_ad_metric_observation_key"),
    )
    op.create_index(
        "ix_ad_metric_ad_key_time",
        "ad_metric_observations",
        ["ad_id", "metric_key", "observed_at"],
    )
    op.create_index(
        "ix_ad_metric_workspace_provider",
        "ad_metric_observations",
        ["workspace_id", "provider"],
    )


def downgrade() -> None:
    op.drop_index("ix_ad_metric_workspace_provider", table_name="ad_metric_observations")
    op.drop_index("ix_ad_metric_ad_key_time", table_name="ad_metric_observations")
    op.drop_table("ad_metric_observations")
