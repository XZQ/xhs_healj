from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


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


class AccountOut(AccountCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    group_ids: list[int] = Field(default_factory=list)


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


class AlertRuleUpdate(BaseModel):
    name: str | None = None
    alert_type: str | None = None
    metric_name: str | None = None
    operator: Literal["lt", "lte", "gt", "gte", "eq"] | None = None
    threshold_value: float | None = None
    severity: Literal["info", "warning", "critical"] | None = None
    enabled: bool | None = None
    cooldown_minutes: int | None = None


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


class NotificationChannelUpdate(BaseModel):
    name: str | None = None
    channel_type: Literal["email", "webhook", "feishu", "dingtalk", "wecom"] | None = None
    target: str | None = None
    enabled: bool | None = None
    config: dict[str, Any] | None = None


class NotificationChannelOut(NotificationChannelCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class NotificationTestRequest(BaseModel):
    event_type: str = "health_alert"
    dry_run: bool = True
    payload: dict[str, Any] = Field(default_factory=dict)


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
