"""create_chat_history_tables

Revision ID: 202608070008
Revises: 202608050007
Create Date: 2026-08-07
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "202608070008"
down_revision = "202608050007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # chat_sessions — one row per (user, frontend-session-id) pair        #
    # ------------------------------------------------------------------ #
    op.create_table(
        "chat_sessions",
        sa.Column("session_id", sa.String(128), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        # Auto-generated from the first human message (first 80 chars).
        sa.Column("title", sa.String(100), nullable=False, server_default=""),
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
    )
    op.create_index("ix_chat_sessions_user_id", "chat_sessions", ["user_id"])
    op.create_index(
        "ix_chat_sessions_user_updated",
        "chat_sessions",
        ["user_id", "updated_at"],
    )

    # ------------------------------------------------------------------ #
    # chat_messages — every individual message in a session               #
    # ------------------------------------------------------------------ #
    op.create_table(
        "chat_messages",
        sa.Column(
            "message_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "session_id",
            sa.String(128),
            sa.ForeignKey("chat_sessions.session_id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Role is stored as a plain varchar. Enum DDL is avoided for
        # portability (avoids issues with ALTER TYPE in Postgres).
        sa.Column("role", sa.String(8), nullable=False),  # 'human' | 'ai'
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_chat_messages_session_id", "chat_messages", ["session_id"])
    op.create_index(
        "ix_chat_messages_session_created",
        "chat_messages",
        ["session_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_chat_messages_session_created", table_name="chat_messages")
    op.drop_index("ix_chat_messages_session_id", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_chat_sessions_user_updated", table_name="chat_sessions")
    op.drop_index("ix_chat_sessions_user_id", table_name="chat_sessions")
    op.drop_table("chat_sessions")
