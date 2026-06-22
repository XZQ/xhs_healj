from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from xhs_health.db import get_session
from xhs_health.models import Account, AccountGroup, AccountGroupMember
from xhs_health.schemas import AccountGroupCreate, AccountGroupMembershipRequest, AccountGroupOut


router = APIRouter()


def _serialize_group(group: AccountGroup) -> AccountGroupOut:
    return AccountGroupOut(
        id=group.id,
        name=group.name,
        description=group.description,
        created_at=group.created_at,
        account_ids=[item.account_id for item in group.members],
    )


@router.post("", response_model=AccountGroupOut)
def create_group(payload: AccountGroupCreate, session: Session = Depends(get_session)) -> AccountGroupOut:
    existing = session.scalar(select(AccountGroup).where(AccountGroup.name == payload.name))
    if existing:
        raise HTTPException(status_code=409, detail="group name already exists")
    group = AccountGroup(**payload.model_dump())
    session.add(group)
    session.commit()
    session.refresh(group)
    return _serialize_group(group)


@router.get("", response_model=list[AccountGroupOut])
def list_groups(session: Session = Depends(get_session)) -> list[AccountGroupOut]:
    groups = list(session.scalars(select(AccountGroup).order_by(AccountGroup.id.asc())).all())
    return [_serialize_group(group) for group in groups]


@router.put("/{group_id}/members", response_model=AccountGroupOut)
def replace_group_members(
    group_id: int,
    payload: AccountGroupMembershipRequest,
    session: Session = Depends(get_session),
) -> AccountGroupOut:
    group = session.get(AccountGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="group not found")

    account_ids = sorted(set(payload.account_ids))
    if account_ids:
        found = set(session.scalars(select(Account.id).where(Account.id.in_(account_ids))).all())
        missing = sorted(set(account_ids) - found)
        if missing:
            raise HTTPException(status_code=404, detail=f"account not found: {missing[0]}")

    session.execute(delete(AccountGroupMember).where(AccountGroupMember.group_id == group_id))
    for account_id in account_ids:
        session.add(AccountGroupMember(group_id=group_id, account_id=account_id))
    session.commit()
    session.refresh(group)
    return _serialize_group(group)


@router.delete("/{group_id}", response_model=AccountGroupOut)
def delete_group(group_id: int, session: Session = Depends(get_session)) -> AccountGroupOut:
    group = session.get(AccountGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="group not found")
    output = _serialize_group(group)
    session.execute(delete(AccountGroupMember).where(AccountGroupMember.group_id == group_id))
    session.delete(group)
    session.commit()
    return output
