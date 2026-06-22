from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from xhs_health.db import get_session
from xhs_health.models import AuditLog
from xhs_health.schemas import AuditLogOut


router = APIRouter()


@router.get("", response_model=list[AuditLogOut])
def list_audit_logs(limit: int = 100, session: Session = Depends(get_session)) -> list[AuditLog]:
    limit = max(1, min(limit, 500))
    return list(
        session.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)).all()
    )
