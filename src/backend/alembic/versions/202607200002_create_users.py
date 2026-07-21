"""create users

Revision ID: 202607200002
Revises: 202607200001
Create Date: 2026-07-20

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "202607200002"
down_revision: str | None = "202607200001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    user_status = postgresql.ENUM(
        "ACTIVE",
        "DISABLED",
        name="user_status",
        create_type=False,
    )
    user_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("authentik_sub", sa.String(length=255), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("status", user_status, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_users")),
        sa.UniqueConstraint("authentik_sub", name=op.f("uq_users_authentik_sub")),
    )


def downgrade() -> None:
    op.drop_table("users")
    user_status = postgresql.ENUM(
        "ACTIVE",
        "DISABLED",
        name="user_status",
        create_type=False,
    )
    user_status.drop(op.get_bind(), checkfirst=True)
