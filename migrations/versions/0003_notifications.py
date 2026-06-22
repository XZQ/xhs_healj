"""notification channels

Revision ID: 0003_notifications
Revises: 0002_mvp_completion_tables
Create Date: 2026-06-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_notifications"
down_revision: Union[str, None] = "0002_mvp_completion_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notification_channels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("channel_type", sa.String(32), nullable=False),
        sa.Column("target", sa.String(512)),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_notification_channels_channel_type", "notification_channels", ["channel_type"])
    op.create_index("ix_notification_channels_enabled", "notification_channels", ["enabled"])

    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("channel_id", sa.Integer(), sa.ForeignKey("notification_channels.id")),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("target", sa.String(512)),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_notification_deliveries_channel_id", "notification_deliveries", ["channel_id"])
    op.create_index("ix_notification_deliveries_event_type", "notification_deliveries", ["event_type"])
    op.create_index("ix_notification_deliveries_status", "notification_deliveries", ["status"])


def downgrade() -> None:
    op.drop_table("notification_deliveries")
    op.drop_table("notification_channels")
