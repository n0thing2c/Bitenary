"""baseline

Revision ID: 202607200001
Revises:
Create Date: 2026-07-20

"""
from collections.abc import Sequence


revision: str = "202607200001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
