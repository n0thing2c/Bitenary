"""create virtual fridge items

Revision ID: 202608020005
Revises: e0b97b04703d
Create Date: 2026-08-02

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "202608020005"
down_revision: str | None = "e0b97b04703d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    food_state = postgresql.ENUM(
        "RAW",
        "COOKED",
        "FROZEN",
        "PREPPED",
        name="virtual_fridge_food_state",
        create_type=False,
    )
    food_state.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "fridge_items",
        sa.Column("fridge_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ingredient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=False),
        sa.Column("food_state", food_state, nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=False),
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
        sa.CheckConstraint(
            "quantity > 0",
            name=op.f("ck_fridge_items_fridge_items_quantity_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["ingredient_id"],
            ["ingredient_master.ingredient_id"],
            name=op.f("fk_fridge_items_ingredient_id_ingredient_master"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
            name=op.f("fk_fridge_items_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "fridge_item_id",
            name=op.f("pk_fridge_items"),
        ),
    )
    op.create_index(
        "ix_fridge_items_user_expiry",
        "fridge_items",
        ["user_id", "expiry_date"],
    )
    op.create_index(
        "ix_fridge_items_user_ingredient",
        "fridge_items",
        ["user_id", "ingredient_id"],
    )
    op.create_index(
        "ix_fridge_items_user_updated",
        "fridge_items",
        ["user_id", "updated_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_fridge_items_user_updated", table_name="fridge_items")
    op.drop_index("ix_fridge_items_user_ingredient", table_name="fridge_items")
    op.drop_index("ix_fridge_items_user_expiry", table_name="fridge_items")
    op.drop_table("fridge_items")
    postgresql.ENUM(
        "RAW",
        "COOKED",
        "FROZEN",
        "PREPPED",
        name="virtual_fridge_food_state",
        create_type=False,
    ).drop(op.get_bind(), checkfirst=True)
