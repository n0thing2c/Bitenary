from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from bitenary_mcp.infrastructure.sqlalchemy_mcp import (
    SqlAlchemyMCPClientRepository,
)
from bitenary_mcp.repository.clients import MCPClientRepository
from bitenary_mcp.service.connections import MCPConnectionService
from bitenary_mcp.service.tokens import MCPTokenCodec
from core.config import Settings, get_settings
from core.database import get_db_session


def get_mcp_client_repository(
    session: AsyncSession = Depends(get_db_session),
) -> MCPClientRepository:
    return SqlAlchemyMCPClientRepository(session)


def get_mcp_token_codec(
    settings: Settings = Depends(get_settings),
) -> MCPTokenCodec:
    return MCPTokenCodec(settings.mcp_token_pepper)


def get_mcp_connection_service(
    repository: MCPClientRepository = Depends(get_mcp_client_repository),
    token_codec: MCPTokenCodec = Depends(get_mcp_token_codec),
    settings: Settings = Depends(get_settings),
) -> MCPConnectionService:
    return MCPConnectionService(
        repository=repository,
        token_codec=token_codec,
        token_ttl_days=settings.mcp_token_ttl_days,
    )
