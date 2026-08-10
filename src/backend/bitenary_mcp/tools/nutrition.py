"""MCP tool: calculate_nutrition

Exposes Spoonacular nutrition estimation to authenticated external AI agents
through the Bitenary MCP server. Follows the same factory + auditor pattern
established by ``tools/status.py``.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from bitenary_mcp.domain.errors import ExternalServiceError
from bitenary_mcp.infrastructure.spoonacular import SpoonacularClient, SpoonacularError
from bitenary_mcp.service.auditing import MCPInvocationAuditor
from bitenary_mcp.tools.status import current_principal


TOOL_NAME = "calculate_nutrition"


def build_nutrition_tool(
    auditor: MCPInvocationAuditor,
    spoonacular: SpoonacularClient,
) -> Callable[[str], Awaitable[dict]]:
    """Return a ready-to-register ``calculate_nutrition`` MCP tool function.

    Args:
        auditor: Shared invocation auditor that logs every tool call to the DB.
        spoonacular: Open ``SpoonacularClient`` instance (must remain open for
            the lifetime of the MCP server).

    Returns:
        An async callable suitable for ``mcp_server.add_tool(...)``.
    """

    async def calculate_nutrition(query: str, is_raw_ingredient: bool = False) -> dict:
        """Estimate the nutritional content of a dish or ingredient.

        Given a free-form food query (dish name, meal description, or
        ingredient with quantity), returns per-serving estimates of
        calories, protein, fat, and carbohydrates sourced from the
        Spoonacular database.

        Args:
            query: Natural-language description of the food item.
                Examples:
                - ``"grilled salmon"``
                - ``"200g chicken breast``
                - ``"a bowl of pho"``
            is_raw_ingredient: Must be set to True if the query contains 
                raw ingredients with specific quantities (e.g., "100g chicken breast", 
                "2 eggs"). Must be set to False if the query is a complete dish 
                name (e.g., "pho", "spaghetti").

        Returns:
            A JSON-serialisable dict with the structure::

                {
                    "query": "<original query>",
                    "nutrition": {
                        "calories": {"amount": 350.0, "unit": "kcal"},
                        "protein":  {"amount":  35.0, "unit": "g"},
                        "fat":      {"amount":  12.0, "unit": "g"},
                        "carbs":    {"amount":  18.0, "unit": "g"}
                    }
                }

        Raises:
            ExternalServiceError: When the Spoonacular API is unavailable or
                returns an unrecognised response.
        """
        principal = current_principal()

        async def nutrition_operation() -> dict:
            import logging as _log
            _logger = _log.getLogger(__name__)
            try:
                info = await spoonacular.get_nutrition_info(query, is_raw_ingredient)
            except SpoonacularError as exc:
                _logger.error("[calculate_nutrition] SpoonacularError query=%r: %s", query, exc)
                raise ExternalServiceError(
                    f"Nutrition lookup failed for {query!r}: {exc}"
                ) from exc
            except Exception as exc:
                # Catch network errors (httpx.ConnectError, timeout, etc.)
                _logger.error(
                    "[calculate_nutrition] Unexpected error query=%r: %s: %s",
                    query, type(exc).__name__, exc
                )
                raise ExternalServiceError(
                    f"Nutrition lookup failed (network?) for {query!r}: {type(exc).__name__}: {exc}"
                ) from exc

            _logger.info("[calculate_nutrition] OK query=%r calories=%s", query, info.calories)
            return {
                "query": query,
                "nutrition": info.to_dict(),
            }

        return await auditor.invoke(
            principal=principal,
            tool_name=TOOL_NAME,
            operation=nutrition_operation,
        )

    calculate_nutrition.__name__ = TOOL_NAME
    return calculate_nutrition
