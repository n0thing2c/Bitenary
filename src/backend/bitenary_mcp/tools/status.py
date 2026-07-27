from collections.abc import Awaitable, Callable
from uuid import UUID

from mcp.server.auth.middleware.auth_context import get_access_token

from bitenary_mcp.domain.entities import MCPClientType, MCPPrincipal
from bitenary_mcp.service.auditing import MCPInvocationAuditor


TOOL_NAME = "get_server_status"


def current_principal() -> MCPPrincipal:
    access_token = get_access_token()
    if (
        access_token is None
        or access_token.subject is None
        or access_token.claims is None
        or "client_type" not in access_token.claims
    ):
        raise RuntimeError("Authenticated MCP principal is unavailable")

    return MCPPrincipal(
        client_id=UUID(access_token.client_id),
        user_id=UUID(access_token.subject),
        client_type=MCPClientType(str(access_token.claims["client_type"])),
    )


def build_status_tool(
    auditor: MCPInvocationAuditor,
) -> Callable[[], Awaitable[dict[str, str]]]:
    async def get_server_status() -> dict[str, str]:
        principal = current_principal()

        async def status_operation() -> dict[str, str]:
            return {
                "status": "ok",
                "service": "bitenary-mcp",
            }

        return await auditor.invoke(
            principal=principal,
            tool_name=TOOL_NAME,
            operation=status_operation,
        )

    get_server_status.__name__ = TOOL_NAME
    get_server_status.__doc__ = "Return the current Bitenary MCP service status."
    return get_server_status
