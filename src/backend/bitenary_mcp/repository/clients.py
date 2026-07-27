from datetime import datetime
from typing import Protocol
from uuid import UUID

from bitenary_mcp.domain.entities import (
    MCPAuthRecord,
    MCPClient,
    MCPClientStatus,
    MCPClientType,
    MCPUsageOutcome,
)


class MCPClientRepository(Protocol):
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
        raise NotImplementedError

    async def list_by_user(self, user_id: UUID) -> list[MCPClient]:
        raise NotImplementedError

    async def revoke_owned(self, *, client_id: UUID, user_id: UUID) -> bool:
        raise NotImplementedError

    async def get_auth_record_by_prefix(
        self,
        token_prefix: str,
    ) -> MCPAuthRecord | None:
        raise NotImplementedError


class MCPAuditRepository(Protocol):
    async def start_invocation(
        self,
        *,
        request_id: UUID,
        client_id: UUID,
        tool_name: str,
        invoked_at: datetime,
    ) -> None:
        raise NotImplementedError

    async def finish_invocation(
        self,
        *,
        request_id: UUID,
        outcome: MCPUsageOutcome,
        completed_at: datetime,
        latency_ms: int,
        error_code: str | None,
    ) -> None:
        raise NotImplementedError
