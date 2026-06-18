from fastapi import APIRouter

from xhs_health.api import accounts, alerts, health, imports, scores


api_router = APIRouter()
api_router.include_router(health.router, tags=["system"])
api_router.include_router(accounts.router, prefix="/accounts", tags=["accounts"])
api_router.include_router(imports.router, prefix="/imports", tags=["imports"])
api_router.include_router(scores.router, prefix="/scores", tags=["scores"])
api_router.include_router(alerts.router, prefix="/alerts", tags=["alerts"])

