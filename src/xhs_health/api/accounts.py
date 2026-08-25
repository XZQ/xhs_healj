from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from xhs_health.db import get_session
from xhs_health.models import Account, AccountGroupMember, Score
from xhs_health.schemas import AccountCreate, AccountOut, AccountUpdate


router = APIRouter()


def _account_out(account: Account, latest_score: Score | None = None) -> AccountOut:
    data = AccountOut.model_validate(account)
    data.group_ids = [item.group_id for item in account.group_links]
    data.latest_score = latest_score
    return data


def _latest_scores_for(session: Session, account_ids: list[int]) -> dict[int, Score]:
    """One query: pick the latest score per account using a window function."""
    if not account_ids:
        return {}
    sub = (
        select(
            Score.id,
            Score.account_id,
            func.row_number()
            .over(
                partition_by=Score.account_id,
                order_by=[desc(Score.score_date), desc(Score.created_at), desc(Score.id)],
            )
            .label("rn"),
        )
        .where(Score.account_id.in_(account_ids))
        .subquery()
    )
    rows = session.execute(
        select(Score).join(sub, Score.id == sub.c.id).where(sub.c.rn == 1)
    ).scalars().all()
    return {row.account_id: row for row in rows}


@router.post("", response_model=AccountOut)
def create_account(payload: AccountCreate, session: Session = Depends(get_session)) -> AccountOut:
    if not payload.platform_uid.strip() or not payload.nickname.strip():
        raise HTTPException(
            status_code=422, detail="platform_uid and nickname must not be blank"
        )
    existing = session.scalar(select(Account).where(Account.platform_uid == payload.platform_uid))
    if existing:
        raise HTTPException(status_code=409, detail="platform_uid already exists")
    account = Account(**payload.model_dump())
    session.add(account)
    session.commit()
    session.refresh(account)
    return _account_out(account)


@router.get("", response_model=list[AccountOut])
def list_accounts(
    status: str | None = None,
    group_id: int | None = None,
    limit: int = 10,
    offset: int = 0,
    response: Response = None,
    session: Session = Depends(get_session),
) -> list[AccountOut]:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    stmt = select(Account)
    if status:
        stmt = stmt.where(Account.status == status)
    if group_id is not None:
        stmt = stmt.join(AccountGroupMember).where(AccountGroupMember.group_id == group_id)
    total = session.scalar(select(func.count()).select_from(stmt.subquery()))
    if response is not None:
        response.headers["X-Total-Count"] = str(total)
    accounts = list(session.scalars(stmt.order_by(Account.id.desc()).limit(limit).offset(offset)).all())
    scores = _latest_scores_for(session, [a.id for a in accounts])
    return [_account_out(account, scores.get(account.id)) for account in accounts]


@router.get("/{account_id}", response_model=AccountOut)
def get_account(account_id: int, session: Session = Depends(get_session)) -> AccountOut:
    account = session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="account not found")
    scores = _latest_scores_for(session, [account.id])
    return _account_out(account, scores.get(account.id))


@router.put("/{account_id}", response_model=AccountOut)
def update_account(
    account_id: int, payload: AccountUpdate, session: Session = Depends(get_session)
) -> AccountOut:
    account = session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="account not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(account, field, value)
    session.commit()
    session.refresh(account)
    return _account_out(account)


@router.delete("/{account_id}", response_model=AccountOut)
def archive_account(account_id: int, session: Session = Depends(get_session)) -> AccountOut:
    account = session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="account not found")
    account.status = "archived"
    session.commit()
    session.refresh(account)
    return _account_out(account)
