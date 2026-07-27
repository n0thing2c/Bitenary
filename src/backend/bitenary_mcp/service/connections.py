from datetime import UTC, datetime, timedelta
from uuid import UUID

from bitenary_mcp.domain.entities import (
    CreatedMCPConnection,
    MCPClient,
    MCPClientStatus,
    MCPClientType,
)
from bitenary_mcp.domain.errors import (
    DuplicateTokenPrefixError,
    MCPConnectionNotFoundError,
)
from bitenary_mcp.repository.clients import MCPClientRepository
from bitenary_mcp.service.tokens import MCPTokenCodec


MAX_TOKEN_GENERATION_ATTEMPTS = 5


class MCPConnectionService:
    def __init__(
        self,
        *,
        repository: MCPClientRepository,
        token_codec: MCPTokenCodec,
        token_ttl_days: int,
    ) -> None:
        self._repository = repository
        self._token_codec = token_codec
        self._token_ttl_days = token_ttl_days

    async def create(
        self,
        *,
        user_id: UUID,
        client_type: MCPClientType,
        display_name: str,
    ) -> CreatedMCPConnection:
        expires_at = datetime.now(UTC) + timedelta(days=self._token_ttl_days)
        for _ in range(MAX_TOKEN_GENERATION_ATTEMPTS):
            plaintext, prefix, digest = self._token_codec.generate()
            try:
                connection = await self._repository.create(
                    user_id=user_id,
                    client_type=client_type,
                    display_name=display_name,
                    token_prefix=prefix,
                    token_digest=digest,
                    status=MCPClientStatus.ACTIVE,
                    expires_at=expires_at,
                )
                return CreatedMCPConnection(
                    connection=connection,
                    plaintext_token=plaintext,
                )
            except DuplicateTokenPrefixError:
                continue
        raise RuntimeError("Could not allocate unique MCP token material")

    async def list_for_user(self, user_id: UUID) -> list[MCPClient]:
        return await self._repository.list_by_user(user_id)

    async def revoke(self, *, client_id: UUID, user_id: UUID) -> None:
        found = await self._repository.revoke_owned(
            client_id=client_id,
            user_id=user_id,
        )
        if not found:
            raise MCPConnectionNotFoundError("MCP connection was not found")
