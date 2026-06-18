from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from xhs_health.db import get_session
from xhs_health.models import Alert
from xhs_health.schemas import AlertOut


router = APIRouter()


@router.get("", response_model=list[AlertOut])
def list_alerts(session: Session = Depends(get_session)) -> list[Alert]:
    return list(session.scalars(select(Alert).order_by(Alert.created_at.desc())).all())

