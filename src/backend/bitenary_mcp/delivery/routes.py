from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from bitenary_mcp.delivery.dto import (
    CreateMCPConnectionRequest,
    CreatedMCPConnectionResponse,
    MCPConnectionResponse,
    connection_response,
    created_connection_response,
)
from bitenary_mcp.domain.errors import MCPConnectionNotFoundError
from bitenary_mcp.service.connections import MCPConnectionService
from bitenary_mcp.wiring import get_mcp_connection_service
from core.config import Settings, get_settings
from identity.domain.entities import CurrentUser
from identity.wiring import get_current_user


router = APIRouter(prefix="/mcp-connections", tags=["mcp-connections"])


@router.post(
    "",
    response_model=CreatedMCPConnectionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_connection(
    payload: CreateMCPConnectionRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: MCPConnectionService = Depends(get_mcp_connection_service),
    settings: Settings = Depends(get_settings),
) -> CreatedMCPConnectionResponse:
    created = await service.create(
        user_id=current_user.user_id,
        client_type=payload.client_type,
        display_name=payload.display_name,
    )
    mcp_url = f"{settings.backend_public_url.rstrip('/')}/mcp"
    return created_connection_response(created, mcp_url=mcp_url)


@router.get("", response_model=list[MCPConnectionResponse])
async def list_connections(
    current_user: CurrentUser = Depends(get_current_user),
    service: MCPConnectionService = Depends(get_mcp_connection_service),
) -> list[MCPConnectionResponse]:
    connections = await service.list_for_user(current_user.user_id)
    return [connection_response(connection) for connection in connections]


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_connection(
    client_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: MCPConnectionService = Depends(get_mcp_connection_service),
) -> None:
    try:
        await service.revoke(
            client_id=client_id,
            user_id=current_user.user_id,
        )
    except MCPConnectionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MCP connection was not found",
        ) from exc
