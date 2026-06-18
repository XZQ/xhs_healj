from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from xhs_health.db import get_session
from xhs_health.schemas import ImportAccountsRequest, ImportAccountsResponse
from xhs_health.services.imports import import_accounts, import_flat_file


router = APIRouter()


@router.post("/accounts", response_model=ImportAccountsResponse)
def import_account_data(
    payload: ImportAccountsRequest, session: Session = Depends(get_session)
) -> ImportAccountsResponse:
    result = import_accounts(session, payload.accounts)
    session.commit()
    return result


@router.post("/account-metrics-file", response_model=ImportAccountsResponse)
async def import_account_metrics_file(
    file: UploadFile = File(...), session: Session = Depends(get_session)
) -> ImportAccountsResponse:
    content = await file.read()
    result = import_flat_file(session, file.filename or "upload.csv", content)
    session.commit()
    return result
