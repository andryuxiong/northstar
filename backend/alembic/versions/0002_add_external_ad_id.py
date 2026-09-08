"""add_external_ad_id

Revision ID: 0002_add_external_ad_id
Revises: 0001_initial
Create Date: 2026-02-01 00:30:00
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_add_external_ad_id"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ads", sa.Column("external_ad_id", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("ads", "external_ad_id")
