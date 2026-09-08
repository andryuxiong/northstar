"""initial

Revision ID: 0001_initial
Revises: 
Create Date: 2026-02-01 00:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


# SQLite is the default database for personal Northstar installations, while
# deployed installations may use PostgreSQL.  Keep the migration portable and
# select JSONB only when PostgreSQL is actually compiling the type.
json_type = sa.JSON().with_variant(
    postgresql.JSONB(astext_type=sa.Text()),
    "postgresql",
)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "workspaces",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
    )

    op.create_table(
        "source_urls",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("type", sa.Enum("ad", "landing_page", "product", "store", "collection", "sitemap", name="sourceurltype"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_fetched_at", sa.DateTime(), nullable=True),
        sa.Column("fetch_status", sa.String(length=50), nullable=True),
        sa.Column("last_http_status", sa.Integer(), nullable=True),
        sa.UniqueConstraint("workspace_id", "url", name="uq_sourceurl_workspace_url"),
    )

    op.create_table(
        "stores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("platform_guess", sa.Enum("shopify", "woocommerce", "custom", "unknown", name="platformguess"), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("workspace_id", "domain", name="uq_store_workspace_domain"),
    )
    op.create_index("ix_store_domain", "stores", ["domain"], unique=False)

    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("store_id", sa.Integer(), sa.ForeignKey("stores.id"), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("workspace_id", "canonical_url", name="uq_product_workspace_canonical_url"),
    )
    op.create_index("ix_product_title", "products", ["title"], unique=False)

    op.create_table(
        "product_variants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("sku", sa.String(length=255), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("compare_at_price", sa.Float(), nullable=True),
        sa.Column("available", sa.Boolean(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "product_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("price_min", sa.Float(), nullable=True),
        sa.Column("price_max", sa.Float(), nullable=True),
        sa.Column("available", sa.Boolean(), nullable=True),
        sa.Column("variant_count", sa.Integer(), nullable=True),
        sa.Column("images_json", json_type, nullable=True),
        sa.Column("raw_extracted_json", json_type, nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
    )
    op.create_index("ix_product_snapshot_time", "product_snapshots", ["product_id", "fetched_at"], unique=False)

    op.create_table(
        "store_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("store_id", sa.Integer(), sa.ForeignKey("stores.id"), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column("product_count", sa.Integer(), nullable=True),
        sa.Column("collections_count", sa.Integer(), nullable=True),
        sa.Column("raw_extracted_json", json_type, nullable=True),
    )
    op.create_index("ix_store_snapshot_time", "store_snapshots", ["store_id", "fetched_at"], unique=False)

    op.create_table(
        "ads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("platform", sa.Enum("meta", "tiktok", "google", "manual", name="adplatform"), nullable=False),
        sa.Column("advertiser_name", sa.String(length=255), nullable=True),
        sa.Column("advertiser_id", sa.String(length=255), nullable=True),
        sa.Column("ad_text", sa.Text(), nullable=True),
        sa.Column("headline", sa.Text(), nullable=True),
        sa.Column("cta", sa.String(length=255), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("creative_type", sa.Enum("image", "video", "carousel", "unknown", name="creativetype"), nullable=False),
        sa.Column("creative_urls_json", json_type, nullable=True),
        sa.Column("landing_url", sa.Text(), nullable=True),
    )
    op.create_index("ix_ad_advertiser", "ads", ["advertiser_name"], unique=False)

    op.create_table(
        "landing_page_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("url_id", sa.Integer(), sa.ForeignKey("source_urls.id"), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column("final_url", sa.Text(), nullable=True),
        sa.Column("html_hash", sa.String(length=64), nullable=False),
        sa.Column("extracted_product_urls_json", json_type, nullable=True),
    )

    op.create_table(
        "ad_landing_edges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ad_id", sa.Integer(), sa.ForeignKey("ads.id"), nullable=False),
        sa.Column("url_id", sa.Integer(), sa.ForeignKey("source_urls.id"), nullable=False),
    )

    op.create_table(
        "landing_product_edges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("landing_url_id", sa.Integer(), sa.ForeignKey("source_urls.id"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
    )

    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.UniqueConstraint("workspace_id", "name", name="uq_tag_workspace_name"),
    )

    op.create_table(
        "tag_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity_type", sa.Enum("ad", "product", "store", name="tagentitytype"), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("tag_id", sa.Integer(), sa.ForeignKey("tags.id"), nullable=False),
    )

    op.create_table(
        "signals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity_type", sa.Enum("ad", "product", "store", name="signalentitytype"), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("signal_type", sa.String(length=100), nullable=False),
        sa.Column("value_json", json_type, nullable=True),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_signal_entity", "signals", ["entity_type", "entity_id"], unique=False)

    op.create_table(
        "scores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity_type", sa.Enum("ad", "product", "store", name="signalentitytype"), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("score_type", sa.Enum("winner", "momentum", "longevity_proxy", name="scoretype"), nullable=False),
        sa.Column("score_value", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("components_json", json_type, nullable=True),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_score_entity", "scores", ["entity_type", "entity_id"], unique=False)

    op.create_table(
        "alert_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("entity_type", sa.Enum("ad", "product", "store", name="signalentitytype"), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("rule_type", sa.Enum("price_drop", "back_in_stock", "new_variant", "new_product_on_store", "score_spike", name="alertruletype"), nullable=False),
        sa.Column("threshold_json", json_type, nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
    )

    op.create_table(
        "alert_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("alert_rule_id", sa.Integer(), sa.ForeignKey("alert_rules.id"), nullable=False),
        sa.Column("fired_at", sa.DateTime(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload_json", json_type, nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False),
    )

    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "CREATE INDEX ix_product_fts ON products USING gin "
            "(to_tsvector('english', coalesce(title,'') || ' ' || coalesce(description,'')))"
        )
        op.execute(
            "CREATE INDEX ix_ad_fts ON ads USING gin "
            "(to_tsvector('english', coalesce(ad_text,'')))"
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.drop_index("ix_ad_fts", table_name="ads")
        op.drop_index("ix_product_fts", table_name="products")

    op.drop_table("alert_events")
    op.drop_table("alert_rules")
    op.drop_index("ix_score_entity", table_name="scores")
    op.drop_table("scores")
    op.drop_index("ix_signal_entity", table_name="signals")
    op.drop_table("signals")
    op.drop_table("tag_assignments")
    op.drop_table("tags")
    op.drop_table("landing_product_edges")
    op.drop_table("ad_landing_edges")
    op.drop_table("landing_page_snapshots")
    op.drop_index("ix_ad_advertiser", table_name="ads")
    op.drop_table("ads")
    op.drop_index("ix_store_snapshot_time", table_name="store_snapshots")
    op.drop_table("store_snapshots")
    op.drop_index("ix_product_snapshot_time", table_name="product_snapshots")
    op.drop_table("product_snapshots")
    op.drop_table("product_variants")
    op.drop_index("ix_product_title", table_name="products")
    op.drop_table("products")
    op.drop_index("ix_store_domain", table_name="stores")
    op.drop_table("stores")
    op.drop_table("source_urls")
    op.drop_table("workspaces")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS alertruletype")
        op.execute("DROP TYPE IF EXISTS scoretype")
        op.execute("DROP TYPE IF EXISTS signalentitytype")
        op.execute("DROP TYPE IF EXISTS tagentitytype")
        op.execute("DROP TYPE IF EXISTS creativetype")
        op.execute("DROP TYPE IF EXISTS adplatform")
        op.execute("DROP TYPE IF EXISTS platformguess")
        op.execute("DROP TYPE IF EXISTS sourceurltype")
