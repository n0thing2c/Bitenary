"""MCP tools for recipe discovery and details.

Exposes two tools to authenticated external AI agents:
- ``search_recipes``: find recipes by keyword, diet, intolerances, and calorie goals.
- ``get_recipe_details``: fetch full ingredient list and step-by-step instructions by ID.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from bitenary_mcp.domain.errors import ExternalServiceError
from bitenary_mcp.infrastructure.spoonacular import SpoonacularClient, SpoonacularError
from bitenary_mcp.service.auditing import MCPInvocationAuditor
from bitenary_mcp.tools.status import current_principal


TOOL_NAME = "search_recipes"


def build_recipe_search_tool(
    auditor: MCPInvocationAuditor,
    spoonacular: SpoonacularClient,
) -> Callable[..., Awaitable[dict]]:
    """Return a ready-to-register ``search_recipes`` MCP tool function.

    Args:
        auditor: Shared invocation auditor that logs every tool call to the DB.
        spoonacular: Open ``SpoonacularClient`` instance (must remain open for
            the lifetime of the MCP server).

    Returns:
        An async callable suitable for ``mcp_server.add_tool(...)``.
    """

    async def search_recipes(
        query: str = "",
        diet: str = "",
        intolerances: str = "",
        include_ingredients: str = "",
        max_calories: int = 0,
        min_protein: int = 0,
        limit: int = 3,
    ) -> dict:
        """Find recipes that match the user's dietary preferences and nutritional goals.

        Use this tool when the user wants recipe suggestions, meal ideas, or wants
        to find dishes that fit specific constraints such as calorie budget, diet
        type, or ingredient availability.

        Args:
            query: Free-text keyword for the dish (e.g. ``"chicken soup"``,
                ``"pasta"``, ``"salad"``). Leave blank to search by
                constraints alone.
            diet: Restrict results to a named diet. Supported values:
                ``"vegetarian"``, ``"vegan"``, ``"ketogenic"``, ``"paleo"``,
                ``"gluten free"``, ``"lacto-vegetarian"``, ``"ovo-vegetarian"``,
                ``"pescetarian"``, ``"primal"``, ``"low-fodmap"``,
                ``"whole30"``. Leave blank for no restriction.
            intolerances: Comma-separated list of ingredients to avoid due to
                allergy or intolerance. Supported values: ``"dairy"``,
                ``"egg"``, ``"gluten"``, ``"grain"``, ``"peanut"``,
                ``"seafood"``, ``"sesame"``, ``"shellfish"``, ``"soy"``,
                ``"sulfite"``, ``"tree nut"``, ``"wheat"``.
                Example: ``"gluten, dairy"``.
            include_ingredients: Comma-separated ingredients that must appear
                in the recipe (e.g. ``"tomato, garlic"``). Useful when the
                user says "I have X in the fridge".
            max_calories: Maximum number of calories per serving. Set to 0 to
                apply no upper bound.
            min_protein: Minimum grams of protein per serving. Set to 0 to
                apply no lower bound.
            limit: Number of recipes to return (1–5, default 3).

        Returns:
            A JSON-serialisable dict with the structure::

                {
                    "count": 3,
                    "recipes": [
                        {
                            "id": 12345,
                            "title": "Keto Chicken Salad",
                            "image": "https://img.spoonacular.com/...",
                            "ready_in_minutes": 25,
                            "nutrition": {
                                "calories": 380.0,
                                "protein_g": 42.0,
                                "fat_g": 18.0,
                                "carbs_g": 6.0
                            }
                        },
                        ...
                    ]
                }

        Raises:
            ExternalServiceError: When the Spoonacular API is unavailable or
                returns an unrecognised response.
        """
        principal = current_principal()

        async def recipe_operation() -> dict:
            try:
                results = await spoonacular.search_recipes(
                    query=query,
                    diet=diet,
                    intolerances=intolerances,
                    include_ingredients=include_ingredients,
                    max_calories=max_calories if max_calories > 0 else None,
                    min_protein=min_protein if min_protein > 0 else None,
                    limit=max(1, min(limit, 5)),
                )
            except SpoonacularError as exc:
                raise ExternalServiceError(
                    f"Recipe search failed: {exc}"
                ) from exc

            return {
                "count": len(results),
                "recipes": [r.to_dict() for r in results],
            }

        return await auditor.invoke(
            principal=principal,
            tool_name=TOOL_NAME,
            operation=recipe_operation,
        )

    search_recipes.__name__ = TOOL_NAME
    return search_recipes


_DETAILS_TOOL_NAME = "get_recipe_details"


def build_recipe_details_tool(
    auditor: MCPInvocationAuditor,
    spoonacular: SpoonacularClient,
) -> Callable[..., Awaitable[dict]]:
    """Return a ready-to-register ``get_recipe_details`` MCP tool function.

    Args:
        auditor: Shared invocation auditor that logs every tool call to the DB.
        spoonacular: Open ``SpoonacularClient`` instance.

    Returns:
        An async callable suitable for ``mcp_server.add_tool(...)``.
    """

    async def get_recipe_details(recipe_id: int) -> dict:
        """Retrieve the complete ingredient list and step-by-step cooking instructions for a recipe.

        Use this tool **after** calling ``search_recipes`` to get an ``id``.
        Pass that ``id`` here to obtain the full cooking details that the user
        needs in order to actually prepare the dish.

        Args:
            recipe_id: The numeric Spoonacular recipe ID returned in the
                ``id`` field of a ``search_recipes`` result.

        Returns:
            A JSON-serialisable dict with the structure::

                {
                    "id": 12345,
                    "title": "Keto Chicken Salad",
                    "source_url": "https://example.com/recipe",
                    "image": "https://img.spoonacular.com/...",
                    "ready_in_minutes": 25,
                    "servings": 4,
                    "ingredients": [
                        {
                            "name": "chicken breast",
                            "original": "2 boneless chicken breasts",
                            "amount": 2.0,
                            "unit": ""
                        },
                        ...
                    ],
                    "instructions": [
                        {"step_number": 1, "description": "Preheat oven to 200 C."},
                        ...
                    ]
                }

        Raises:
            ExternalServiceError: When the recipe ID is not found or the
                Spoonacular API returns an error.
        """
        principal = current_principal()

        async def details_operation() -> dict:
            try:
                details = await spoonacular.get_recipe_details(recipe_id)
            except SpoonacularError as exc:
                raise ExternalServiceError(
                    f"Recipe details fetch failed for id={recipe_id}: {exc}"
                ) from exc

            return details.to_dict()

        return await auditor.invoke(
            principal=principal,
            tool_name=_DETAILS_TOOL_NAME,
            operation=details_operation,
        )

    get_recipe_details.__name__ = _DETAILS_TOOL_NAME
    return get_recipe_details
