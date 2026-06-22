import csv
from io import BytesIO, StringIO

from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import HTTPException
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from xhs_health.db import get_session
from xhs_health.models import Account, AccountDailySnapshot, Alert, Note, NoteDailyMetric, Score


router = APIRouter()


def _latest_score_query(account_id: int):
    return (
        select(Score)
        .where(Score.account_id == account_id)
        .order_by(Score.score_date.desc(), Score.created_at.desc())
    )


@router.get("/accounts.csv")
def export_accounts_report(session: Session = Depends(get_session)) -> StreamingResponse:
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "account_id",
            "platform_uid",
            "nickname",
            "category",
            "status",
            "latest_score",
            "health_level",
            "confidence_level",
            "score_date",
            "unresolved_alerts",
        ]
    )
    accounts = list(session.scalars(select(Account).order_by(Account.id.asc())).all())
    for account in accounts:
        latest_score = session.scalar(_latest_score_query(account.id))
        unresolved_alerts = (
            session.scalar(
                select(func.count())
                .select_from(Alert)
                .where(Alert.account_id == account.id, Alert.is_resolved.is_(False))
            )
            or 0
        )
        writer.writerow(
            [
                account.id,
                account.platform_uid,
                account.nickname,
                account.category or "",
                account.status,
                f"{float(latest_score.total_score):.2f}" if latest_score else "",
                latest_score.health_level if latest_score else "",
                latest_score.confidence_level if latest_score else "",
                latest_score.score_date.isoformat() if latest_score else "",
                unresolved_alerts,
            ]
        )

    buffer.seek(0)
    headers = {"Content-Disposition": 'attachment; filename="xhs-health-accounts.csv"'}
    return StreamingResponse(iter([buffer.getvalue()]), media_type="text/csv", headers=headers)


@router.get("/accounts.xlsx")
def export_accounts_xlsx_report(session: Session = Depends(get_session)) -> StreamingResponse:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "accounts"
    sheet.append(
        [
            "account_id",
            "platform_uid",
            "nickname",
            "category",
            "status",
            "latest_score",
            "health_level",
            "confidence_level",
            "score_date",
            "unresolved_alerts",
        ]
    )
    for account in session.scalars(select(Account).order_by(Account.id.asc())):
        latest_score = session.scalar(_latest_score_query(account.id))
        unresolved_alerts = (
            session.scalar(
                select(func.count())
                .select_from(Alert)
                .where(Alert.account_id == account.id, Alert.is_resolved.is_(False))
            )
            or 0
        )
        sheet.append(
            [
                account.id,
                account.platform_uid,
                account.nickname,
                account.category or "",
                account.status,
                float(latest_score.total_score) if latest_score else None,
                latest_score.health_level if latest_score else "",
                latest_score.confidence_level if latest_score else "",
                latest_score.score_date.isoformat() if latest_score else "",
                unresolved_alerts,
            ]
        )
    for column_cells in sheet.columns:
        max_length = max(len(str(cell.value or "")) for cell in column_cells)
        sheet.column_dimensions[column_cells[0].column_letter].width = min(max_length + 2, 32)

    output = BytesIO()
    workbook.save(output)
    headers = {"Content-Disposition": 'attachment; filename="xhs-health-accounts.xlsx"'}
    media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return StreamingResponse(iter([output.getvalue()]), media_type=media_type, headers=headers)


@router.get("/accounts/{account_id}.json")
def export_single_account_report(
    account_id: int, session: Session = Depends(get_session)
) -> dict[str, object]:
    account = session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="account not found")
    latest_score = session.scalar(_latest_score_query(account_id))
    score_history = list(
        session.scalars(
            select(Score).where(Score.account_id == account_id).order_by(Score.score_date.desc())
        ).all()
    )
    snapshots = list(
        session.scalars(
            select(AccountDailySnapshot)
            .where(AccountDailySnapshot.account_id == account_id)
            .order_by(AccountDailySnapshot.data_date.desc())
        ).all()
    )
    notes = list(
        session.scalars(select(Note).where(Note.account_id == account_id).order_by(Note.id.asc())).all()
    )
    note_metrics = list(
        session.scalars(
            select(NoteDailyMetric)
            .where(NoteDailyMetric.account_id == account_id)
            .order_by(NoteDailyMetric.data_date.desc())
        ).all()
    )
    alerts = list(
        session.scalars(
            select(Alert).where(Alert.account_id == account_id).order_by(Alert.created_at.desc())
        ).all()
    )
    suggestions = []
    if latest_score:
        suggestions = list(latest_score.details_json.get("suggestions", []))
    return jsonable_encoder(
        {
            "account": account,
            "latest_score": latest_score,
            "score_history": score_history,
            "snapshots": snapshots,
            "notes": notes,
            "note_metrics": note_metrics,
            "alerts": alerts,
            "summary": {
                "unresolved_alerts": len([alert for alert in alerts if not alert.is_resolved]),
                "missing_fields": latest_score.missing_fields if latest_score else [],
                "warning_flags": latest_score.warning_flags if latest_score else [],
                "suggestions": suggestions,
            },
        }
    )
