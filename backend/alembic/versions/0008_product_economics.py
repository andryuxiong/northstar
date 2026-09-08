"""add versioned user-entered product economics scenarios

Revision ID: 0008_product_economics
Revises: 0007_ad_metric_observations
Create Date: 2026-07-12 06:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_product_economics"
down_revision = "0007_ad_metric_observations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_economics_scenarios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scenario_key", sa.String(length=64), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("supersedes_id", sa.Integer(), sa.ForeignKey("product_economics_scenarios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("input_source", sa.String(length=50), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("selling_price", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("product_cost_low", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("product_cost_high", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("shipping_cost_low", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("shipping_cost_high", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("fulfillment_cost_low", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("fulfillment_cost_high", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("other_variable_cost_low", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("other_variable_cost_high", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("payment_fee_rate", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column("payment_fee_fixed", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("refund_allowance_rate", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column("target_profit_margin", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("revision >= 1", name="ck_product_economics_revision"),
        sa.CheckConstraint("selling_price > 0", name="ck_product_economics_price"),
        sa.CheckConstraint("product_cost_low >= 0 AND shipping_cost_low >= 0 AND fulfillment_cost_low >= 0 AND other_variable_cost_low >= 0", name="ck_product_economics_nonnegative_costs"),
        sa.CheckConstraint("payment_fee_fixed >= 0", name="ck_product_economics_fixed_fee"),
        sa.CheckConstraint("product_cost_low <= product_cost_high", name="ck_product_economics_product_cost"),
        sa.CheckConstraint("shipping_cost_low <= shipping_cost_high", name="ck_product_economics_shipping_cost"),
        sa.CheckConstraint("fulfillment_cost_low <= fulfillment_cost_high", name="ck_product_economics_fulfillment_cost"),
        sa.CheckConstraint("other_variable_cost_low <= other_variable_cost_high", name="ck_product_economics_other_cost"),
        sa.CheckConstraint("payment_fee_rate >= 0 AND payment_fee_rate <= 1", name="ck_product_economics_payment_rate"),
        sa.CheckConstraint("refund_allowance_rate >= 0 AND refund_allowance_rate <= 1", name="ck_product_economics_refund_rate"),
        sa.CheckConstraint("target_profit_margin >= 0 AND target_profit_margin < 1", name="ck_product_economics_target_margin"),
        sa.UniqueConstraint("workspace_id", "scenario_key", "revision", name="uq_product_economics_revision"),
    )
    op.create_index("ix_product_economics_product_active", "product_economics_scenarios", ["product_id", "is_active"])
    op.create_index("ix_product_economics_workspace_key", "product_economics_scenarios", ["workspace_id", "scenario_key"])


def downgrade() -> None:
    op.drop_index("ix_product_economics_workspace_key", table_name="product_economics_scenarios")
    op.drop_index("ix_product_economics_product_active", table_name="product_economics_scenarios")
    op.drop_table("product_economics_scenarios")
