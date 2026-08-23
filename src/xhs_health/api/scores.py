import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from xhs_health.db import get_session
from xhs_health.models import Account, Score
from xhs_health.schemas import BatchTriggerScoreRequest, ScoreOut, TriggerScoreRequest
from xhs_health.services.score_service import calculate_and_store_score


_log = logging.getLogger("xhs_health.scores")


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
        account_ids = list(
            session.scalars(select(Account.id).where(Account.status == "active")).all()
        )
    elif account_ids:
        requested = set(account_ids)
        found = set(session.scalars(select(Account.id).where(Account.id.in_(requested))).all())
        missing = sorted(requested - found)
        if missing:
            # Validate before the first per-account commit. Returning a 404 after
            # earlier scores were persisted makes the failed request non-atomic.
            raise HTTPException(status_code=404, detail=f"account not found: {missing[0]}")
    scores = []
    for account_id in account_ids:
        try:
            score = calculate_and_store_score(session, account_id, payload.score_date)
            # Commit per account so one account's failure cannot discard the
            # scores already computed for the rest of the batch.
            session.commit()
            scores.append(score)
        except HTTPException as exc:
            session.rollback()
            # IDs are prevalidated above. A concurrent delete or a no-snapshot
            # account is an item-level failure and must not turn already committed
            # results into a request-level error.
            _log.warning(
                "batch-trigger: score rejected for account_id=%s: %s",
                account_id,
                exc.detail,
            )
            continue
        except Exception as exc:
            session.rollback()
            _log.warning("batch-trigger: score failed for account_id=%s: %s", account_id, exc)
            continue
    for score in scores:
        session.refresh(score)
    return scores


@router.get("/{account_id}", response_model=ScoreOut)
def get_latest_score(account_id: int, session: Session = Depends(get_session)) -> Score:
    score = session.scalar(
        select(Score)
        .where(Score.account_id == account_id)
        .order_by(Score.score_date.desc(), Score.created_at.desc(), Score.id.desc())
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
            .order_by(Score.score_date.desc(), Score.created_at.desc(), Score.id.desc())
            .limit(limit)
        ).all()
    )
