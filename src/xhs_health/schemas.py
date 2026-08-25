import math
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator


def _require_finite(value: float, field_name: str) -> float:
    # NaN/Infinity arrive as real floats here: Python's json module parses the
    # bare NaN/Infinity tokens. NaN cannot bind to a NOT NULL Numeric column
    # (500) and Infinity silently makes "lt Infinity" rules always fire.
    if value is not None and not math.isfinite(value):
        raise ValueError(f"{field_name} must be a finite number")
    return value


def _require_finite_json(value: Any, field_name: str, path: str = "") -> Any:
    """Recursively reject non-finite floats inside user-supplied JSON blobs
    (they land verbatim in JSON columns and distort on read-back)."""
    where = path or field_name
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{where} must be a finite number")
    elif isinstance(value, dict):
        for key, item in value.items():
            _require_finite_json(item, field_name, f"{where}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _require_finite_json(item, field_name, f"{where}[{index}]")
    return value


class AccountCreate(BaseModel):
    platform_uid: str
    nickname: str
    avatar_url: str | None = None
    category: str | None = None
    tags: list[str] = Field(default_factory=list)


class AccountUpdate(BaseModel):
    nickname: str | None = None
    avatar_url: str | None = None
    category: str | None = None
    tags: list[str] | None = None
    status: Literal["active", "paused", "archived"] | None = None

    @field_validator("nickname", "tags", "status")
    @classmethod
    def _required_fields_not_null(cls, value: Any, info: ValidationInfo) -> Any:
        if value is None:
            raise ValueError(f"{info.field_name} cannot be null")
        return value


class AccountOut(AccountCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    group_ids: list[int] = Field(default_factory=list)
    latest_score: "ScoreOut | None" = None


class AccountSnapshotIn(BaseModel):
    data_date: date
    fans_count: int | None = None
    fans_delta: int | None = None
    notes_count: int | None = None
    total_reads: int | None = None
    total_likes: int | None = None
    total_collects: int | None = None
    total_comments: int | None = None
    total_shares: int | None = None
    publish_count: int | None = None
    data_source: str = "manual"


class NoteMetricIn(BaseModel):
    data_date: date
    read_count: int | None = None
    like_count: int | None = None
    collect_count: int | None = None
    comment_count: int | None = None
    share_count: int | None = None
    data_source: str = "manual"


class NoteImportIn(BaseModel):
    note_id: str
    title: str | None = None
    content_type: str = "image"
    publish_time: datetime | None = None
    is_ad: bool = False
    is_original: bool = True
    tags: list[str] = Field(default_factory=list)
    metrics: list[NoteMetricIn] = Field(default_factory=list)


class AccountImportIn(AccountCreate):
    violation_count_180d: int | None = None
    ad_compliance_rate: float | None = None
    audit_pass_rate: float | None = None
    shadowban_risk: float | None = None
    fan_quality_score: float | None = None
    cpe: float | None = None
    avg_cpe_benchmark: float | None = None
    business_stability: float | None = None
    snapshots: list[AccountSnapshotIn] = Field(default_factory=list)
    notes: list[NoteImportIn] = Field(default_factory=list)


# Tuple-like alias for (field_name, message) pairs used by import validation.
ValidationError = tuple[str, str]


def _in_range(value: float | None, low: float, high: float) -> bool:
    return value is None or low <= value <= high


# Cumulative counters: negative values are always bad input (fans_delta is NOT
# here — losing fans is legitimate and must be scored, not rejected).
SNAPSHOT_COUNTER_FIELDS = (
    "notes_count",
    "total_reads",
    "total_likes",
    "total_collects",
    "total_comments",
    "total_shares",
)
NOTE_METRIC_COUNTER_FIELDS = (
    "read_count",
    "like_count",
    "collect_count",
    "comment_count",
    "share_count",
)


def validate_import_payload(payload: AccountImportIn) -> list[ValidationError]:
    """Business-rule checks layered on top of pydantic type validation."""
    errors: list[ValidationError] = []
    if not (payload.platform_uid or "").strip():
        errors.append(("platform_uid", "platform_uid is required"))
    if not (payload.nickname or "").strip():
        errors.append(("nickname", "nickname is required"))
    if payload.violation_count_180d is not None and payload.violation_count_180d < 0:
        errors.append(("violation_count_180d", "must be >= 0"))
    for field_name in (
        "ad_compliance_rate",
        "audit_pass_rate",
        "shadowban_risk",
        "fan_quality_score",
        "business_stability",
    ):
        value = getattr(payload, field_name)
        if not _in_range(value, 0.0, 1.0):
            errors.append((field_name, f"{field_name} must be between 0 and 1"))
    for field_name in ("cpe", "avg_cpe_benchmark"):
        # NaN/inf pass "< 0" checks (comparisons are False) but poison scores;
        # Python's json module happily parses NaN/Infinity tokens.
        value = getattr(payload, field_name)
        if value is not None and not math.isfinite(value):
            errors.append((field_name, f"{field_name} must be a finite number"))
        elif value is not None and value < 0:
            errors.append((field_name, f"{field_name} must be >= 0"))
    for snapshot in payload.snapshots:
        if snapshot.fans_count is not None and snapshot.fans_count < 0:
            errors.append(("fans_count", "fans_count must be >= 0"))
        if snapshot.publish_count is not None and snapshot.publish_count < 0:
            errors.append(("publish_count", "publish_count must be >= 0"))
        for field_name in SNAPSHOT_COUNTER_FIELDS:
            value = getattr(snapshot, field_name)
            if value is not None and value < 0:
                errors.append((field_name, f"{field_name} must be >= 0"))
    for note in payload.notes:
        for metric in note.metrics:
            for field_name in NOTE_METRIC_COUNTER_FIELDS:
                value = getattr(metric, field_name)
                if value is not None and value < 0:
                    errors.append((field_name, f"{field_name} must be >= 0"))
    return errors


class ImportAccountsRequest(BaseModel):
    accounts: list[AccountImportIn]


class ImportAccountsResponse(BaseModel):
    accounts_upserted: int
    snapshots_upserted: int
    notes_upserted: int
    note_metrics_upserted: int
    import_batch_id: int | None = None
    total_rows: int | None = None
    error_rows: int = 0


class TriggerScoreRequest(BaseModel):
    account_id: int
    score_date: date | None = None


class BatchTriggerScoreRequest(BaseModel):
    account_ids: list[int] | None = None
    score_date: date | None = None


class ScoreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    score_date: date
    total_score: float
    data_score: float | None
    content_score: float | None
    compliance_score: float | None
    conversion_score: float | None
    health_level: str
    model_version: str
    data_completeness: float | None
    confidence_level: str | None
    details_json: dict[str, Any]
    missing_fields: list[str]
    warning_flags: list[str]


AccountOut.model_rebuild()


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    alert_type: str
    severity: str
    title: str
    message: str | None
    metric_name: str | None
    current_value: float | None
    threshold_value: float | None
    is_resolved: bool
    created_at: datetime


class AccountGroupCreate(BaseModel):
    name: str
    description: str | None = None


class AccountGroupOut(AccountGroupCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_ids: list[int] = Field(default_factory=list)
    created_at: datetime


class AccountGroupMembershipRequest(BaseModel):
    account_ids: list[int]


class AlertRuleCreate(BaseModel):
    name: str
    alert_type: str
    metric_name: str
    operator: Literal["lt", "lte", "gt", "gte", "eq"] = "lt"
    threshold_value: float
    severity: Literal["info", "warning", "critical"] = "warning"
    enabled: bool = True
    cooldown_minutes: int = 1440

    @field_validator("threshold_value")
    @classmethod
    def _threshold_finite(cls, value: float) -> float:
        return _require_finite(value, "threshold_value")


class AlertRuleUpdate(BaseModel):
    name: str | None = None
    alert_type: str | None = None
    metric_name: str | None = None
    operator: Literal["lt", "lte", "gt", "gte", "eq"] | None = None
    threshold_value: float | None = None
    severity: Literal["info", "warning", "critical"] | None = None
    enabled: bool | None = None
    cooldown_minutes: int | None = None

    @field_validator(
        "name",
        "alert_type",
        "metric_name",
        "operator",
        "severity",
        "enabled",
        "cooldown_minutes",
    )
    @classmethod
    def _required_fields_not_null(cls, value: Any, info: ValidationInfo) -> Any:
        if value is None:
            raise ValueError(f"{info.field_name} cannot be null")
        return value

    @field_validator("threshold_value")
    @classmethod
    def _threshold_finite(cls, value: float | None) -> float | None:
        # Explicit null reaches setattr and violates the NOT NULL column at
        # commit (500); "absent" never enters this validator thanks to exclude_unset.
        if value is None:
            raise ValueError("threshold_value cannot be null")
        return _require_finite(value, "threshold_value")


class AlertRuleOut(AlertRuleCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class ImportBatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    total_rows: int
    valid_rows: int
    error_rows: int
    status: str
    created_at: datetime


class ImportErrorRowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    batch_id: int
    row_number: int
    field_name: str
    message: str
    raw_payload: dict[str, Any]
    created_at: datetime


class DataSourceVerificationCreate(BaseModel):
    source: str
    interface_name: str | None = None
    auth_method: str | None = None
    authorization_subject: str | None = None
    requires_creator_authorization: bool = True
    available_fields: list[str] = Field(default_factory=list)
    rate_limit: str | None = None
    history_range: str | None = None
    commercial_usage: str | None = None
    fallback_strategy: str | None = None
    status: Literal["pending", "verified", "blocked", "rejected"] = "pending"
    notes: str | None = None


class DataSourceVerificationOut(DataSourceVerificationCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class AccountAuthorizationCreate(BaseModel):
    authorization_type: Literal["manual", "oauth", "contract", "platform"] = "manual"
    authorized_by: str | None = None
    scope: dict[str, Any] = Field(default_factory=dict)
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    proof_url: str | None = None

    @field_validator("scope")
    @classmethod
    def _scope_finite(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _require_finite_json(value, "scope")


class AccountAuthorizationOut(AccountAuthorizationCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    revoked_at: datetime | None
    created_at: datetime


class AccountDataDeletionRequest(BaseModel):
    mode: Literal["anonymize", "delete"] = "anonymize"
    actor: str | None = None
    reason: str | None = None


class AccountDataActionOut(BaseModel):
    account_id: int
    action: str
    status: str
    deleted_records: dict[str, int] = Field(default_factory=dict)


class NotificationChannelCreate(BaseModel):
    name: str
    channel_type: Literal["email", "webhook", "feishu", "dingtalk", "wecom"]
    target: str | None = None
    enabled: bool = True
    config: dict[str, Any] = Field(default_factory=dict)

    @field_validator("config")
    @classmethod
    def _config_finite(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _require_finite_json(value, "config")


class NotificationChannelUpdate(BaseModel):
    name: str | None = None
    channel_type: Literal["email", "webhook", "feishu", "dingtalk", "wecom"] | None = None
    target: str | None = None
    enabled: bool | None = None
    config: dict[str, Any] | None = None

    @field_validator("name", "channel_type", "enabled")
    @classmethod
    def _required_fields_not_null(cls, value: Any, info: ValidationInfo) -> Any:
        if value is None:
            raise ValueError(f"{info.field_name} cannot be null")
        return value

    @field_validator("config")
    @classmethod
    def _config_finite(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is None:
            # config column is NOT NULL; an explicit null would 500 at commit.
            raise ValueError("config cannot be null")
        return _require_finite_json(value, "config")


class NotificationChannelOut(NotificationChannelCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class NotificationTestRequest(BaseModel):
    event_type: str = "health_alert"
    dry_run: bool = True
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("payload")
    @classmethod
    def _payload_finite(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _require_finite_json(value, "payload")


class NotificationDeliveryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    channel_id: int | None
    event_type: str
    target: str | None
    status: str
    payload: dict[str, Any]
    error_message: str | None
    created_at: datetime


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor: str | None
    action: str
    target_type: str | None
    target_id: str | None
    detail: dict[str, Any]
    created_at: datetime


class OverviewStatsOut(BaseModel):
    monitored_accounts: int
    healthy_accounts: int
    warning_accounts: int
    risky_accounts: int
    low_confidence_accounts: int
    unresolved_alerts: int


class SchedulerStatusOut(BaseModel):
    name: str
    enabled: bool
    interval_seconds: int
    running: bool
    last_started_at: datetime | None
    last_finished_at: datetime | None
    last_status: str
    last_message: str | None
    total_runs: int
    scores_created: int


class XhsIntegrationStatusOut(BaseModel):
    mode: str
    configured: bool
    message: str


class XhsSyncRequest(BaseModel):
    platform_uid: str
