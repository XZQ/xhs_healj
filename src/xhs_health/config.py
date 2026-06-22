from functools import lru_cache
from os import getenv
from pathlib import Path


class Settings:
    def __init__(self) -> None:
        default_db = f"sqlite:///{Path.cwd() / 'xhs_health.sqlite3'}"
        self.app_name = getenv("APP_NAME", "xhs-health")
        self.database_url = getenv("DATABASE_URL", default_db)
        self.api_prefix = getenv("API_PREFIX", "/api/v1")
        self.api_token = getenv("APP_API_TOKEN")
        self.enable_scheduler = getenv("ENABLE_SCHEDULER", "false").lower() == "true"
        self.scheduler_interval_seconds = int(getenv("SCHEDULER_INTERVAL_SECONDS", "3600"))
        self.xhs_connector_mode = getenv("XHS_CONNECTOR_MODE", "manual")


@lru_cache
def get_settings() -> Settings:
    return Settings()
