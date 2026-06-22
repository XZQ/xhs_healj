from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from xhs_health.db import get_session
from xhs_health.models import Account, Alert, Score
from xhs_health.services.scheduler import score_scheduler


router = APIRouter()


@router.get("", response_class=PlainTextResponse)
def prometheus_metrics(session: Session = Depends(get_session)) -> str:
    account_count = session.scalar(select(func.count()).select_from(Account)) or 0
    active_count = (
        session.scalar(select(func.count()).select_from(Account).where(Account.status == "active"))
        or 0
    )
    score_count = session.scalar(select(func.count()).select_from(Score)) or 0
    unresolved_alerts = (
        session.scalar(select(func.count()).select_from(Alert).where(Alert.is_resolved.is_(False)))
        or 0
    )
    scheduler = score_scheduler.snapshot()
    lines = [
        "# HELP xhs_accounts_total Total monitored creator accounts.",
        "# TYPE xhs_accounts_total gauge",
        f"xhs_accounts_total {account_count}",
        "# HELP xhs_accounts_active Active creator accounts.",
        "# TYPE xhs_accounts_active gauge",
        f"xhs_accounts_active {active_count}",
        "# HELP xhs_scores_total Total stored health scores.",
        "# TYPE xhs_scores_total gauge",
        f"xhs_scores_total {score_count}",
        "# HELP xhs_alerts_unresolved Unresolved health alerts.",
        "# TYPE xhs_alerts_unresolved gauge",
        f"xhs_alerts_unresolved {unresolved_alerts}",
        "# HELP xhs_scheduler_runs_total Score scheduler run count.",
        "# TYPE xhs_scheduler_runs_total counter",
        f"xhs_scheduler_runs_total {scheduler.total_runs}",
        "# HELP xhs_scheduler_running Whether the score scheduler is currently running.",
        "# TYPE xhs_scheduler_running gauge",
        f"xhs_scheduler_running {1 if scheduler.running else 0}",
    ]
    return "\n".join(lines) + "\n"
