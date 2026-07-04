import os

# Tests do not authenticate; allow the app to start without APP_API_TOKEN.
os.environ.setdefault("XHS_HEALTH_ALLOW_NO_TOKEN", "1")
