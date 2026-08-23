from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from xhs_health.db import get_session
from xhs_health.models import AuditLog
from xhs_health.schemas import AuditLogOut


router = APIRouter()


@router.get("", response_model=list[AuditLogOut])
def list_audit_logs(
    action: str | None = None,
    target_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
    response: Response = None,
    session: Session = Depends(get_session),
) -> list[AuditLog]:
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    stmt = select(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if target_type:
        stmt = stmt.where(AuditLog.target_type == target_type)
    total = session.scalar(select(func.count()).select_from(stmt.subquery()))
    if response is not None:
        response.headers["X-Total-Count"] = str(total)
    return list(
        session.scalars(
            stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .limit(limit)
            .offset(offset)
        ).all()
    )
