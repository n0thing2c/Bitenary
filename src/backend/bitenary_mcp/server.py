from urllib.parse import urlsplit

from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import AnyHttpUrl

from bitenary_mcp.infrastructure.token_verifier import BitenaryMCPTokenVerifier
from bitenary_mcp.service.auditing import MCPInvocationAuditor
from bitenary_mcp.service.tokens import MCPTokenCodec
from bitenary_mcp.tools.status import build_status_tool
from core.config import Settings
from core.database import AsyncSessionLocal


def create_mcp_server(settings: Settings) -> FastMCP:
    token_codec = MCPTokenCodec(settings.mcp_token_pepper)
    verifier = BitenaryMCPTokenVerifier(
        session_factory=AsyncSessionLocal,
        token_codec=token_codec,
    )
    auditor = MCPInvocationAuditor(AsyncSessionLocal)

    mcp_server = FastMCP(
        name="Bitenary",
        instructions="Authenticated nutrition and meal-planning tools.",
        token_verifier=verifier,
        auth=AuthSettings(
            issuer_url=AnyHttpUrl(settings.backend_public_url),
            resource_server_url=None,
            required_scopes=["mcp"],
        ),
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
        transport_security=transport_security(settings),
    )
    mcp_server.add_tool(build_status_tool(auditor), name="get_server_status")
    return mcp_server


def transport_security(settings: Settings) -> TransportSecuritySettings:
    parsed = urlsplit(settings.backend_public_url)
    allowed_hosts = [parsed.netloc]
    if parsed.hostname:
        allowed_hosts.append(f"{parsed.hostname}:*")
    backend_origin = f"{parsed.scheme}://{parsed.netloc}"
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=list(dict.fromkeys(allowed_hosts)),
        allowed_origins=list(
            dict.fromkeys([backend_origin, *settings.frontend_origin_list])
        ),
    )
