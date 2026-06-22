from fastapi import APIRouter, HTTPException

from xhs_health.config import get_settings
from xhs_health.integrations.xhs import XhsConnector, XhsConnectorNotConfigured
from xhs_health.schemas import XhsIntegrationStatusOut, XhsSyncRequest


router = APIRouter()


def _connector() -> XhsConnector:
    return XhsConnector(get_settings().xhs_connector_mode)


@router.get("/xhs/status", response_model=XhsIntegrationStatusOut)
def get_xhs_status() -> XhsIntegrationStatusOut:
    status = _connector().status()
    return XhsIntegrationStatusOut.model_validate(status.__dict__)


@router.post("/xhs/sync")
def sync_xhs_account(payload: XhsSyncRequest) -> dict[str, str]:
    try:
        return _connector().sync_account(payload.platform_uid)
    except XhsConnectorNotConfigured as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
