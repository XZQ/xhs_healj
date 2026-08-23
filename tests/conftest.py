import atexit
import os
import shutil
import tempfile
from pathlib import Path

# Tests must never touch the developer's working database: force the engine onto a
# throwaway file before any xhs_health module import binds DATABASE_URL. This
# overrides an exported DATABASE_URL on purpose — tests hitting a real Postgres
# would be worse than the default dev SQLite.
_test_dir = tempfile.mkdtemp(prefix="xhs_health_tests_")
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_test_dir).as_posix()}/tests.sqlite3"


def _cleanup_test_db() -> None:
    try:
        from xhs_health.db import engine

        engine.dispose()
    except Exception:
        pass
    shutil.rmtree(_test_dir, ignore_errors=True)


atexit.register(_cleanup_test_db)

# Tests do not authenticate; allow the app to start without APP_API_TOKEN.
os.environ.setdefault("XHS_HEALTH_ALLOW_NO_TOKEN", "1")
