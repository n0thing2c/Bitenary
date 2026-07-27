"""create MCP authentication and audit tables

Revision ID: 202607240003
Revises: 202607200002
Create Date: 2026-07-24

"""
from collections.abc import Sequence
from uuid import UUID

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "202607240003"
down_revision: str | None = "202607200002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STATUS_TOOL_ID = UUID("f7c1f9df-2ef9-4e26-b76e-0f60b5ec8a01")


def upgrade() -> None:
    client_type = postgresql.ENUM(
        "CODEX",
        "CLAUDE",
        name="mcp_client_type",
        create_type=False,
    )
    client_status = postgresql.ENUM(
        "ACTIVE",
        "DISABLED",
        name="mcp_client_status",
        create_type=False,
    )
    usage_outcome = postgresql.ENUM(
        "PENDING",
        "SUCCEEDED",
        "FAILED",
        name="mcp_usage_outcome",
        create_type=False,
    )
    client_type.create(op.get_bind(), checkfirst=True)
    client_status.create(op.get_bind(), checkfirst=True)
    usage_outcome.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "mcp_clients",
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_type", client_type, nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("token_prefix", sa.String(length=16), nullable=False),
        sa.Column("token_digest", sa.String(length=64), nullable=False),
        sa.Column("status", client_status, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
            name=op.f("fk_mcp_clients_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("client_id", name=op.f("pk_mcp_clients")),
        sa.UniqueConstraint("token_digest", name=op.f("uq_mcp_clients_token_digest")),
        sa.UniqueConstraint("token_prefix", name=op.f("uq_mcp_clients_token_prefix")),
    )
    op.create_index(
        op.f("ix_mcp_clients_user_id"),
        "mcp_clients",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "mcp_tools",
        sa.Column("tool_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("input_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("version", sa.String(length=30), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("tool_id", name=op.f("pk_mcp_tools")),
        sa.UniqueConstraint("name", name=op.f("uq_mcp_tools_name")),
    )
    # Use a literal JSONB cast so both online and --sql/offline migrations work.
    op.execute(
        sa.text(
            f"""
            INSERT INTO mcp_tools
                (tool_id, name, description, input_schema, version, is_active)
            VALUES
                (
                    '{STATUS_TOOL_ID}',
                    'get_server_status',
                    'Return the current Bitenary MCP service status.',
                    '{{"type":"object","properties":{{}},"additionalProperties": false}}'::jsonb,
                    '1.0.0',
                    true
                )
            """
        )
    )

    op.create_table(
        "mcp_usage_logs",
        sa.Column("log_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tool_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invoked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome", usage_outcome, nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["mcp_clients.client_id"],
            name=op.f("fk_mcp_usage_logs_client_id_mcp_clients"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tool_id"],
            ["mcp_tools.tool_id"],
            name=op.f("fk_mcp_usage_logs_tool_id_mcp_tools"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("log_id", name=op.f("pk_mcp_usage_logs")),
        sa.UniqueConstraint("request_id", name=op.f("uq_mcp_usage_logs_request_id")),
    )
    op.create_index(
        op.f("ix_mcp_usage_logs_client_id"),
        "mcp_usage_logs",
        ["client_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_mcp_usage_logs_client_id"), table_name="mcp_usage_logs")
    op.drop_table("mcp_usage_logs")
    op.drop_table("mcp_tools")
    op.drop_index(op.f("ix_mcp_clients_user_id"), table_name="mcp_clients")
    op.drop_table("mcp_clients")

    postgresql.ENUM(
        "PENDING",
        "SUCCEEDED",
        "FAILED",
        name="mcp_usage_outcome",
        create_type=False,
    ).drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(
        "ACTIVE",
        "DISABLED",
        name="mcp_client_status",
        create_type=False,
    ).drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(
        "CODEX",
        "CLAUDE",
        name="mcp_client_type",
        create_type=False,
    ).drop(op.get_bind(), checkfirst=True)
