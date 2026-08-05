from urllib.parse import urlsplit

from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import AnyHttpUrl

from bitenary_mcp.infrastructure.spoonacular import SpoonacularClient
from bitenary_mcp.infrastructure.token_verifier import BitenaryMCPTokenVerifier
from bitenary_mcp.service.auditing import MCPInvocationAuditor
from bitenary_mcp.service.tokens import MCPTokenCodec
from bitenary_mcp.tools.fridge import build_fridge_inventory_tool
from bitenary_mcp.tools.meal_plan import build_save_meal_plan_tool
from bitenary_mcp.tools.nutrition import build_nutrition_tool
from bitenary_mcp.tools.recipe import build_recipe_search_tool, build_recipe_details_tool
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

    # Spoonacular client is kept open for the lifetime of the server process
    # to reuse the underlying connection pool across tool invocations.
    spoonacular = SpoonacularClient(settings.spoonacular_api_key)

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
    mcp_server.add_tool(build_nutrition_tool(auditor, spoonacular), name="calculate_nutrition")
    mcp_server.add_tool(build_recipe_search_tool(auditor, spoonacular), name="search_recipes")
    mcp_server.add_tool(build_recipe_details_tool(auditor, spoonacular), name="get_recipe_details")
    # Fridge tool: the builder receives the session factory and settings so it
    # can create a fresh DB session per invocation, consistent with the auditor.
    mcp_server.add_tool(
        build_fridge_inventory_tool(
            auditor=auditor,
            session_factory=AsyncSessionLocal,
            warning_days=settings.fridge_expiry_warning_days,
        ),
        name="get_fridge_inventory",
    )
    # Meal Plan tool: AI calls this only after user explicitly approves a plan.
    mcp_server.add_tool(
        build_save_meal_plan_tool(
            auditor=auditor,
            session_factory=AsyncSessionLocal,
        ),
        name="save_meal_plan",
    )
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
