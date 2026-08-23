import csv
from io import BytesIO, StringIO

from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import HTTPException
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from xhs_health.db import get_session
from xhs_health.models import Account, AccountDailySnapshot, Alert, Note, NoteDailyMetric, Score


router = APIRouter()


REPORT_COLUMNS = [
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


def _latest_scores_by_account(session: Session) -> dict[int, Score]:
    """Latest score per account by (score_date, created_at) in one query."""
    sub = (
        select(
            Score.id.label("sid"),
            func.row_number()
            .over(
                partition_by=Score.account_id,
                order_by=[desc(Score.score_date), desc(Score.created_at), desc(Score.id)],
            )
            .label("rn"),
        )
        .subquery()
    )
    rows = (
        session.execute(select(Score).join(sub, Score.id == sub.c.sid).where(sub.c.rn == 1))
        .scalars()
        .all()
    )
    return {row.account_id: row for row in rows}


def _unresolved_alert_counts(session: Session) -> dict[int, int]:
    rows = session.execute(
        select(Alert.account_id, func.count())
        .where(Alert.is_resolved.is_(False))
        .group_by(Alert.account_id)
    ).all()
    return {account_id: int(count) for account_id, count in rows}


@router.get("/accounts.csv")
def export_accounts_report(session: Session = Depends(get_session)) -> StreamingResponse:
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(REPORT_COLUMNS)
    accounts = list(session.scalars(select(Account).order_by(Account.id.asc())).all())
    latest_scores = _latest_scores_by_account(session)
    alert_counts = _unresolved_alert_counts(session)
    for account in accounts:
        latest_score = latest_scores.get(account.id)
        unresolved_alerts = alert_counts.get(account.id, 0)
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
    sheet.append(REPORT_COLUMNS)
    accounts = list(session.scalars(select(Account).order_by(Account.id.asc())).all())
    latest_scores = _latest_scores_by_account(session)
    alert_counts = _unresolved_alert_counts(session)
    for account in accounts:
        latest_score = latest_scores.get(account.id)
        unresolved_alerts = alert_counts.get(account.id, 0)
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
    latest_score = session.scalar(
        select(Score)
        .where(Score.account_id == account_id)
        .order_by(desc(Score.score_date), desc(Score.created_at), desc(Score.id))
    )
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
