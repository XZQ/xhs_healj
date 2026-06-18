from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from xhs_health.db import get_session
from xhs_health.models import Account
from xhs_health.schemas import AccountCreate, AccountOut


router = APIRouter()


@router.post("", response_model=AccountOut)
def create_account(payload: AccountCreate, session: Session = Depends(get_session)) -> Account:
    existing = session.scalar(select(Account).where(Account.platform_uid == payload.platform_uid))
    if existing:
        raise HTTPException(status_code=409, detail="platform_uid already exists")
    account = Account(**payload.model_dump())
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


@router.get("", response_model=list[AccountOut])
def list_accounts(session: Session = Depends(get_session)) -> list[Account]:
    return list(session.scalars(select(Account).order_by(Account.id.desc())).all())


@router.get("/{account_id}", response_model=AccountOut)
def get_account(account_id: int, session: Session = Depends(get_session)) -> Account:
    account = session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="account not found")
    return account

