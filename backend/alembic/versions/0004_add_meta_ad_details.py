"""add Meta Ad Library detail fields

Revision ID: 0004_add_meta_ad_details
Revises: 0003_add_traffic_snapshots
Create Date: 2026-07-10 21:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_add_meta_ad_details"
down_revision = "0003_add_traffic_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ads", sa.Column("ad_creation_time", sa.DateTime(), nullable=True))
    op.add_column("ads", sa.Column("delivery_start_time", sa.DateTime(), nullable=True))
    op.add_column("ads", sa.Column("delivery_stop_time", sa.DateTime(), nullable=True))
    op.add_column("ads", sa.Column("ad_snapshot_url", sa.Text(), nullable=True))
    op.add_column("ads", sa.Column("publisher_platforms_json", sa.JSON(), nullable=True))
    op.create_index(
        "ix_ad_workspace_platform_external",
        "ads",
        ["workspace_id", "platform", "external_ad_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_ad_workspace_platform_external", table_name="ads")
    op.drop_column("ads", "publisher_platforms_json")
    op.drop_column("ads", "ad_snapshot_url")
    op.drop_column("ads", "delivery_stop_time")
    op.drop_column("ads", "delivery_start_time")
    op.drop_column("ads", "ad_creation_time")
