"""
Async HTTP client for the Spoonacular Food & Nutrition API.

Docs: https://spoonacular.com/food-api/docs

Spoonacular is used exclusively to back the MCP nutrition-calculation tool.
All calls are fire-and-forget relative to the caller; the caller owns
error handling and timeouts.
"""

from __future__ import annotations

import logging

import httpx

from bitenary_mcp.domain.schemas import NutrientValue, NutritionInformation


logger = logging.getLogger(__name__)

_BASE_URL = "https://api.spoonacular.com"
_TIMEOUT_SECONDS = 8.0

# Spoonacular field names returned by /recipes/guessNutrition
_CALORIE_KEY = "calories"
_PROTEIN_KEY = "protein"
_FAT_KEY = "fat"
_CARBS_KEY = "carbs"


class SpoonacularError(Exception):
    """Raised when the Spoonacular API returns an unexpected response."""


class SpoonacularClient:
    """Thin async wrapper around the Spoonacular REST API.

    Usage::

        async with SpoonacularClient(api_key="...") as client:
            info = await client.guess_nutrition_by_dish_name("grilled salmon")
    """

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError("SPOONACULAR_API_KEY must not be empty.")
        self._api_key = api_key
        self._client: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    # Context-manager support
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "SpoonacularClient":
        self._client = httpx.AsyncClient(
            base_url=_BASE_URL,
            timeout=_TIMEOUT_SECONDS,
            params={"apiKey": self._api_key},
        )
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    async def get_nutrition_info(
        self,
        query: str,
        is_raw_ingredient: bool = False,
    ) -> NutritionInformation:
        """Return estimated macro-nutrient information for a query.

        Args:
            query: Natural-language name of the dish or ingredients.
            is_raw_ingredient: If True, uses the parseIngredients endpoint
                which is optimized for raw ingredients with quantities.
                If False, uses the guessNutrition endpoint for full dish names.
        """
        if self._client is None:
            raise RuntimeError(
                "SpoonacularClient must be used as an async context manager."
            )

        if is_raw_ingredient:
            logger.debug("Spoonacular parseIngredients: %r", query)
            return await self._parse_ingredients(query)

        logger.debug("Spoonacular guessNutrition: %r", query)
        response = await self._client.get(
            "/recipes/guessNutrition",
            params={"title": query},
        )

        data = response.json()
        
        if response.status_code != 200 or data.get("status") == "error":
             raise SpoonacularError(
                f"Spoonacular guessNutrition error (maybe try is_raw_ingredient=True?): {response.text[:200]}"
             )

        return _parse_guess_nutrition_response(data)

    async def _parse_ingredients(self, query: str) -> NutritionInformation:
        response = await self._client.post(
            "/recipes/parseIngredients",
            data={"ingredientList": query, "includeNutrition": "true"}
        )
        if response.status_code != 200:
            raise SpoonacularError(f"Spoonacular parseIngredients error: {response.text[:200]}")
            
        data = response.json()
        if not data or not isinstance(data, list):
             raise SpoonacularError(f"Could not parse ingredient: {query}")
             
        # Aggregate nutrients across all parsed ingredients
        total_cal = total_pro = total_fat = total_carb = 0.0
        
        for item in data:
            nutrition = item.get("nutrition", {}).get("nutrients", [])
            for n in nutrition:
                name = n.get("name", "").lower()
                amount = float(n.get("amount", 0))
                if name == "calories": total_cal += amount
                elif name == "protein": total_pro += amount
                elif name == "fat": total_fat += amount
                elif name == "carbohydrates": total_carb += amount
                
        return NutritionInformation(
            calories=NutrientValue(amount=round(total_cal, 2), unit="kcal"),
            protein=NutrientValue(amount=round(total_pro, 2), unit="g"),
            fat=NutrientValue(amount=round(total_fat, 2), unit="g"),
            carbs=NutrientValue(amount=round(total_carb, 2), unit="g"),
        )


# ------------------------------------------------------------------
# Private helpers
# ------------------------------------------------------------------

def _extract_nutrient(data: dict, key: str, default_unit: str) -> NutrientValue:
    """Safely extract a nutrient entry from the API response dict."""
    entry = data.get(key, {})
    if not isinstance(entry, dict):
        # Some older API responses return a plain number instead of an object.
        return NutrientValue(amount=float(entry or 0), unit=default_unit)
    return NutrientValue(
        amount=float(entry.get("value", 0)),
        unit=str(entry.get("unit", default_unit)),
    )


def _parse_guess_nutrition_response(data: dict) -> NutritionInformation:
    """Convert a raw Spoonacular guessNutrition JSON response to a domain object."""
    try:
        return NutritionInformation(
            calories=_extract_nutrient(data, _CALORIE_KEY, "kcal"),
            protein=_extract_nutrient(data, _PROTEIN_KEY, "g"),
            fat=_extract_nutrient(data, _FAT_KEY, "g"),
            carbs=_extract_nutrient(data, _CARBS_KEY, "g"),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise SpoonacularError(
            f"Unexpected Spoonacular response format: {exc}"
        ) from exc
