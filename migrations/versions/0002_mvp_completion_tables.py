"""mvp completion tables

Revision ID: 0002_mvp_completion_tables
Revises: 0001_initial
Create Date: 2026-06-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_mvp_completion_tables"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "account_groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("description", sa.String(256)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_account_groups_name", "account_groups", ["name"])

    op.create_table(
        "account_group_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("account_groups.id"), nullable=False),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("group_id", "account_id"),
    )
    op.create_index("ix_account_group_members_group_id", "account_group_members", ["group_id"])
    op.create_index("ix_account_group_members_account_id", "account_group_members", ["account_id"])

    op.create_table(
        "alert_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("alert_type", sa.String(64), nullable=False),
        sa.Column("metric_name", sa.String(64), nullable=False),
        sa.Column("operator", sa.String(8), nullable=False),
        sa.Column("threshold_value", sa.Numeric(12, 4), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("cooldown_minutes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_alert_rules_alert_type", "alert_rules", ["alert_type"])
    op.create_index("ix_alert_rules_enabled", "alert_rules", ["enabled"])

    op.create_table(
        "import_batches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("filename", sa.String(256), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False),
        sa.Column("valid_rows", sa.Integer(), nullable=False),
        sa.Column("error_rows", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "import_error_rows",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("batch_id", sa.Integer(), sa.ForeignKey("import_batches.id"), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("field_name", sa.String(64), nullable=False),
        sa.Column("message", sa.String(256), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_import_error_rows_batch_id", "import_error_rows", ["batch_id"])

    op.create_table(
        "data_source_verifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("interface_name", sa.String(128)),
        sa.Column("auth_method", sa.String(64)),
        sa.Column("authorization_subject", sa.String(128)),
        sa.Column("requires_creator_authorization", sa.Boolean(), nullable=False),
        sa.Column("available_fields", sa.JSON(), nullable=False),
        sa.Column("rate_limit", sa.String(128)),
        sa.Column("history_range", sa.String(128)),
        sa.Column("commercial_usage", sa.String(256)),
        sa.Column("fallback_strategy", sa.String(256)),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_data_source_verifications_source", "data_source_verifications", ["source"])
    op.create_index("ix_data_source_verifications_status", "data_source_verifications", ["status"])

    op.create_table(
        "account_authorizations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("authorization_type", sa.String(32), nullable=False),
        sa.Column("authorized_by", sa.String(128)),
        sa.Column("scope", sa.JSON(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("proof_url", sa.String(512)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_account_authorizations_account_id", "account_authorizations", ["account_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor", sa.String(128)),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_type", sa.String(64)),
        sa.Column("target_id", sa.String(64)),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("account_authorizations")
    op.drop_table("data_source_verifications")
    op.drop_table("import_error_rows")
    op.drop_table("import_batches")
    op.drop_table("alert_rules")
    op.drop_table("account_group_members")
    op.drop_table("account_groups")
