from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from xhs_health.db import get_session
from xhs_health.models import Alert, AlertRule
from xhs_health.schemas import AlertOut, AlertRuleCreate, AlertRuleOut, AlertRuleUpdate


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


@router.get("/rules", response_model=list[AlertRuleOut])
def list_alert_rules(session: Session = Depends(get_session)) -> list[AlertRule]:
    return list(session.scalars(select(AlertRule).order_by(AlertRule.id.asc())).all())


@router.post("/rules", response_model=AlertRuleOut)
def create_alert_rule(payload: AlertRuleCreate, session: Session = Depends(get_session)) -> AlertRule:
    existing = session.scalar(select(AlertRule).where(AlertRule.name == payload.name))
    if existing:
        raise HTTPException(status_code=409, detail="alert rule name already exists")
    rule = AlertRule(**payload.model_dump())
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


@router.put("/rules/{rule_id}", response_model=AlertRuleOut)
def update_alert_rule(
    rule_id: int, payload: AlertRuleUpdate, session: Session = Depends(get_session)
) -> AlertRule:
    rule = session.get(AlertRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="alert rule not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)
    session.commit()
    session.refresh(rule)
    return rule
