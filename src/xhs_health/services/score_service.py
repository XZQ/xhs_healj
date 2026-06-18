from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from xhs_health.models import Account, AccountDailySnapshot, Alert, Note, NoteDailyMetric, Score
from xhs_health.services.scoring import MODEL_VERSION, HealthScoreEngine


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value


def _row_dict(obj: Any, keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: _jsonable(getattr(obj, key)) for key in keys}


def calculate_and_store_score(
    session: Session, account_id: int, score_date: date | None = None
) -> Score:
    account = session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="account not found")

    snapshots = list(
        session.scalars(
            select(AccountDailySnapshot)
            .where(AccountDailySnapshot.account_id == account_id)
            .order_by(AccountDailySnapshot.data_date.asc())
        ).all()
    )
    if not snapshots:
        raise HTTPException(status_code=400, detail="account has no snapshots")

    target_date = score_date or snapshots[-1].data_date
    notes = _latest_note_metrics(session, account_id)
    account_data = _row_dict(
        account,
        (
            "violation_count_180d",
            "ad_compliance_rate",
            "audit_pass_rate",
            "shadowban_risk",
            "fan_quality_score",
            "cpe",
            "avg_cpe_benchmark",
            "business_stability",
        ),
    )
    snapshot_data = [
        _row_dict(
            item,
            (
                "data_date",
                "fans_count",
                "fans_delta",
                "notes_count",
                "total_reads",
                "total_likes",
                "total_collects",
                "total_comments",
                "total_shares",
                "publish_count",
            ),
        )
        for item in snapshots
    ]

    result = HealthScoreEngine().calculate(account_data, snapshot_data, notes)
    dims = result.dimensions
    existing = session.scalar(
        select(Score).where(
            Score.account_id == account_id,
            Score.score_date == target_date,
            Score.model_version == MODEL_VERSION,
        )
    )
    score_data = {
        "account_id": account_id,
        "score_date": target_date,
        "total_score": result.total_score,
        "data_score": dims["data"].final_score,
        "content_score": dims["content"].final_score,
        "compliance_score": dims["compliance"].final_score,
        "conversion_score": dims["conversion"].final_score,
        "health_level": result.health_level,
        "model_version": result.model_version,
        "data_completeness": result.data_completeness,
        "confidence_level": result.confidence_level,
        "details_json": _jsonable(result.to_dict()),
        "missing_fields": result.missing_fields,
        "warning_flags": result.warning_flags,
    }

    if existing is None:
        score = Score(**score_data)
        session.add(score)
    else:
        score = existing
        for key, value in score_data.items():
            setattr(score, key, value)
    session.flush()
    _refresh_score_alerts(session, account, score, result.warning_flags)
    return score


def _latest_note_metrics(session: Session, account_id: int) -> list[dict[str, Any]]:
    notes = list(session.scalars(select(Note).where(Note.account_id == account_id)).all())
    output = []
    for note in notes:
        metric = session.scalar(
            select(NoteDailyMetric)
            .where(NoteDailyMetric.note_id == note.note_id)
            .order_by(NoteDailyMetric.data_date.desc())
        )
        if metric is None:
            output.append(
                {
                    "note_id": note.note_id,
                    "is_original": note.is_original,
                    "tags": note.tags,
                }
            )
            continue
        row = _row_dict(
            metric,
            (
                "note_id",
                "read_count",
                "like_count",
                "collect_count",
                "comment_count",
                "share_count",
                "interaction_rate",
                "cqi",
            ),
        )
        row["is_original"] = note.is_original
        row["tags"] = note.tags
        output.append(row)
    return output


def _refresh_score_alerts(
    session: Session, account: Account, score: Score, warning_flags: list[str]
) -> None:
    session.execute(
        delete(Alert).where(
            Alert.account_id == account.id,
            Alert.alert_type.in_(["low_score", "low_confidence"]),
            Alert.is_resolved.is_(False),
        )
    )
    if float(score.total_score) < 55:
        session.add(
            Alert(
                account_id=account.id,
                alert_type="low_score",
                severity="critical",
                title=f"{account.nickname} 健康评分低于阈值",
                message=f"当前健康评分为 {float(score.total_score):.2f}，建议尽快排查。",
                metric_name="total_score",
                current_value=score.total_score,
                threshold_value=55,
            )
        )
    if "low_confidence" in warning_flags:
        session.add(
            Alert(
                account_id=account.id,
                alert_type="low_confidence",
                severity="warning",
                title=f"{account.nickname} 评分置信度较低",
                message="关键数据缺失较多，当前评分不建议用于高风险决策。",
                metric_name="data_completeness",
                current_value=score.data_completeness,
                threshold_value=0.6,
            )
        )

