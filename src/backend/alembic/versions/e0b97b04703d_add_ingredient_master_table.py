"""add ingredient_master table

Revision ID: e0b97b04703d
Revises: 202607300004
Create Date: 2026-08-02 02:46:31.840819

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'e0b97b04703d'
down_revision: str | None = '202607300004'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Enable pg_trgm extension for fast ILIKE / fuzzy search.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "ingredient_master",
        sa.Column("ingredient_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(512), nullable=False),
        sa.Column("variant", sa.String(512), nullable=False, server_default=""),
        sa.Column("category", sa.String(128), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    # B-tree indexes for exact filter queries.
    op.create_index("ix_ingredient_master_name", "ingredient_master", ["name"])
    op.create_index("ix_ingredient_master_category", "ingredient_master", ["category"])
    op.create_index("ix_ingredient_master_is_default", "ingredient_master", ["is_default"])

    # GIN trigram index for fast ILIKE search on name.
    op.execute(
        "CREATE INDEX ix_ingredient_master_name_trgm "
        "ON ingredient_master USING gin (name gin_trgm_ops)"
    )


def downgrade() -> None:
    op.drop_index("ix_ingredient_master_name_trgm", table_name="ingredient_master")
    op.drop_index("ix_ingredient_master_is_default", table_name="ingredient_master")
    op.drop_index("ix_ingredient_master_category", table_name="ingredient_master")
    op.drop_index("ix_ingredient_master_name", table_name="ingredient_master")
    op.drop_table("ingredient_master")
