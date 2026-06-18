from fastapi import APIRouter, Depends, File, Response, UploadFile
from sqlalchemy.orm import Session

from xhs_health.db import get_session
from xhs_health.schemas import ImportAccountsRequest, ImportAccountsResponse
from xhs_health.services.imports import import_accounts, import_flat_file


router = APIRouter()

TEMPLATE_CSV = """platform_uid,nickname,category,data_date,fans_count,fans_delta,notes_count,total_reads,total_likes,total_collects,total_comments,total_shares,publish_count,violation_count_180d,ad_compliance_rate,audit_pass_rate,shadowban_risk,fan_quality_score,cpe,avg_cpe_benchmark,business_stability,note_id,note_title,content_type,is_ad,is_repost,tags,read_count,like_count,collect_count,comment_count,share_count,data_source
demo_001,示例美妆博主,美妆护肤,2026-06-19,52000,320,120,180000,8200,5100,920,310,1,0,1,0.98,0.04,0.72,2.1,3.0,0.86,note_001,夏季护肤清单,image,false,false,"护肤,夏季",30000,1800,1200,180,70,file
"""


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


@router.get("/template")
def download_import_template() -> Response:
    headers = {"Content-Disposition": 'attachment; filename="xhs_health_import_template.csv"'}
    return Response(content=TEMPLATE_CSV, media_type="text/csv; charset=utf-8", headers=headers)
