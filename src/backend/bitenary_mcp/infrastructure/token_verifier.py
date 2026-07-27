from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mcp.server.auth.provider import AccessToken

from bitenary_mcp.infrastructure.sqlalchemy_mcp import (
    SqlAlchemyMCPClientRepository,
)
from bitenary_mcp.service.authentication import MCPAuthenticationService
from bitenary_mcp.service.tokens import MCPTokenCodec


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
