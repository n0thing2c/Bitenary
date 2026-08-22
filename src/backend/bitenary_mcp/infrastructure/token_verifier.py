from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mcp.server.auth.provider import AccessToken

from bitenary_mcp.infrastructure.sqlalchemy_mcp import (
    SqlAlchemyMCPClientRepository,
)
from bitenary_mcp.service.authentication import MCPAuthenticationService
from bitenary_mcp.service.tokens import MCPTokenCodec

_INTERNAL_CLIENT_ID = "00000000-0000-0000-0000-000000000000"
_INTERNAL_CLIENT_TYPE = "INTERNAL_AGENT"


class BitenaryMCPTokenVerifier:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        token_codec: MCPTokenCodec,
    ) -> None:
        self._session_factory = session_factory
        self._token_codec = token_codec

    async def verify_token(self, token: str) -> AccessToken | None:
        # Fast path: internal tokens are signed by the server's own pepper
        # and do not require a database round-trip. The Orchestrator uses these
        # to authenticate itself when it calls the MCP server in-process.
        user_id = self._token_codec.verify_internal_token(token)
        if user_id is not None:
            return AccessToken(
                token="[internal]",
                client_id=_INTERNAL_CLIENT_ID,
                subject=str(user_id),
                scopes=["mcp"],
                claims={"client_type": _INTERNAL_CLIENT_TYPE},
            )

        # Standard path: look up the hashed token in the database.
        async with self._session_factory() as session:
            repository = SqlAlchemyMCPClientRepository(session)
            service = MCPAuthenticationService(
                repository=repository,
                token_codec=self._token_codec,
            )
            principal = await service.authenticate(token)

        if principal is None:
            return None
        return AccessToken(
            # The actual bearer value is not needed after validation.
            token="[redacted]",
            client_id=str(principal.client_id),
            subject=str(principal.user_id),
            scopes=["mcp"],
            claims={"client_type": principal.client_type.value},
        )
