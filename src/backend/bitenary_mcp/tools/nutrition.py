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
        """Look up calories and macronutrients for food, dishes, and meals.

        This is Bitenary's primary tool for nutrition calculations. Use it
        first, before web search or manual estimation, whenever the user asks
        about calories, protein, fat, carbohydrates, macros, or nutritional
        values for any food, drink, ingredient, dish, meal, or portion. This
        applies to natural-language requests in any language, including
        Vietnamese questions such as "Một tô phở bò có bao nhiêu calo?".

        The result is an estimate sourced from Spoonacular. Do not present it
        as an exact laboratory measurement. If a dish lookup fails, retry once
        with a short, plain English dish name and remove serving filler,
        accents, and parenthetical translations; for example, retry
        ``"1 bowl of Vietnamese beef pho (phở bò)"`` as ``"beef pho"``. If
        the shorter query also fails, report that nutrition data could not be
        retrieved instead of inventing values or silently switching to web
        search.

        Args:
            query: Natural-language food description. Prefer a concise dish
                name for a prepared dish, or an ingredient/basic food with a
                concrete quantity when using ingredient mode.
                Examples:
                - ``"beef pho"`` with ``is_raw_ingredient=False``
                - ``"spaghetti bolognese"`` with
                  ``is_raw_ingredient=False``
                - ``"200 g chicken breast"`` with
                  ``is_raw_ingredient=True``
                - ``"2 eggs"`` with ``is_raw_ingredient=True``
            is_raw_ingredient: Selects how Spoonacular interprets ``query``.
                Set to ``True`` for an ingredient or basic food with an
                explicit quantity, including cooked basics such as
                ``"150 g cooked white rice"``. Set to ``False`` for a named
                prepared or complex dish, even when the user describes it as
                one bowl or one serving. For example, use ``False`` for
                ``"beef pho"`` and ``"spaghetti bolognese"``.

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
            ExternalServiceError: When Spoonacular is unavailable, cannot
                identify the food, or returns an unrecognised response.
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
