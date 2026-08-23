from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from xhs_health.db import get_session
from xhs_health.models import AuditLog, NotificationChannel, NotificationDelivery
from xhs_health.schemas import (
    NotificationChannelCreate,
    NotificationChannelOut,
    NotificationChannelUpdate,
    NotificationDeliveryOut,
    NotificationTestRequest,
)


router = APIRouter()


def _audit(
    session: Session,
    action: str,
    target_type: str,
    target_id: str | int,
    detail: dict[str, Any] | None = None,
) -> None:
    session.add(
        AuditLog(
            action=action,
            target_type=target_type,
            target_id=str(target_id),
            detail=detail or {},
        )
    )


@router.get("/channels", response_model=list[NotificationChannelOut])
def list_notification_channels(
    limit: int = 100, session: Session = Depends(get_session)
) -> list[NotificationChannel]:
    limit = max(1, min(limit, 500))
    return list(
        session.scalars(
            select(NotificationChannel)
            .order_by(NotificationChannel.created_at.desc(), NotificationChannel.id.desc())
            .limit(limit)
        ).all()
    )


@router.post("/channels", response_model=NotificationChannelOut)
def create_notification_channel(
    payload: NotificationChannelCreate, session: Session = Depends(get_session)
) -> NotificationChannel:
    existing = session.scalar(select(NotificationChannel).where(NotificationChannel.name == payload.name))
    if existing:
        raise HTTPException(status_code=409, detail="notification channel name already exists")
    channel = NotificationChannel(**payload.model_dump())
    session.add(channel)
    session.flush()
    _audit(
        session,
        action="notification_channel.created",
        target_type="notification_channel",
        target_id=channel.id,
        detail={"channel_type": channel.channel_type},
    )
    session.commit()
    session.refresh(channel)
    return channel


@router.put("/channels/{channel_id}", response_model=NotificationChannelOut)
def update_notification_channel(
    channel_id: int,
    payload: NotificationChannelUpdate,
    session: Session = Depends(get_session),
) -> NotificationChannel:
    channel = session.get(NotificationChannel, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="notification channel not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(channel, field, value)
    _audit(
        session,
        action="notification_channel.updated",
        target_type="notification_channel",
        target_id=channel.id,
    )
    session.commit()
    session.refresh(channel)
    return channel


@router.get("/deliveries", response_model=list[NotificationDeliveryOut])
def list_notification_deliveries(
    limit: int = 50, session: Session = Depends(get_session)
) -> list[NotificationDelivery]:
    limit = max(1, min(limit, 200))
    return list(
        session.scalars(
            select(NotificationDelivery)
            .order_by(NotificationDelivery.created_at.desc(), NotificationDelivery.id.desc())
            .limit(limit)
        ).all()
    )


@router.post("/channels/{channel_id}/test", response_model=NotificationDeliveryOut)
def test_notification_channel(
    channel_id: int,
    payload: NotificationTestRequest,
    session: Session = Depends(get_session),
) -> NotificationDelivery:
    """Test-fire a notification channel.

    STUB: in MVP this only records the delivery row; no real webhook/email/IM
    transport is wired. Once a transport implementation is added, replace the
    status logic below with the real send-then-record flow.
    """
    channel = session.get(NotificationChannel, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="notification channel not found")

    status = "dry_run"
    error_message = None
    if not channel.enabled:
        status = "skipped"
        error_message = "channel disabled"
    elif not channel.target:
        status = "skipped"
        error_message = "channel target not configured"
    elif not payload.dry_run:
        # Until a real transport is wired, even non-dry-run requests are recorded as stub.
        status = "stub"
        error_message = "real transport not implemented; recorded only"

    delivery_payload = {
        "channel": {
            "name": channel.name,
            "channel_type": channel.channel_type,
            "target": channel.target,
        },
        "event": payload.event_type,
        "payload": payload.payload or {"message": "XHS health notification test"},
    }
    delivery = NotificationDelivery(
        channel_id=channel.id,
        event_type=payload.event_type,
        target=channel.target,
        status=status,
        payload=delivery_payload,
        error_message=error_message,
    )
    session.add(delivery)
    session.flush()
    _audit(
        session,
        action="notification_delivery.tested",
        target_type="notification_channel",
        target_id=channel.id,
        detail={"delivery_id": delivery.id, "status": status},
    )
    session.commit()
    session.refresh(delivery)
    return delivery
