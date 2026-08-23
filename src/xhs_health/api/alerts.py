from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from xhs_health.db import get_session
from xhs_health.models import Alert, AlertRule
from xhs_health.schemas import AlertOut, AlertRuleCreate, AlertRuleOut, AlertRuleUpdate


router = APIRouter()


@router.get("", response_model=list[AlertOut])
def list_alerts(
    account_id: int | None = None,
    unresolved_only: bool = False,
    limit: int = 100,
    offset: int = 0,
    response: Response = None,
    session: Session = Depends(get_session),
) -> list[Alert]:
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    stmt = select(Alert)
    if account_id is not None:
        stmt = stmt.where(Alert.account_id == account_id)
    if unresolved_only:
        stmt = stmt.where(Alert.is_resolved.is_(False))
    total = session.scalar(select(func.count()).select_from(stmt.subquery()))
    if response is not None:
        response.headers["X-Total-Count"] = str(total)
    return list(
        session.scalars(
            stmt.order_by(Alert.created_at.desc(), Alert.id.desc()).limit(limit).offset(offset)
        ).all()
    )


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
    if payload.name is not None and payload.name != rule.name:
        clash = session.scalar(
            select(AlertRule).where(AlertRule.name == payload.name, AlertRule.id != rule_id)
        )
        if clash:
            raise HTTPException(status_code=409, detail="alert rule name already exists")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)
    session.commit()
    session.refresh(rule)
    return rule
