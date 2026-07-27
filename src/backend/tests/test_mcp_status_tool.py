from uuid import uuid4

import pytest
from mcp.server.auth.middleware.auth_context import auth_context_var
from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser
from mcp.server.auth.provider import AccessToken

from bitenary_mcp.domain.entities import MCPClientType, MCPPrincipal
from bitenary_mcp.tools.status import build_status_tool


class FakeAuditor:
    def __init__(self) -> None:
        self.principal: MCPPrincipal | None = None
        self.tool_name: str | None = None

    async def invoke(self, *, principal, tool_name, operation):
        self.principal = principal
        self.tool_name = tool_name
        return await operation()


@pytest.mark.anyio
async def test_status_tool_propagates_authenticated_principal_to_audit() -> None:
    client_id = uuid4()
    user_id = uuid4()
    access_token = AccessToken(
        token="[redacted]",
        client_id=str(client_id),
        subject=str(user_id),
        scopes=["mcp"],
        claims={"client_type": "CLAUDE"},
    )
    context_token = auth_context_var.set(AuthenticatedUser(access_token))
    auditor = FakeAuditor()
    tool = build_status_tool(auditor)  # type: ignore[arg-type]

    try:
        result = await tool()
    finally:
        auth_context_var.reset(context_token)

    assert result == {"status": "ok", "service": "bitenary-mcp"}
    assert auditor.tool_name == "get_server_status"
    assert auditor.principal == MCPPrincipal(
        client_id=client_id,
        user_id=user_id,
        client_type=MCPClientType.CLAUDE,
    )


@pytest.mark.anyio
async def test_status_tool_rejects_missing_principal() -> None:
    auditor = FakeAuditor()
    tool = build_status_tool(auditor)  # type: ignore[arg-type]

    with pytest.raises(RuntimeError, match="principal"):
        await tool()
