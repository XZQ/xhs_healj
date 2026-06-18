from functools import lru_cache
from os import getenv
from pathlib import Path


class Settings:
    def __init__(self) -> None:
        default_db = f"sqlite:///{Path.cwd() / 'xhs_health.sqlite3'}"
        self.app_name = getenv("APP_NAME", "xhs-health")
        self.database_url = getenv("DATABASE_URL", default_db)
        self.api_prefix = getenv("API_PREFIX", "/api/v1")


@lru_cache
def get_settings() -> Settings:
    return Settings()

