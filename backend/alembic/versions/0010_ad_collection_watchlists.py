"""add durable ad collection watchlists and retention observations

Revision ID: 0010_ad_collection_watchlists
Revises: 0009_investigation_shortlist
Create Date: 2026-07-12 22:15:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0010_ad_collection_watchlists"
down_revision = "0009_investigation_shortlist"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ad_watches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("store_id", sa.Integer(), sa.ForeignKey("stores.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False, server_default="meta_ad_library"),
        sa.Column("search_terms", sa.String(length=100), nullable=True),
        sa.Column("advertiser_id", sa.String(length=255), nullable=True),
        sa.Column("countries_json", sa.JSON(), nullable=False),
        sa.Column("interval_hours", sa.Integer(), nullable=False, server_default="24"),
        sa.Column("result_limit", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("next_run_at", sa.DateTime(), nullable=True),
        sa.Column("last_status", sa.String(length=30), nullable=False, server_default="never_run"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("interval_hours >= 1", name="ck_ad_watch_interval"),
        sa.CheckConstraint("result_limit >= 1 AND result_limit <= 500", name="ck_ad_watch_limit"),
    )
    op.create_index("ix_ad_watch_workspace_due", "ad_watches", ["workspace_id", "is_enabled", "next_run_at"])
    op.create_table(
        "ad_collection_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("watch_id", sa.Integer(), sa.ForeignKey("ad_watches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("trigger", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("fetched_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("inserted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("recurring_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_ad_collection_run_watch_time", "ad_collection_runs", ["watch_id", "started_at"])
    op.create_index("ix_ad_collection_run_workspace_status", "ad_collection_runs", ["workspace_id", "status"])
    op.create_table(
        "ad_watch_observations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("watch_id", sa.Integer(), sa.ForeignKey("ad_watches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ad_id", sa.Integer(), sa.ForeignKey("ads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("observation_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("consecutive_misses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_status", sa.String(length=30), nullable=False, server_default="observed"),
        sa.Column("retention_tier", sa.String(length=30), nullable=False, server_default="metadata"),
        sa.Column("retention_reason", sa.Text(), nullable=True),
        sa.UniqueConstraint("watch_id", "ad_id", name="uq_ad_watch_observation"),
    )
    op.create_index("ix_ad_watch_observation_watch_status", "ad_watch_observations", ["watch_id", "current_status"])
    op.create_index("ix_ad_watch_observation_ad", "ad_watch_observations", ["ad_id"])


def downgrade() -> None:
    op.drop_index("ix_ad_watch_observation_ad", table_name="ad_watch_observations")
    op.drop_index("ix_ad_watch_observation_watch_status", table_name="ad_watch_observations")
    op.drop_table("ad_watch_observations")
    op.drop_index("ix_ad_collection_run_workspace_status", table_name="ad_collection_runs")
    op.drop_index("ix_ad_collection_run_watch_time", table_name="ad_collection_runs")
    op.drop_table("ad_collection_runs")
    op.drop_index("ix_ad_watch_workspace_due", table_name="ad_watches")
    op.drop_table("ad_watches")
