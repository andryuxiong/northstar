"""add traffic snapshots

Revision ID: 0003_add_traffic_snapshots
Revises: 0002_add_external_ad_id
Create Date: 2026-07-10 20:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_add_traffic_snapshots"
down_revision = "0002_add_external_ad_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "traffic_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("store_id", sa.Integer(), sa.ForeignKey("stores.id"), nullable=True),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column("period_start", sa.String(length=7), nullable=False),
        sa.Column("period_end", sa.String(length=7), nullable=False),
        sa.Column("country", sa.String(length=10), nullable=False),
        sa.Column("granularity", sa.String(length=20), nullable=False),
        sa.Column("main_domain_only", sa.Boolean(), nullable=False),
        sa.Column("total_visits", sa.Float(), nullable=True),
        sa.Column("global_rank", sa.Integer(), nullable=True),
        sa.Column("visits_series_json", sa.JSON(), nullable=True),
        sa.Column("global_rank_series_json", sa.JSON(), nullable=True),
        sa.Column("metric_status_json", sa.JSON(), nullable=True),
        sa.Column("fetch_status", sa.String(length=30), nullable=False),
        sa.Column("provider_last_updated", sa.String(length=30), nullable=True),
    )
    op.create_index(
        "ix_traffic_snapshot_store_time",
        "traffic_snapshots",
        ["store_id", "fetched_at"],
        unique=False,
    )
    op.create_index(
        "ix_traffic_snapshot_domain_time",
        "traffic_snapshots",
        ["workspace_id", "domain", "fetched_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_traffic_snapshot_domain_time", table_name="traffic_snapshots")
    op.drop_index("ix_traffic_snapshot_store_time", table_name="traffic_snapshots")
    op.drop_table("traffic_snapshots")
