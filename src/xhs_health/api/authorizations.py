from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from xhs_health.db import get_session
from xhs_health.models import (
    Account,
    AccountAuthorization,
    AccountDailySnapshot,
    AccountGroupMember,
    Alert,
    AuditLog,
    Note,
    NoteDailyMetric,
    Score,
)
from xhs_health.schemas import (
    AccountAuthorizationCreate,
    AccountAuthorizationOut,
    AccountDataActionOut,
    AccountDataDeletionRequest,
)


router = APIRouter()


def _audit(
    session: Session,
    action: str,
    target_type: str,
    target_id: str | int,
    detail: dict[str, Any] | None = None,
    actor: str | None = None,
) -> None:
    session.add(
        AuditLog(
            actor=actor,
            action=action,
            target_type=target_type,
            target_id=str(target_id),
            detail=detail or {},
        )
    )


def _require_account(session: Session, account_id: int) -> Account:
    account = session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="account not found")
    return account


@router.get("/accounts/{account_id}", response_model=list[AccountAuthorizationOut])
def list_account_authorizations(
    account_id: int, limit: int = 100, session: Session = Depends(get_session)
) -> list[AccountAuthorization]:
    _require_account(session, account_id)
    limit = max(1, min(limit, 500))
    return list(
        session.scalars(
            select(AccountAuthorization)
            .where(AccountAuthorization.account_id == account_id)
            .order_by(AccountAuthorization.created_at.desc(), AccountAuthorization.id.desc())
            .limit(limit)
        ).all()
    )


@router.post("/accounts/{account_id}", response_model=AccountAuthorizationOut)
def create_account_authorization(
    account_id: int,
    payload: AccountAuthorizationCreate,
    session: Session = Depends(get_session),
) -> AccountAuthorization:
    _require_account(session, account_id)
    authorization = AccountAuthorization(account_id=account_id, **payload.model_dump())
    session.add(authorization)
    _audit(
        session,
        action="authorization.created",
        target_type="account",
        target_id=account_id,
        detail={"authorization_type": payload.authorization_type, "scope": payload.scope},
        actor=payload.authorized_by,
    )
    session.commit()
    session.refresh(authorization)
    return authorization


@router.put("/{authorization_id}/revoke", response_model=AccountAuthorizationOut)
def revoke_account_authorization(
    authorization_id: int,
    actor: str | None = None,
    session: Session = Depends(get_session),
) -> AccountAuthorization:
    authorization = session.get(AccountAuthorization, authorization_id)
    if not authorization:
        raise HTTPException(status_code=404, detail="authorization not found")
    authorization.revoked_at = datetime.now(timezone.utc)
    account = session.get(Account, authorization.account_id)
    if account:
        account.status = "archived"
    _audit(
        session,
        action="authorization.revoked",
        target_type="account",
        target_id=authorization.account_id,
        detail={"authorization_id": authorization.id},
        actor=actor,
    )
    session.commit()
    session.refresh(authorization)
    return authorization


@router.get("/accounts/{account_id}/export")
def export_account_data(account_id: int, session: Session = Depends(get_session)) -> dict[str, Any]:
    account = _require_account(session, account_id)
    snapshots = list(
        session.scalars(
            select(AccountDailySnapshot)
            .where(AccountDailySnapshot.account_id == account_id)
            .order_by(AccountDailySnapshot.data_date.desc())
        ).all()
    )
    notes = list(
        session.scalars(select(Note).where(Note.account_id == account_id).order_by(Note.id.asc())).all()
    )
    metrics = list(
        session.scalars(
            select(NoteDailyMetric)
            .where(NoteDailyMetric.account_id == account_id)
            .order_by(NoteDailyMetric.data_date.desc())
        ).all()
    )
    scores = list(
        session.scalars(
            select(Score).where(Score.account_id == account_id).order_by(Score.score_date.desc())
        ).all()
    )
    alerts = list(
        session.scalars(
            select(Alert).where(Alert.account_id == account_id).order_by(Alert.created_at.desc())
        ).all()
    )
    authorizations = list(
        session.scalars(
            select(AccountAuthorization)
            .where(AccountAuthorization.account_id == account_id)
            .order_by(AccountAuthorization.created_at.desc())
        ).all()
    )
    return jsonable_encoder(
        {
            "account": account,
            "snapshots": snapshots,
            "notes": notes,
            "note_metrics": metrics,
            "scores": scores,
            "alerts": alerts,
            "authorizations": authorizations,
        }
    )


@router.post("/accounts/{account_id}/data-deletion", response_model=AccountDataActionOut)
def handle_account_data_deletion(
    account_id: int,
    payload: AccountDataDeletionRequest,
    session: Session = Depends(get_session),
) -> AccountDataActionOut:
    account = _require_account(session, account_id)
    if payload.mode == "anonymize":
        account.platform_uid = f"anonymized_{account.id}_{int(datetime.now(timezone.utc).timestamp())}"
        account.nickname = "Anonymized Account"
        account.avatar_url = None
        account.category = None
        account.tags = []
        account.status = "archived"
        for note in session.scalars(select(Note).where(Note.account_id == account_id)):
            note.title = None
            note.tags = []
        # raw_payload stores the unmodified imported row — it can embed PII the
        # structured columns no longer carry, so an anonymize must purge it too.
        for snapshot in session.scalars(
            select(AccountDailySnapshot).where(AccountDailySnapshot.account_id == account_id)
        ):
            snapshot.raw_payload = {}
        for metric in session.scalars(
            select(NoteDailyMetric).where(NoteDailyMetric.account_id == account_id)
        ):
            metric.raw_payload = {}
        _audit(
            session,
            action="account_data.anonymized",
            target_type="account",
            target_id=account_id,
            detail={"reason": payload.reason},
            actor=payload.actor,
        )
        session.commit()
        return AccountDataActionOut(account_id=account_id, action="anonymize", status="completed")

    deletes: dict[str, int] = {}
    for name, stmt in [
        ("note_metrics", delete(NoteDailyMetric).where(NoteDailyMetric.account_id == account_id)),
        ("notes", delete(Note).where(Note.account_id == account_id)),
        ("snapshots", delete(AccountDailySnapshot).where(AccountDailySnapshot.account_id == account_id)),
        ("scores", delete(Score).where(Score.account_id == account_id)),
        ("alerts", delete(Alert).where(Alert.account_id == account_id)),
        (
            "authorizations",
            delete(AccountAuthorization).where(AccountAuthorization.account_id == account_id),
        ),
        ("group_memberships", delete(AccountGroupMember).where(AccountGroupMember.account_id == account_id)),
    ]:
        result = session.execute(stmt)
        deletes[name] = int(result.rowcount or 0)
    session.delete(account)
    _audit(
        session,
        action="account_data.deleted",
        target_type="account",
        target_id=account_id,
        detail={"reason": payload.reason, "deleted_records": deletes},
        actor=payload.actor,
    )
    session.commit()
    return AccountDataActionOut(
        account_id=account_id, action="delete", status="completed", deleted_records=deletes
    )
