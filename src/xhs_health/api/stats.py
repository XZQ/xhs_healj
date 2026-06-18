from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends

from xhs_health.db import get_session
from xhs_health.models import Account, Alert, Score
from xhs_health.schemas import OverviewStatsOut


router = APIRouter()


@router.get("/overview", response_model=OverviewStatsOut)
def overview_stats(session: Session = Depends(get_session)) -> OverviewStatsOut:
    monitored_accounts = session.scalar(select(func.count()).select_from(Account)) or 0
    latest_score_ids = (
        select(func.max(Score.id).label("id"))
        .group_by(Score.account_id)
        .subquery()
    )
    latest_scores = list(
        session.scalars(select(Score).join(latest_score_ids, Score.id == latest_score_ids.c.id)).all()
    )
    healthy_accounts = sum(1 for score in latest_scores if float(score.total_score) >= 70)
    warning_accounts = sum(1 for score in latest_scores if 55 <= float(score.total_score) < 70)
    risky_accounts = sum(1 for score in latest_scores if float(score.total_score) < 55)
    low_confidence_accounts = sum(1 for score in latest_scores if score.confidence_level == "Low")
    unresolved_alerts = (
        session.scalar(select(func.count()).select_from(Alert).where(Alert.is_resolved.is_(False))) or 0
    )
    return OverviewStatsOut(
        monitored_accounts=monitored_accounts,
        healthy_accounts=healthy_accounts,
        warning_accounts=warning_accounts,
        risky_accounts=risky_accounts,
        low_confidence_accounts=low_confidence_accounts,
        unresolved_alerts=unresolved_alerts,
    )
