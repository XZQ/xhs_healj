from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from xhs_health.db import get_session
from xhs_health.models import DataSourceVerification
from xhs_health.schemas import DataSourceVerificationCreate, DataSourceVerificationOut


router = APIRouter()


@router.get("/verifications", response_model=list[DataSourceVerificationOut])
def list_data_source_verifications(
    session: Session = Depends(get_session),
) -> list[DataSourceVerification]:
    return list(
        session.scalars(
            select(DataSourceVerification).order_by(DataSourceVerification.created_at.desc())
        ).all()
    )


@router.post("/verifications", response_model=DataSourceVerificationOut)
def create_data_source_verification(
    payload: DataSourceVerificationCreate,
    session: Session = Depends(get_session),
) -> DataSourceVerification:
    item = DataSourceVerification(**payload.model_dump())
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.put("/verifications/{verification_id}", response_model=DataSourceVerificationOut)
def update_data_source_verification(
    verification_id: int,
    payload: DataSourceVerificationCreate,
    session: Session = Depends(get_session),
) -> DataSourceVerification:
    item = session.get(DataSourceVerification, verification_id)
    if not item:
        raise HTTPException(status_code=404, detail="data source verification not found")
    for field, value in payload.model_dump().items():
        setattr(item, field, value)
    session.commit()
    session.refresh(item)
    return item
