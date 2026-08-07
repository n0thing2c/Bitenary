"""create_meal_plans_table

Revision ID: 202608050007
Revises: 202608020006_create_expiry_notifications
Create Date: 2026-08-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "202608050007"
down_revision = "202608020006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "meal_plans",
        sa.Column(
            "plan_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("total_calories", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "plan_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_meal_plans_user_start",
        "meal_plans",
        ["user_id", "start_date"],
    )
    op.create_index(
        "ix_meal_plans_user_created",
        "meal_plans",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_meal_plans_user_created", table_name="meal_plans")
    op.drop_index("ix_meal_plans_user_start", table_name="meal_plans")
    op.drop_table("meal_plans")
