from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import delete, desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from xhs_health.models import Account, AccountDailySnapshot, Alert, AlertRule, Note, NoteDailyMetric, Score
from xhs_health.services.scoring import (
    DEFAULT_THRESHOLDS,
    MODEL_VERSION,
    HealthScoreEngine,
    ScoreThresholds,
)


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
    session: Session,
    account_id: int,
    score_date: date | None = None,
    thresholds: ScoreThresholds | None = None,
) -> Score:
    thresholds = thresholds or DEFAULT_THRESHOLDS
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
    window_start: date | None = None
    if thresholds.analysis_window_days > 0:
        window_start = target_date - timedelta(days=thresholds.analysis_window_days - 1)
    notes = _latest_note_metrics(session, account_id, window_start)
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

    result = HealthScoreEngine(thresholds=thresholds).calculate(account_data, snapshot_data, notes)
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
        try:
            # Savepoint so a concurrent insert of the same unique key only
            # rolls back this row (API trigger racing the scheduler thread),
            # not the rest of an in-flight batch.
            with session.begin_nested():
                session.add(score)
                session.flush()
        except IntegrityError:
            score = session.scalar(
                select(Score).where(
                    Score.account_id == account_id,
                    Score.score_date == target_date,
                    Score.model_version == MODEL_VERSION,
                )
            )
            if score is None:
                raise
            for key, value in score_data.items():
                setattr(score, key, value)
            session.flush()
    else:
        score = existing
        for key, value in score_data.items():
            setattr(score, key, value)
        session.flush()
    _refresh_score_alerts(session, account, score, result.warning_flags, thresholds)
    return score


def _latest_note_metrics(
    session: Session, account_id: int, window_start: date | None = None
) -> list[dict[str, Any]]:
    notes = list(session.scalars(select(Note).where(Note.account_id == account_id)).all())
    latest_by_note = _latest_metric_per_note(session, account_id)
    output = []
    for note in notes:
        metric = latest_by_note.get(note.note_id)
        if metric is not None and window_start is not None and metric.data_date < window_start:
            # Stale metric: exclude it so historical notes don't feed today's score.
            metric = None
        if metric is None and window_start is not None:
            published = note.publish_time.date() if note.publish_time else None
            if published is None or published < window_start:
                continue
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


def _latest_metric_per_note(
    session: Session, account_id: int
) -> dict[str, NoteDailyMetric]:
    """One query: pick the latest metric per note using a window function."""
    sub = (
        select(
            NoteDailyMetric.id.label("mid"),
            func.row_number()
            .over(
                partition_by=NoteDailyMetric.note_id,
                # id tiebreak: same-day metrics from different sources are legal
                # (the unique key includes data_source); pick the last inserted.
                order_by=[desc(NoteDailyMetric.data_date), desc(NoteDailyMetric.id)],
            )
            .label("rn"),
        )
        .where(NoteDailyMetric.account_id == account_id)
        .subquery()
    )
    rows = (
        session.execute(select(NoteDailyMetric).join(sub, NoteDailyMetric.id == sub.c.mid).where(sub.c.rn == 1))
        .scalars()
        .all()
    )
    return {row.note_id: row for row in rows}


