from pathlib import Path
from secrets import token_urlsafe

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BACKEND_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR.parent / ".env", extra="ignore")
    app_env: str = "local"
    app_secret: str = Field(default_factory=lambda: token_urlsafe(32))
    app_base_url: str = "http://localhost:8000"

    # Personal installations use a local SQLite file by default. A Postgres URL
    # can still be supplied through DATABASE_URL for a larger deployment.
    database_url: str = f"sqlite:///{(DATA_DIR / 'northstar.db').as_posix()}"

    postgres_user: str = "app"
    postgres_password: str = "app"
    postgres_db: str = "dropship"
    postgres_host: str = "postgres"
    postgres_port: int = 5432

    redis_host: str = "redis"
    redis_port: int = 6379

    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/1"

    snapshot_dir: str = str(DATA_DIR / "snapshots")
    user_agent: str = "NorthstarPersonalResearch/1.0"
    crawl_min_interval_seconds: int = 1
    max_products_per_scan: int = 100
    max_response_bytes: int = 10_000_000
    local_task_workers: int = 1
    mirror_product_images: bool = False

    frontend_origin: str = "http://localhost:5173"

    meta_ads_access_token: str = ""
    # Meta versions the Graph API. Keep this configurable for future upgrades,
    # but use the current supported version for fresh personal installations.
    meta_graph_version: str = "v25.0"

    # Optional GetHookd public API integration. Results are searched live and
    # are not persisted until the ad schema carries explicit provider provenance.
    gethookd_api_token: str = ""
    gethookd_api_base_url: str = "https://app.gethookd.ai/api/v1"

    # Similarweb can be configured with SIMILARWEB_API_KEY or through the
    # loopback-only integration API. API-configured credentials are stored in
    # this local JSON file as plaintext; see the warning returned by the
    # integration status endpoint.
    similarweb_api_key: str = ""
    similarweb_api_base_url: str = "https://api.similarweb.com"
    integration_config_path: str = str(DATA_DIR / "integrations.json")

    @property
    def sqlalchemy_database_uri(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+psycopg2://{self.postgres_user}:"
            f"{self.postgres_password}@{self.postgres_host}:"
            f"{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
