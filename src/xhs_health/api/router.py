from fastapi import APIRouter

from xhs_health.api import (
    accounts,
    alerts,
    audit,
    authorizations,
    data_sources,
    groups,
    health,
    imports,
    integrations,
    jobs,
    metrics,
    notifications,
    reports,
    scores,
    stats,
)


api_router = APIRouter()
api_router.include_router(health.router, tags=["system"])
api_router.include_router(accounts.router, prefix="/accounts", tags=["accounts"])
api_router.include_router(imports.router, prefix="/imports", tags=["imports"])
api_router.include_router(scores.router, prefix="/scores", tags=["scores"])
api_router.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
api_router.include_router(groups.router, prefix="/groups", tags=["groups"])
api_router.include_router(stats.router, prefix="/stats", tags=["stats"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(metrics.router, prefix="/metrics", tags=["metrics"])
api_router.include_router(integrations.router, prefix="/integrations", tags=["integrations"])
api_router.include_router(data_sources.router, prefix="/data-sources", tags=["data-sources"])
api_router.include_router(authorizations.router, prefix="/authorizations", tags=["authorizations"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(audit.router, prefix="/audit-logs", tags=["audit"])