def _refresh_score_alerts(
    session: Session,
    account: Account,
    score: Score,
    warning_flags: list[str],
    thresholds: ScoreThresholds | None = None,
) -> None:
    t = thresholds or DEFAULT_THRESHOLDS
    latest, previous = _latest_snapshots(session, account.id)
    rules = list(session.scalars(select(AlertRule).where(AlertRule.enabled.is_(True))).all())
    generated_types = [
        "low_score",
        "low_confidence",
        "interaction_drop",
        "fan_loss",
        "inactive",
        "shadowban_risk",
    ]
    generated_types.extend(rule.alert_type for rule in rules)
    session.execute(
        delete(Alert).where(
            Alert.account_id == account.id,
            Alert.alert_type.in_(generated_types),
            Alert.is_resolved.is_(False),
        )
    )
    if float(score.total_score) < t.alert_low_score:
        session.add(
            Alert(
                account_id=account.id,
                alert_type="low_score",
                severity="critical",
                title=f"{account.nickname} 健康评分低于阈值",
                message=f"当前健康评分为 {float(score.total_score):.2f}，建议尽快排查。",
                metric_name="total_score",
                current_value=score.total_score,
                threshold_value=t.alert_low_score,
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
                threshold_value=t.confidence_medium_completeness,
            )
        )
    if latest is not None and previous is not None:
        latest_interaction = _snapshot_interaction_rate(latest)
        previous_interaction = _snapshot_interaction_rate(previous)
        if (
            latest_interaction is not None
            and previous_interaction is not None
            and previous_interaction > 0
            and (previous_interaction - latest_interaction) / previous_interaction
            > t.alert_interaction_drop_ratio
        ):
            session.add(
                Alert(
                    account_id=account.id,
                    alert_type="interaction_drop",
                    severity="critical",
                    title=f"{account.nickname} 互动率骤降",
                    message=(
                        f"互动率由 {previous_interaction:.2%} 降至 {latest_interaction:.2%}，"
                        "建议排查内容分发和限流信号。"
                    ),
                    metric_name="interaction_rate",
                    current_value=latest_interaction,
                    threshold_value=previous_interaction * (1 - t.alert_interaction_drop_ratio),
                )
            )

    if latest is not None:
        fans_count = latest.fans_count or 0
        fans_delta = latest.fans_delta
        if (
            fans_count > 0
            and fans_delta is not None
            and fans_delta < 0
            and abs(fans_delta) / fans_count > t.alert_fan_loss_ratio
        ):
            session.add(
                Alert(
                    account_id=account.id,
                    alert_type="fan_loss",
                    severity="warning",
                    title=f"{account.nickname} 粉丝异常流失",
                    message=f"单日粉丝净流失 {abs(fans_delta)}，超过当前粉丝量 1%。",
                    metric_name="fans_delta",
                    current_value=fans_delta,
                    threshold_value=-(fans_count * t.alert_fan_loss_ratio),
                )
            )
        if latest.publish_count is not None and latest.publish_count <= 0:
            recent_publish = session.scalar(
                select(AccountDailySnapshot)
                .where(
                    AccountDailySnapshot.account_id == account.id,
                    AccountDailySnapshot.publish_count > 0,
                )
                .order_by(AccountDailySnapshot.data_date.desc())
            )
            if (
                recent_publish is None
                or (latest.data_date - recent_publish.data_date).days >= t.alert_inactive_days
            ):
                session.add(
                    Alert(
                        account_id=account.id,
                        alert_type="inactive",
                        severity="warning",
                        title=f"{account.nickname} 长期未更新",
                        message=f"最近 {t.alert_inactive_days} 天未检测到发布记录，存在停更风险。",
                        metric_name="publish_count",
                        current_value=0,
                        threshold_value=1,
                    )
                )

    shadowban_risk = account.shadowban_risk
    if shadowban_risk is not None and float(shadowban_risk) > t.alert_shadowban_risk:
        session.add(
            Alert(
                account_id=account.id,
                alert_type="shadowban_risk",
                severity="critical",
                title=f"{account.nickname} 限流风险较高",
                message=f"限流风险指数为 {float(shadowban_risk):.2f}，建议立即排查。",
                metric_name="shadowban_risk",
                current_value=shadowban_risk,
                threshold_value=t.alert_shadowban_risk,
            )
        )

    metric_values = _metric_values(account, score, latest)
    for rule in rules:
        current_value = metric_values.get(rule.metric_name)
        if current_value is None:
            continue
        if _rule_matches(float(current_value), rule.operator, float(rule.threshold_value)):
            session.add(
                Alert(
                    account_id=account.id,
                    alert_type=rule.alert_type,
                    severity=rule.severity,
                    title=f"{account.nickname} 触发告警规则：{rule.name}",
                    message=(
                        f"{rule.metric_name} 当前值 {float(current_value):.4f} "
                        f"{rule.operator} {float(rule.threshold_value):.4f}"
                    ),
                    metric_name=rule.metric_name,
                    current_value=current_value,
                    threshold_value=rule.threshold_value,
                )
            )


def _latest_snapshots(
    session: Session, account_id: int
) -> tuple[AccountDailySnapshot | None, AccountDailySnapshot | None]:
    rows = list(
        session.scalars(
            select(AccountDailySnapshot)
            .where(AccountDailySnapshot.account_id == account_id)
            .order_by(AccountDailySnapshot.data_date.desc())
            .limit(2)
        ).all()
    )
    latest = rows[0] if rows else None
    previous = rows[1] if len(rows) > 1 else None
    return latest, previous


def _snapshot_interaction_rate(snapshot: AccountDailySnapshot) -> float | None:
    reads = snapshot.total_reads
    if not reads or reads <= 0:
        return None
    interactions = sum(
        value or 0
        for value in (
            snapshot.total_likes,
            snapshot.total_collects,
            snapshot.total_comments,
            snapshot.total_shares,
        )
    )
    return interactions / reads


def _metric_values(
    account: Account, score: Score, latest: AccountDailySnapshot | None
) -> dict[str, float | None]:
    values: dict[str, float | None] = {
        "total_score": float(score.total_score),
        "data_completeness": None if score.data_completeness is None else float(score.data_completeness),
        "shadowban_risk": None if account.shadowban_risk is None else float(account.shadowban_risk),
        "ad_compliance_rate": None
        if account.ad_compliance_rate is None
        else float(account.ad_compliance_rate),
        "audit_pass_rate": None if account.audit_pass_rate is None else float(account.audit_pass_rate),
    }
    if latest is not None:
        values.update(
            {
                "fans_count": None if latest.fans_count is None else float(latest.fans_count),
                "fans_delta": None if latest.fans_delta is None else float(latest.fans_delta),
                "publish_count": None if latest.publish_count is None else float(latest.publish_count),
                "interaction_rate": _snapshot_interaction_rate(latest),
            }
        )
    return values


def _rule_matches(value: float, operator: str, threshold: float) -> bool:
    if operator == "lt":
        return value < threshold
    if operator == "lte":
        return value <= threshold
    if operator == "gt":
        return value > threshold
    if operator == "gte":
        return value >= threshold
    if operator == "eq":
        return value == threshold
    return False
