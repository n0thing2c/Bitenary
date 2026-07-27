from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID


class MCPClientType(StrEnum):
    CODEX = "CODEX"
    CLAUDE = "CLAUDE"


class MCPClientStatus(StrEnum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class MCPConnectionState(StrEnum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    DISABLED = "DISABLED"


class MCPUsageOutcome(StrEnum):
    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class MCPClient:
    client_id: UUID
    user_id: UUID
    client_type: MCPClientType
    display_name: str
    token_prefix: str
    token_digest: str
    status: MCPClientStatus
    expires_at: datetime
    revoked_at: datetime | None
    last_used_at: datetime | None
    created_at: datetime
    updated_at: datetime

    def connection_state(self, now: datetime | None = None) -> MCPConnectionState:
        current_time = now or datetime.now(UTC)
        if self.revoked_at is not None:
            return MCPConnectionState.REVOKED
        if self.status == MCPClientStatus.DISABLED:
            return MCPConnectionState.DISABLED
        if self.expires_at <= current_time:
            return MCPConnectionState.EXPIRED
        return MCPConnectionState.ACTIVE


@dataclass(frozen=True)
class MCPPrincipal:
    client_id: UUID
    user_id: UUID
    client_type: MCPClientType


@dataclass(frozen=True)
class CreatedMCPConnection:
    connection: MCPClient
    plaintext_token: str


@dataclass(frozen=True)
class MCPAuthRecord:
    connection: MCPClient
    user_is_active: bool
