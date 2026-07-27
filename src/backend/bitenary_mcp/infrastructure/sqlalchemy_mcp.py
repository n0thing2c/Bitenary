from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from bitenary_mcp.domain.entities import (
    MCPAuthRecord,
    MCPClient,
    MCPClientStatus,
    MCPClientType,
    MCPUsageOutcome,
)
from bitenary_mcp.domain.errors import (
    DuplicateTokenPrefixError,
    MCPAuditUnavailableError,
)
from bitenary_mcp.repository.clients import MCPAuditRepository, MCPClientRepository
from core.database import Base
from identity.domain.entities import UserStatus
from identity.infrastructure.sqlalchemy_users import UserModel


class MCPClientModel(Base):
    __tablename__ = "mcp_clients"

    client_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_type: Mapped[MCPClientType] = mapped_column(
        Enum(MCPClientType, name="mcp_client_type"),
        nullable=False,
    )
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    token_prefix: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    token_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    status: Mapped[MCPClientStatus] = mapped_column(
        Enum(MCPClientStatus, name="mcp_client_status"),
        nullable=False,
        default=MCPClientStatus.ACTIVE,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class MCPToolModel(Base):
    __tablename__ = "mcp_tools"

    tool_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    input_schema: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    version: Mapped[str] = mapped_column(String(30), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )


class MCPUsageLogModel(Base):
    __tablename__ = "mcp_usage_logs"

    log_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    request_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        unique=True,
        nullable=False,
    )
    client_id: Mapped[UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("mcp_clients.client_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    tool_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("mcp_tools.tool_id", ondelete="RESTRICT"),
        nullable=False,
    )
    invoked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    outcome: Mapped[MCPUsageOutcome] = mapped_column(
        Enum(MCPUsageOutcome, name="mcp_usage_outcome"),
        nullable=False,
    )
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(50))


def to_domain(model: MCPClientModel) -> MCPClient:
    return MCPClient(
        client_id=model.client_id,
        user_id=model.user_id,
        client_type=model.client_type,
        display_name=model.display_name,
        token_prefix=model.token_prefix,
        token_digest=model.token_digest,
        status=model.status,
        expires_at=model.expires_at,
        revoked_at=model.revoked_at,
        last_used_at=model.last_used_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SqlAlchemyMCPClientRepository(MCPClientRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        user_id: UUID,
        client_type: MCPClientType,
        display_name: str,
        token_prefix: str,
        token_digest: str,
        status: MCPClientStatus,
        expires_at: datetime,
    ) -> MCPClient:
        model = MCPClientModel(
            user_id=user_id,
            client_type=client_type,
            display_name=display_name,
            token_prefix=token_prefix,
            token_digest=token_digest,
            status=status,
            expires_at=expires_at,
        )
        self._session.add(model)
        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise DuplicateTokenPrefixError("MCP token material already exists") from exc
        await self._session.refresh(model)
        return to_domain(model)

    async def list_by_user(self, user_id: UUID) -> list[MCPClient]:
        result = await self._session.execute(
            select(MCPClientModel)
            .where(MCPClientModel.user_id == user_id)
            .order_by(MCPClientModel.created_at.desc())
        )
        return [to_domain(model) for model in result.scalars().all()]

    async def revoke_owned(self, *, client_id: UUID, user_id: UUID) -> bool:
        result = await self._session.execute(
            select(MCPClientModel).where(
                MCPClientModel.client_id == client_id,
                MCPClientModel.user_id == user_id,
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            return False
        if model.revoked_at is None:
            model.revoked_at = datetime.now(UTC)
            await self._session.commit()
        return True

    async def get_auth_record_by_prefix(
        self,
        token_prefix: str,
    ) -> MCPAuthRecord | None:
        result = await self._session.execute(
            select(MCPClientModel, UserModel.status)
            .join(UserModel, UserModel.user_id == MCPClientModel.user_id)
            .where(MCPClientModel.token_prefix == token_prefix)
        )
        row = result.one_or_none()
        if row is None:
            return None
        model, user_status = row
        return MCPAuthRecord(
            connection=to_domain(model),
            user_is_active=user_status == UserStatus.ACTIVE,
        )


class SqlAlchemyMCPAuditRepository(MCPAuditRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def start_invocation(
        self,
        *,
        request_id: UUID,
        client_id: UUID,
        tool_name: str,
        invoked_at: datetime,
    ) -> None:
        tool_result = await self._session.execute(
            select(MCPToolModel).where(
                MCPToolModel.name == tool_name,
                MCPToolModel.is_active.is_(True),
            )
        )
        tool = tool_result.scalar_one_or_none()
        client = await self._session.get(MCPClientModel, client_id)
        if tool is None or client is None:
            raise MCPAuditUnavailableError("MCP audit subject is unavailable")

        client.last_used_at = invoked_at
        self._session.add(
            MCPUsageLogModel(
                request_id=request_id,
                client_id=client_id,
                tool_id=tool.tool_id,
                invoked_at=invoked_at,
                outcome=MCPUsageOutcome.PENDING,
            )
        )
        try:
            await self._session.commit()
        except Exception as exc:
            await self._session.rollback()
            raise MCPAuditUnavailableError("Could not start MCP audit") from exc

    async def finish_invocation(
        self,
        *,
        request_id: UUID,
        outcome: MCPUsageOutcome,
        completed_at: datetime,
        latency_ms: int,
        error_code: str | None,
    ) -> None:
        result = await self._session.execute(
            select(MCPUsageLogModel).where(
                MCPUsageLogModel.request_id == request_id
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise MCPAuditUnavailableError("MCP audit row is unavailable")
        model.outcome = outcome
        model.completed_at = completed_at
        model.latency_ms = latency_ms
        model.error_code = error_code
        await self._session.commit()
