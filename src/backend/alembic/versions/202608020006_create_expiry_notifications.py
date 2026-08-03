"""create expiry notification settings and notifications

Revision ID: 202608020006
Revises: 202608020005
Create Date: 2026-08-02

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "202608020006"
down_revision: str | None = "202608020005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    notification_type = postgresql.ENUM(
        "EXPIRING_SOON",
        "EXPIRED",
        name="expiry_notification_type",
        create_type=False,
    )
    notification_status = postgresql.ENUM(
        "PENDING",
        "SENT",
        "READ",
        "FAILED",
        name="notification_status",
        create_type=False,
    )
    notification_type.create(op.get_bind(), checkfirst=True)
    notification_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "expiry_notification_settings",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "warning_days",
            sa.SmallInteger(),
            server_default=sa.text("3"),
            nullable=False,
        ),
        sa.Column(
            "timezone",
            sa.String(length=64),
            server_default=sa.text("'Asia/Ho_Chi_Minh'"),
            nullable=False,
        ),
        sa.Column(
            "delivery_hour",
            sa.SmallInteger(),
            server_default=sa.text("9"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "delivery_hour BETWEEN 0 AND 23",
            name=op.f(
                "ck_expiry_notification_settings_"
                "expiry_notification_settings_delivery_hour_range"
            ),
        ),
        sa.CheckConstraint(
            "warning_days BETWEEN 1 AND 30",
            name=op.f(
                "ck_expiry_notification_settings_"
                "expiry_notification_settings_warning_days_range"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
            name=op.f("fk_expiry_notification_settings_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "user_id",
            name=op.f("pk_expiry_notification_settings"),
        ),
    )

    op.create_table(
        "notifications",
        sa.Column("notification_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fridge_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("notification_type", notification_type, nullable=False),
        sa.Column("status", notification_status, nullable=False),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("trigger_date", sa.Date(), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["fridge_item_id"],
            ["fridge_items.fridge_item_id"],
            name=op.f("fk_notifications_fridge_item_id_fridge_items"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
            name=op.f("fk_notifications_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "notification_id",
            name=op.f("pk_notifications"),
        ),
        sa.UniqueConstraint(
            "fridge_item_id",
            "notification_type",
            "trigger_date",
            name="uq_notifications_fridge_type_trigger",
        ),
    )
    op.create_index(
        "ix_notifications_user_created",
        "notifications",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_notifications_user_status",
        "notifications",
        ["user_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_user_status", table_name="notifications")
    op.drop_index("ix_notifications_user_created", table_name="notifications")
    op.drop_table("notifications")
    op.drop_table("expiry_notification_settings")

    postgresql.ENUM(
        "PENDING",
        "SENT",
        "READ",
        "FAILED",
        name="notification_status",
        create_type=False,
    ).drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(
        "EXPIRING_SOON",
        "EXPIRED",
        name="expiry_notification_type",
        create_type=False,
    ).drop(op.get_bind(), checkfirst=True)
