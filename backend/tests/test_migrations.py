from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.core.config import BACKEND_DIR
from app.db.schema_compat import HEAD_REVISION, upgrade_database_schema


def _config() -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return config


def _upgrade(engine, revision: str) -> None:
    config = _config()
    with engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, revision)


def test_fresh_sqlite_migrates_to_current_schema(tmp_path):
    database = tmp_path / "fresh.db"
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    try:
        upgrade_database_schema(engine)
        tables = set(inspect(engine).get_table_names())
        assert {
            "store_profiles",
            "store_identities",
            "estimation_profiles",
            "analysis_runs",
            "traffic_observations",
            "derived_insights",
            "evidence_records",
            "insight_evidence",
        } <= tables
        evidence_columns = {column["name"] for column in inspect(engine).get_columns("evidence_records")}
        assert {"independence_group", "details"} <= evidence_columns
        ad_columns = {column["name"] for column in inspect(engine).get_columns("ads")}
        assert {
            "data_provider",
            "source_type",
            "provider_record_id",
            "source_url",
            "provider_metadata_json",
        } <= ad_columns
        assert "ad_metric_observations" in tables
        assert "product_economics_scenarios" in tables
        assert "investigation_items" in tables
        assert "investigation_evidence_links" in tables
        assert "ad_watches" in tables
        assert "ad_collection_runs" in tables
        assert "ad_watch_observations" in tables
        metric_columns = {
            column["name"] for column in inspect(engine).get_columns("ad_metric_observations")
        }
        assert {"metric_key", "value_kind", "range_low", "range_high", "provider"} <= metric_columns
        economics_columns = {
            column["name"] for column in inspect(engine).get_columns("product_economics_scenarios")
        }
        assert {
            "scenario_key", "revision", "selling_price", "product_cost_low",
            "product_cost_high", "target_profit_margin", "input_source",
        } <= economics_columns
        with engine.connect() as connection:
            revision = connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one()
        assert revision == HEAD_REVISION
    finally:
        engine.dispose()


def test_unversioned_legacy_sqlite_is_backed_up_and_rows_survive(tmp_path):
    database = tmp_path / "legacy.db"
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    try:
        _upgrade(engine, "0004_add_meta_ad_details")
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "INSERT INTO users (id, email, password_hash, created_at) "
                "VALUES (1, 'legacy@example.com', NULL, CURRENT_TIMESTAMP)"
            )
            connection.exec_driver_sql(
                "INSERT INTO workspaces (id, name, owner_user_id) VALUES (1, 'Legacy', 1)"
            )
            connection.exec_driver_sql(
                "INSERT INTO stores "
                "(id, workspace_id, domain, platform_guess, first_seen_at, last_seen_at) "
                "VALUES (1, 1, 'legacy.example.com', 'unknown', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
            connection.exec_driver_sql("DROP TABLE alembic_version")

        upgrade_database_schema(engine)
        with engine.connect() as connection:
            assert connection.exec_driver_sql("SELECT COUNT(*) FROM users").scalar_one() == 1
            assert connection.exec_driver_sql("SELECT COUNT(*) FROM stores").scalar_one() == 1
            assert (
                connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one()
                == HEAD_REVISION
            )
        backups = list((tmp_path / "backups").glob("legacy.pre-legacy.*.db"))
        assert len(backups) == 1
        assert backups[0].stat().st_size > 0
    finally:
        engine.dispose()


def test_0005_ads_receive_provider_provenance_without_losing_rows(tmp_path):
    database = tmp_path / "ad-provenance.db"
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    try:
        _upgrade(engine, "0005_intelligence_foundation")
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "INSERT INTO users (id, email, password_hash, created_at) "
                "VALUES (1, 'ads@example.com', NULL, CURRENT_TIMESTAMP)"
            )
            connection.exec_driver_sql(
                "INSERT INTO workspaces (id, name, owner_user_id) VALUES (1, 'Ads', 1)"
            )
            connection.exec_driver_sql(
                "INSERT INTO ads "
                "(id, workspace_id, external_ad_id, platform, advertiser_name, first_seen_at, "
                "last_seen_at, creative_type, ad_snapshot_url) "
                "VALUES (1, 1, 'meta-123', 'meta', 'Merchant', CURRENT_TIMESTAMP, "
                "CURRENT_TIMESTAMP, 'unknown', 'https://www.facebook.com/ads/library/?id=meta-123')"
            )

        upgrade_database_schema(engine)
        with engine.connect() as connection:
            row = connection.exec_driver_sql(
                "SELECT data_provider, source_type, provider_record_id, source_url "
                "FROM ads WHERE id = 1"
            ).one()
            assert row[0] == "meta_ad_library"
            assert row[1] == "official_provider_api"
            assert row[2] == "meta-123"
            assert row[3].endswith("?id=meta-123")
            assert connection.exec_driver_sql("SELECT COUNT(*) FROM ads").scalar_one() == 1
    finally:
        engine.dispose()
