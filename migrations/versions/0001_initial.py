"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("platform_uid", sa.String(64), nullable=False),
        sa.Column("nickname", sa.String(128), nullable=False),
        sa.Column("avatar_url", sa.String(512)),
        sa.Column("category", sa.String(64)),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("violation_count_180d", sa.Integer()),
        sa.Column("ad_compliance_rate", sa.Numeric(8, 6)),
        sa.Column("audit_pass_rate", sa.Numeric(8, 6)),
        sa.Column("shadowban_risk", sa.Numeric(8, 6)),
        sa.Column("fan_quality_score", sa.Numeric(8, 6)),
        sa.Column("cpe", sa.Numeric(12, 4)),
        sa.Column("avg_cpe_benchmark", sa.Numeric(12, 4)),
        sa.Column("business_stability", sa.Numeric(8, 6)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("platform_uid"),
    )
    op.create_index("ix_accounts_category", "accounts", ["category"])
    op.create_index("ix_accounts_platform_uid", "accounts", ["platform_uid"])
    op.create_index("ix_accounts_status", "accounts", ["status"])

    op.create_table(
        "account_daily_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("data_date", sa.Date(), nullable=False),
        sa.Column("fans_count", sa.Integer()),
        sa.Column("fans_delta", sa.Integer()),
        sa.Column("notes_count", sa.Integer()),
        sa.Column("total_reads", sa.Integer()),
        sa.Column("total_likes", sa.Integer()),
        sa.Column("total_collects", sa.Integer()),
        sa.Column("total_comments", sa.Integer()),
        sa.Column("total_shares", sa.Integer()),
        sa.Column("publish_count", sa.Integer()),
        sa.Column("data_source", sa.String(64), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("account_id", "data_date", "data_source"),
    )
    op.create_index("ix_account_daily_snapshots_account_id", "account_daily_snapshots", ["account_id"])
    op.create_index("ix_account_daily_snapshots_data_date", "account_daily_snapshots", ["data_date"])

    op.create_table(
        "notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("note_id", sa.String(64), nullable=False),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("title", sa.String(512)),
        sa.Column("content_type", sa.String(16), nullable=False),
        sa.Column("publish_time", sa.DateTime(timezone=True)),
        sa.Column("is_ad", sa.Boolean(), nullable=False),
        sa.Column("is_original", sa.Boolean(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("note_id"),
    )
    op.create_index("ix_notes_account_id", "notes", ["account_id"])
    op.create_index("ix_notes_note_id", "notes", ["note_id"])

    op.create_table(
        "note_daily_metrics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("note_pk", sa.Integer(), sa.ForeignKey("notes.id"), nullable=False),
        sa.Column("note_id", sa.String(64), nullable=False),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("data_date", sa.Date(), nullable=False),
        sa.Column("read_count", sa.Integer()),
        sa.Column("like_count", sa.Integer()),
        sa.Column("collect_count", sa.Integer()),
        sa.Column("comment_count", sa.Integer()),
        sa.Column("share_count", sa.Integer()),
        sa.Column("interaction_rate", sa.Numeric(8, 6)),
        sa.Column("cqi", sa.Numeric(8, 6)),
        sa.Column("data_source", sa.String(64), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("note_id", "data_date", "data_source"),
    )
    op.create_index("ix_note_daily_metrics_account_id", "note_daily_metrics", ["account_id"])
    op.create_index("ix_note_daily_metrics_data_date", "note_daily_metrics", ["data_date"])
    op.create_index("ix_note_daily_metrics_note_id", "note_daily_metrics", ["note_id"])
    op.create_index("ix_note_daily_metrics_note_pk", "note_daily_metrics", ["note_pk"])

    op.create_table(
        "scores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("score_date", sa.Date(), nullable=False),
        sa.Column("total_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("data_score", sa.Numeric(5, 2)),
        sa.Column("content_score", sa.Numeric(5, 2)),
        sa.Column("compliance_score", sa.Numeric(5, 2)),
        sa.Column("conversion_score", sa.Numeric(5, 2)),
        sa.Column("health_level", sa.String(4), nullable=False),
        sa.Column("model_version", sa.String(32), nullable=False),
        sa.Column("data_completeness", sa.Numeric(5, 4)),
        sa.Column("confidence_level", sa.String(16)),
        sa.Column("details_json", sa.JSON(), nullable=False),
        sa.Column("missing_fields", sa.JSON(), nullable=False),
        sa.Column("warning_flags", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("account_id", "score_date", "model_version"),
    )
    op.create_index("ix_scores_account_id", "scores", ["account_id"])
    op.create_index("ix_scores_score_date", "scores", ["score_date"])

    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("alert_type", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("message", sa.Text()),
        sa.Column("metric_name", sa.String(64)),
        sa.Column("current_value", sa.Numeric(12, 4)),
        sa.Column("threshold_value", sa.Numeric(12, 4)),
        sa.Column("is_resolved", sa.Boolean(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_alerts_account_id", "alerts", ["account_id"])
    op.create_index("ix_alerts_is_resolved", "alerts", ["is_resolved"])


def downgrade() -> None:
    op.drop_table("alerts")
    op.drop_table("scores")
    op.drop_table("note_daily_metrics")
    op.drop_table("notes")
    op.drop_table("account_daily_snapshots")
    op.drop_table("accounts")

