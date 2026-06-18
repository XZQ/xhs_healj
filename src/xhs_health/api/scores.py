from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from xhs_health.db import get_session
from xhs_health.models import Score
from xhs_health.schemas import ScoreOut, TriggerScoreRequest
from xhs_health.services.score_service import calculate_and_store_score


router = APIRouter()


@router.post("/trigger", response_model=ScoreOut)
def trigger_score(payload: TriggerScoreRequest, session: Session = Depends(get_session)) -> Score:
    score = calculate_and_store_score(session, payload.account_id, payload.score_date)
    session.commit()
    session.refresh(score)
    return score


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
def get_score_history(account_id: int, session: Session = Depends(get_session)) -> list[Score]:
    return list(
        session.scalars(
            select(Score).where(Score.account_id == account_id).order_by(Score.score_date.desc())
        ).all()
    )

