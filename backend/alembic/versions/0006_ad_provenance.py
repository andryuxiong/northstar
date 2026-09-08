"""add durable ad provider provenance

Revision ID: 0006_ad_provenance
Revises: 0005_intelligence_foundation
Create Date: 2026-07-11 16:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0006_ad_provenance"
down_revision = "0005_intelligence_foundation"
branch_labels = None
depends_on = None


json_type = sa.JSON().with_variant(
    postgresql.JSONB(astext_type=sa.Text()),
    "postgresql",
)


def upgrade() -> None:
    with op.batch_alter_table("ads") as batch:
        batch.add_column(sa.Column("data_provider", sa.String(length=50), nullable=True))
        batch.add_column(sa.Column("source_type", sa.String(length=50), nullable=True))
        batch.add_column(sa.Column("provider_record_id", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("source_url", sa.Text(), nullable=True))
        batch.add_column(sa.Column("provider_metadata_json", json_type, nullable=True))

    op.execute(
        "UPDATE ads SET "
        "data_provider = CASE "
        "WHEN platform = 'meta' AND external_ad_id IS NOT NULL THEN 'meta_ad_library' "
        "ELSE 'northstar_manual' END, "
        "source_type = CASE "
        "WHEN platform = 'meta' AND external_ad_id IS NOT NULL THEN 'official_provider_api' "
        "ELSE 'manual_import' END, "
        "provider_record_id = CASE "
        "WHEN platform = 'meta' AND external_ad_id IS NOT NULL THEN external_ad_id "
        "ELSE NULL END, "
        "source_url = CASE "
        "WHEN platform = 'meta' AND external_ad_id IS NOT NULL THEN ad_snapshot_url "
        "ELSE NULL END"
    )

    with op.batch_alter_table("ads") as batch:
        batch.alter_column("data_provider", existing_type=sa.String(length=50), nullable=False)
        batch.alter_column("source_type", existing_type=sa.String(length=50), nullable=False)
        batch.drop_index("ix_ad_workspace_platform_external")
        batch.create_index(
            "ix_ad_workspace_provider_record",
            ["workspace_id", "data_provider", "provider_record_id"],
            unique=True,
        )
        batch.create_index(
            "ix_ad_workspace_platform_external",
            ["workspace_id", "platform", "external_ad_id"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("ads") as batch:
        batch.drop_index("ix_ad_workspace_platform_external")
        batch.drop_index("ix_ad_workspace_provider_record")
        batch.create_index(
            "ix_ad_workspace_platform_external",
            ["workspace_id", "platform", "external_ad_id"],
            unique=True,
        )
        batch.drop_column("provider_metadata_json")
        batch.drop_column("source_url")
        batch.drop_column("provider_record_id")
        batch.drop_column("source_type")
        batch.drop_column("data_provider")
