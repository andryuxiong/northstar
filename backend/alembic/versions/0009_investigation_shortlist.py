"""add durable decision-focused investigation shortlist

Revision ID: 0009_investigation_shortlist
Revises: 0008_product_economics
Create Date: 2026-07-12 07:05:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0009_investigation_shortlist"
down_revision = "0008_product_economics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "investigation_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("entity_type", sa.String(length=30), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("workflow_stage", sa.String(length=30), nullable=False),
        sa.Column("decision", sa.String(length=30), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("thesis", sa.Text(), nullable=True),
        sa.Column("risks", sa.Text(), nullable=True),
        sa.Column("next_action", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("entity_type IN ('store', 'product', 'ad')", name="ck_investigation_entity_type"),
        sa.CheckConstraint("workflow_stage IN ('inbox', 'researching', 'ready_to_test', 'testing', 'decided', 'archived')", name="ck_investigation_stage"),
        sa.CheckConstraint("decision IN ('undecided', 'investigate', 'test', 'reject')", name="ck_investigation_decision"),
        sa.CheckConstraint("priority IN ('low', 'medium', 'high')", name="ck_investigation_priority"),
        sa.UniqueConstraint("workspace_id", "entity_type", "entity_id", name="uq_investigation_entity"),
    )
    op.create_index("ix_investigation_workspace_stage", "investigation_items", ["workspace_id", "workflow_stage"])
    op.create_index("ix_investigation_workspace_priority", "investigation_items", ["workspace_id", "priority"])
    op.create_table(
        "investigation_evidence_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("investigation_id", sa.Integer(), sa.ForeignKey("investigation_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("evidence_id", sa.Integer(), sa.ForeignKey("evidence_records.id", ondelete="CASCADE"), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("investigation_id", "evidence_id", name="uq_investigation_evidence"),
    )
    op.create_index("ix_investigation_evidence_evidence", "investigation_evidence_links", ["evidence_id"])


def downgrade() -> None:
    op.drop_index("ix_investigation_evidence_evidence", table_name="investigation_evidence_links")
    op.drop_table("investigation_evidence_links")
    op.drop_index("ix_investigation_workspace_priority", table_name="investigation_items")
    op.drop_index("ix_investigation_workspace_stage", table_name="investigation_items")
    op.drop_table("investigation_items")
