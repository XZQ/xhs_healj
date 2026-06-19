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


class OverviewStatsOut(BaseModel):
    monitored_accounts: int
    healthy_accounts: int
    warning_accounts: int
    risky_accounts: int
    low_confidence_accounts: int
    unresolved_alerts: int
