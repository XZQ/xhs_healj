from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from xhs_health.db import get_session
from xhs_health.models import Alert
from xhs_health.schemas import AlertOut


router = APIRouter()


@router.get("", response_model=list[AlertOut])
def list_alerts(session: Session = Depends(get_session)) -> list[Alert]:
    return list(session.scalars(select(Alert).order_by(Alert.created_at.desc())).all())


@router.put("/{alert_id}/resolve", response_model=AlertOut)
def resolve_alert(alert_id: int, session: Session = Depends(get_session)) -> Alert:
    alert = session.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="alert not found")
    alert.is_resolved = True
    alert.resolved_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(alert)
    return alert
