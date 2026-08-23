from functools import lru_cache
from os import getenv
from pathlib import Path


def _positive_int_env(name: str, default: int, minimum: int = 1) -> int:
    raw = getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}, got {value}")
    return value


def _default_database_url() -> str:
    # Resolve relative to the project root (repo root) so cwd does not matter.
    project_root = Path(__file__).resolve().parents[2]
    return f"sqlite:///{project_root / 'xhs_health.sqlite3'}"


def _cors_origins() -> list[str]:
    raw = getenv("CORS_ALLOW_ORIGINS", "")
    if raw:
        return [item.strip() for item in raw.split(",") if item.strip()]
    # MVP default: local dev front-end only. Production must override.
    return ["http://127.0.0.1:5173", "http://localhost:5173"]


class Settings:
    def __init__(self) -> None:
        self.app_name = getenv("APP_NAME", "xhs-health")
        self.database_url = getenv("DATABASE_URL") or _default_database_url()
        self.api_prefix = getenv("API_PREFIX", "/api/v1")
        self.api_token = getenv("APP_API_TOKEN")
        if not self.api_token:
            # MVP-friendly: refuse to start naked in non-test environments.
            # Tests set APP_API_TOKEN="" explicitly via fixture or rely on TestClient.
            # For local dev we auto-derive a stable ephemeral token and print a warning.
            import secrets as _secrets
            import sys

            if getenv("XHS_HEALTH_ALLOW_NO_TOKEN") == "1":
                self.api_token = ""
            else:
                self.api_token = "dev-" + _secrets.token_hex(8)
                print(
                    "[xhs-health] WARNING: APP_API_TOKEN not set; generated ephemeral dev token: "
                    f"{self.api_token} (set APP_API_TOKEN or XHS_HEALTH_ALLOW_NO_TOKEN=1 to silence).",
                    file=sys.stderr,
                )
        self.cors_origins = _cors_origins()
        self.enable_scheduler = getenv("ENABLE_SCHEDULER", "false").lower() == "true"
        # Keep in sync with the scheduler's defensive 60s clamp: reject below-minimum
        # intervals at startup instead of silently running at a different cadence.
        self.scheduler_interval_seconds = _positive_int_env(
            "SCHEDULER_INTERVAL_SECONDS", 3600, minimum=60
        )
        self.xhs_connector_mode = getenv("XHS_CONNECTOR_MODE", "manual")


@lru_cache
def get_settings() -> Settings:
    return Settings()
