import json
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from bitenary_mcp.domain.entities import (
    CreatedMCPConnection,
    MCPClient,
    MCPClientType,
    MCPConnectionState,
)


TOKEN_ENV_VAR = "BITENARY_MCP_TOKEN"


class CreateMCPConnectionRequest(BaseModel):
    client_type: MCPClientType
    display_name: str = Field(min_length=1, max_length=100)

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("display_name must not be blank")
        return normalized


class MCPConnectionResponse(BaseModel):
    client_id: UUID
    client_type: MCPClientType
    display_name: str
    token_prefix: str
    state: MCPConnectionState
    expires_at: datetime
    revoked_at: datetime | None
    last_used_at: datetime | None
    created_at: datetime


class CreatedMCPConnectionResponse(MCPConnectionResponse):
    mcp_url: str
    token: str
    token_env_var: str
    codex_config: str
    claude_config: str


def connection_response(connection: MCPClient) -> MCPConnectionResponse:
    return MCPConnectionResponse(
        client_id=connection.client_id,
        client_type=connection.client_type,
        display_name=connection.display_name,
        token_prefix=connection.token_prefix,
        state=connection.connection_state(),
        expires_at=connection.expires_at,
        revoked_at=connection.revoked_at,
        last_used_at=connection.last_used_at,
        created_at=connection.created_at,
    )


def created_connection_response(
    created: CreatedMCPConnection,
    *,
    mcp_url: str,
) -> CreatedMCPConnectionResponse:
    connection = created.connection
    codex_config = "\n".join(
        [
            "[mcp_servers.bitenary]",
            f'url = "{mcp_url}"',
            f'bearer_token_env_var = "{TOKEN_ENV_VAR}"',
        ]
    )
    claude_config = json.dumps(
        {
            "mcpServers": {
                "bitenary": {
                    "type": "http",
                    "url": mcp_url,
                    "headers": {
                        "Authorization": f"Bearer ${{{TOKEN_ENV_VAR}}}",
                    },
                }
            }
        },
        indent=2,
    )
    return CreatedMCPConnectionResponse(
        **connection_response(connection).model_dump(),
        mcp_url=mcp_url,
        token=created.plaintext_token,
        token_env_var=TOKEN_ENV_VAR,
        codex_config=codex_config,
        claude_config=claude_config,
    )
