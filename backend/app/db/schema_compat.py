"""Safe schema bootstrap for personal SQLite and normal Alembic upgrades.

Early personal Northstar builds called ``Base.metadata.create_all`` at startup
and therefore have a complete but unversioned SQLite schema.  Alembic cannot
upgrade those files until their existing schema is verified and stamped.  This
module creates a transactionally consistent SQLite backup, brings the small
known pre-Alembic gap to revision 0004, stamps it, and then runs normal Alembic
migrations.  It never drops or rewrites an existing user table.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from threading import Lock

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect

from app.core.config import BACKEND_DIR


logger = logging.getLogger(__name__)

LEGACY_BASELINE_REVISION = "0004_add_meta_ad_details"
HEAD_REVISION = "0010_ad_collection_watchlists"

_MIGRATION_LOCK = Lock()

_LEGACY_TABLES = {
    "users",
    "workspaces",
    "source_urls",
    "stores",
    "products",
    "product_variants",
    "product_snapshots",
    "store_snapshots",
    "ads",
    "landing_page_snapshots",
    "ad_landing_edges",
    "landing_product_edges",
    "tags",
    "tag_assignments",
    "signals",
    "scores",
    "alert_rules",
    "alert_events",
}

_FOUNDATION_TABLES = {
    "store_profiles",
    "store_identities",
    "estimation_profiles",
    "analysis_runs",
    "traffic_observations",
    "derived_insights",
    "evidence_records",
    "insight_evidence",
}

_SQLITE_AD_COLUMNS = {
    "external_ad_id": "VARCHAR(255)",
    "ad_creation_time": "DATETIME",
    "delivery_start_time": "DATETIME",
    "delivery_stop_time": "DATETIME",
    "ad_snapshot_url": "TEXT",
    "publisher_platforms_json": "JSON",
}

_AD_PROVENANCE_COLUMNS = {
    "data_provider",
    "source_type",
    "provider_record_id",
    "source_url",
    "provider_metadata_json",
}

_TRAFFIC_COLUMNS = {
    "id",
    "workspace_id",
    "store_id",
    "domain",
    "provider",
    "fetched_at",
    "period_start",
    "period_end",
    "country",
    "granularity",
    "main_domain_only",
    "total_visits",
    "global_rank",
    "visits_series_json",
    "global_rank_series_json",
    "metric_status_json",
    "fetch_status",
    "provider_last_updated",
}

_FOUNDATION_KEY_COLUMNS = {
    "store_profiles": {"id", "workspace_id", "store_id", "profile_version"},
    "store_identities": {
        "id",
        "workspace_id",
        "store_id",
        "identity_type",
        "normalized_value",
    },
    "estimation_profiles": {
        "id",
        "workspace_id",
        "category_key",
        "conversion_rate_low",
        "conversion_rate_high",
    },
    "analysis_runs": {
        "id",
        "workspace_id",
        "store_id",
        "analysis_version",
        "input_fingerprint",
    },
    "traffic_observations": {
        "id",
        "workspace_id",
        "observation_key",
        "metric_key",
        "period_start",
    },
    "derived_insights": {
        "id",
        "analysis_run_id",
        "subject_key",
        "metric_key",
        "estimator_version",
    },
    "evidence_records": {
        "id",
        "workspace_id",
        "store_id",
        "evidence_key",
        "evidence_type",
        "independence_group",
    },
    "insight_evidence": {"id", "insight_id", "evidence_id"},
}


class SchemaBootstrapError(RuntimeError):
    """Raised instead of guessing when a legacy database is not recognizable."""


def _alembic_config() -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    # Alembic otherwise resolves this relative path against the process's
    # current working directory, which is not guaranteed by the launcher.
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return config


def _current_revisions(engine: Engine) -> set[str]:
    inspector = inspect(engine)
    if "alembic_version" not in inspector.get_table_names():
        return set()
    with engine.connect() as connection:
        rows = connection.exec_driver_sql("SELECT version_num FROM alembic_version").all()
    return {str(row[0]) for row in rows}


def _sqlite_database_path(engine: Engine) -> Path | None:
    database = engine.url.database
    if not database or database == ":memory:":
        return None
    return Path(database).expanduser().resolve()


def _backup_sqlite_database(engine: Engine, reason: str) -> Path | None:
    source_path = _sqlite_database_path(engine)
    if source_path is None or not source_path.exists() or source_path.stat().st_size == 0:
        return None

    backup_dir = source_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S%fZ")
    safe_reason = "".join(character if character.isalnum() else "-" for character in reason)
    backup_path = backup_dir / f"{source_path.stem}.pre-{safe_reason}.{timestamp}.db"

    source = sqlite3.connect(str(source_path), timeout=30)
    destination = sqlite3.connect(str(backup_path), timeout=30)
    try:
        source.execute("PRAGMA busy_timeout=30000")
        source.backup(destination)
        integrity = destination.execute("PRAGMA integrity_check").fetchone()
        if not integrity or integrity[0] != "ok":
            raise SchemaBootstrapError(
                f"SQLite backup integrity check failed; backup retained at {backup_path}"
            )
    finally:
        destination.close()
        source.close()

    logger.info("Created pre-migration SQLite backup at %s", backup_path)
    return backup_path


def _validate_columns(engine: Engine, table: str, required: set[str]) -> None:
    inspector = inspect(engine)
    present = {column["name"] for column in inspector.get_columns(table)}
    missing = sorted(required - present)
    if missing:
        raise SchemaBootstrapError(
            f"Cannot safely stamp legacy SQLite database: {table} is missing "
            f"required columns {', '.join(missing)}"
        )


def _validate_legacy_baseline(engine: Engine) -> None:
    tables = set(inspect(engine).get_table_names())
    missing_tables = sorted(_LEGACY_TABLES - tables)
    if missing_tables:
        raise SchemaBootstrapError(
            "Cannot safely stamp a partial legacy SQLite database. Missing tables: "
            + ", ".join(missing_tables)
        )
    _validate_columns(
        engine,
        "users",
        {"id", "email", "password_hash", "created_at"},
    )
    _validate_columns(
        engine,
        "workspaces",
        {"id", "name", "owner_user_id"},
    )
    _validate_columns(
        engine,
        "stores",
        {"id", "workspace_id", "domain", "platform_guess", "first_seen_at", "last_seen_at"},
    )
    _validate_columns(
        engine,
        "products",
        {
            "id",
            "workspace_id",
            "store_id",
            "canonical_url",
            "title",
            "currency",
            "created_at",
            "last_seen_at",
        },
    )
    _validate_columns(
        engine,
        "ads",
        {
            "id",
            "workspace_id",
            "platform",
            "first_seen_at",
            "last_seen_at",
            "creative_type",
        },
    )


def _ensure_legacy_revision_0004(engine: Engine) -> None:
    """Apply only the additive gaps known between create_all builds and 0004."""

    _validate_legacy_baseline(engine)
    existing_ad_columns = {
        column["name"] for column in inspect(engine).get_columns("ads")
    }
    with engine.begin() as connection:
        for name, sql_type in _SQLITE_AD_COLUMNS.items():
            if name not in existing_ad_columns:
                connection.exec_driver_sql(f"ALTER TABLE ads ADD COLUMN {name} {sql_type}")
        connection.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_ad_workspace_platform_external "
            "ON ads (workspace_id, platform, external_ad_id)"
        )
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_ad_advertiser ON ads (advertiser_name)"
        )
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_product_title ON products (title)"
        )

    if "traffic_snapshots" not in inspect(engine).get_table_names():
        # Import lazily to avoid loading all ORM metadata during module import.
        from app.db.models import TrafficSnapshot

        TrafficSnapshot.__table__.create(bind=engine, checkfirst=True)
    _validate_columns(engine, "traffic_snapshots", _TRAFFIC_COLUMNS)


def _unversioned_foundation_revision(engine: Engine) -> str | None:
    """Recognize a database previously created from current ORM metadata.

    A process interrupted between an old ``create_all`` startup and stamping can
    already contain every foundation table. Validate their key columns, then
    stamp 0005 or the current head based on whether ad provenance is present.
    """

    tables = set(inspect(engine).get_table_names())
    present = tables & _FOUNDATION_TABLES
    if not present:
        return None
    if present != _FOUNDATION_TABLES:
        missing = sorted(_FOUNDATION_TABLES - present)
        raise SchemaBootstrapError(
            "Cannot safely stamp a partially-created intelligence schema. Missing tables: "
            + ", ".join(missing)
        )
    for table, columns in _FOUNDATION_KEY_COLUMNS.items():
        _validate_columns(engine, table, columns)
    ad_columns = {column["name"] for column in inspect(engine).get_columns("ads")}
    if not _AD_PROVENANCE_COLUMNS <= ad_columns:
        return "0005_intelligence_foundation"
    if "ad_metric_observations" not in tables:
        return "0006_ad_provenance"
    return HEAD_REVISION


def _stamp(engine: Engine, revision: str) -> None:
    config = _alembic_config()
    with engine.connect() as connection:
        config.attributes["connection"] = connection
        command.stamp(config, revision)


def _upgrade_to_head(engine: Engine) -> None:
    config = _alembic_config()
    with engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


def _upgrade_sqlite(engine: Engine) -> None:
    tables = set(inspect(engine).get_table_names())
    revisions = _current_revisions(engine)

    if revisions == {HEAD_REVISION}:
        return

    if not tables or tables == {"alembic_version"}:
        _upgrade_to_head(engine)
        return

    backup_path = _backup_sqlite_database(
        engine,
        "legacy" if not revisions else "-".join(sorted(revisions)),
    )
    try:
        if not revisions:
            _ensure_legacy_revision_0004(engine)
            foundation_revision = _unversioned_foundation_revision(engine)
            if foundation_revision:
                _stamp(engine, foundation_revision)
            else:
                _stamp(engine, LEGACY_BASELINE_REVISION)
        _upgrade_to_head(engine)
    except Exception as exc:
        backup_note = f" A complete backup is available at {backup_path}." if backup_path else ""
        detail = f" {exc}" if isinstance(exc, SchemaBootstrapError) else ""
        raise SchemaBootstrapError(
            f"Northstar database migration failed.{detail}{backup_note}"
        ) from exc

    final_revisions = _current_revisions(engine)
    if final_revisions != {HEAD_REVISION}:
        raise SchemaBootstrapError(
            "Northstar database did not reach the expected schema revision "
            f"{HEAD_REVISION}; found {sorted(final_revisions)}"
        )


def upgrade_database_schema(engine: Engine) -> None:
    """Upgrade the configured database without destructive schema guessing."""

    with _MIGRATION_LOCK:
        if engine.dialect.name == "sqlite":
            _upgrade_sqlite(engine)
        else:
            _upgrade_to_head(engine)


def ensure_personal_sqlite_schema(engine: Engine) -> None:
    """Backward-compatible entry point retained for older launch code."""

    upgrade_database_schema(engine)
