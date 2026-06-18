from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from xhs_health.db import Base


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    platform_uid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    nickname: Mapped[str] = mapped_column(String(128))
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    category: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)

    violation_count_180d: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ad_compliance_rate: Mapped[float | None] = mapped_column(Numeric(8, 6), nullable=True)
    audit_pass_rate: Mapped[float | None] = mapped_column(Numeric(8, 6), nullable=True)
    shadowban_risk: Mapped[float | None] = mapped_column(Numeric(8, 6), nullable=True)
    fan_quality_score: Mapped[float | None] = mapped_column(Numeric(8, 6), nullable=True)
    cpe: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    avg_cpe_benchmark: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    business_stability: Mapped[float | None] = mapped_column(Numeric(8, 6), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    snapshots: Mapped[list["AccountDailySnapshot"]] = relationship(back_populates="account")
    notes: Mapped[list["Note"]] = relationship(back_populates="account")
    scores: Mapped[list["Score"]] = relationship(back_populates="account")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="account")


class AccountDailySnapshot(Base):
    __tablename__ = "account_daily_snapshots"
    __table_args__ = (UniqueConstraint("account_id", "data_date", "data_source"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    data_date: Mapped[date] = mapped_column(Date, index=True)
    fans_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fans_delta: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_reads: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_likes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_collects: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_comments: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_shares: Mapped[int | None] = mapped_column(Integer, nullable=True)
    publish_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    data_source: Mapped[str] = mapped_column(String(64), default="manual")
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    account: Mapped[Account] = relationship(back_populates="snapshots")


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    note_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    content_type: Mapped[str] = mapped_column(String(16), default="image")
    publish_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_ad: Mapped[bool] = mapped_column(Boolean, default=False)
    is_original: Mapped[bool] = mapped_column(Boolean, default=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    account: Mapped[Account] = relationship(back_populates="notes")
    metrics: Mapped[list["NoteDailyMetric"]] = relationship(back_populates="note")


class NoteDailyMetric(Base):
    __tablename__ = "note_daily_metrics"
    __table_args__ = (UniqueConstraint("note_id", "data_date", "data_source"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    note_pk: Mapped[int] = mapped_column(ForeignKey("notes.id"), index=True)
    note_id: Mapped[str] = mapped_column(String(64), index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    data_date: Mapped[date] = mapped_column(Date, index=True)
    read_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    like_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    collect_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comment_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    share_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    interaction_rate: Mapped[float | None] = mapped_column(Numeric(8, 6), nullable=True)
    cqi: Mapped[float | None] = mapped_column(Numeric(8, 6), nullable=True)
    data_source: Mapped[str] = mapped_column(String(64), default="manual")
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    note: Mapped[Note] = relationship(back_populates="metrics")


class Score(Base):
    __tablename__ = "scores"
    __table_args__ = (UniqueConstraint("account_id", "score_date", "model_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    score_date: Mapped[date] = mapped_column(Date, index=True)
    total_score: Mapped[float] = mapped_column(Numeric(5, 2))
    data_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    content_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    compliance_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    conversion_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    health_level: Mapped[str] = mapped_column(String(4))
    model_version: Mapped[str] = mapped_column(String(32), default="rules_v1")
    data_completeness: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    confidence_level: Mapped[str | None] = mapped_column(String(16), nullable=True)
    details_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    missing_fields: Mapped[list[str]] = mapped_column(JSON, default=list)
    warning_flags: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    account: Mapped[Account] = relationship(back_populates="scores")


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    alert_type: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(256))
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metric_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    current_value: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    threshold_value: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    account: Mapped[Account] = relationship(back_populates="alerts")
