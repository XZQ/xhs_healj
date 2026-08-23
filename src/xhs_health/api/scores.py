from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from xhs_health.db import get_session
from xhs_health.models import Account, Score
from xhs_health.schemas import BatchTriggerScoreRequest, ScoreOut, TriggerScoreRequest
from xhs_health.services.score_service import calculate_and_store_score


router = APIRouter()


@router.post("/trigger", response_model=ScoreOut)
def trigger_score(payload: TriggerScoreRequest, session: Session = Depends(get_session)) -> Score:
    score = calculate_and_store_score(session, payload.account_id, payload.score_date)
    session.commit()
    session.refresh(score)
    return score


@router.post("/batch-trigger", response_model=list[ScoreOut])
def batch_trigger_scores(
    payload: BatchTriggerScoreRequest, session: Session = Depends(get_session)
) -> list[Score]:
    account_ids = payload.account_ids
    if account_ids is None:
        account_ids = list(session.scalars(select(Account.id).where(Account.status == "active")).all())
    scores = []
    for account_id in account_ids:
        try:
            scores.append(calculate_and_store_score(session, account_id, payload.score_date))
        except HTTPException as exc:
            if exc.status_code != 400:
                raise
    session.commit()
    for score in scores:
        session.refresh(score)
    return scores


@router.get("/{account_id}", response_model=ScoreOut)
def get_latest_score(account_id: int, session: Session = Depends(get_session)) -> Score:
    score = session.scalar(
        select(Score)
        .where(Score.account_id == account_id)
        .order_by(Score.score_date.desc(), Score.created_at.desc())
    )
    if not score:
        raise HTTPException(status_code=404, detail="score not found")
    return score


@router.get("/{account_id}/history", response_model=list[ScoreOut])
def get_score_history(
    account_id: int,
    limit: int = 365,
    session: Session = Depends(get_session),
) -> list[Score]:
    limit = max(1, min(limit, 1000))
    return list(
        session.scalars(
            select(Score)
            .where(Score.account_id == account_id)
            .order_by(Score.score_date.desc(), Score.created_at.desc())
            .limit(limit)
        ).all()
    )
