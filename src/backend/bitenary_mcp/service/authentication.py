from datetime import UTC, datetime

from bitenary_mcp.domain.entities import (
    MCPClientStatus,
    MCPPrincipal,
)
from bitenary_mcp.repository.clients import MCPClientRepository
from bitenary_mcp.service.tokens import MCPTokenCodec


class MCPAuthenticationService:
    def __init__(
        self,
        *,
        repository: MCPClientRepository,
        token_codec: MCPTokenCodec,
    ) -> None:
        self._repository = repository
        self._token_codec = token_codec

    async def authenticate(self, token: str) -> MCPPrincipal | None:
        token_prefix = self._token_codec.parse_prefix(token)
        if token_prefix is None:
            return None

        record = await self._repository.get_auth_record_by_prefix(token_prefix)
        if record is None:
            return None

        connection = record.connection
        now = datetime.now(UTC)
        if not self._token_codec.matches(token, connection.token_digest):
            return None
        if not record.user_is_active:
            return None
        if connection.status != MCPClientStatus.ACTIVE:
            return None
        if connection.revoked_at is not None or connection.expires_at <= now:
            return None

        return MCPPrincipal(
            client_id=connection.client_id,
            user_id=connection.user_id,
            client_type=connection.client_type,
        )
