"""
Async HTTP client for the Spoonacular Food & Nutrition API.

Docs: https://spoonacular.com/food-api/docs

Spoonacular backs three MCP tools:
- ``calculate_nutrition``: estimate macro-nutrients for a dish or ingredient.
- ``search_recipes``: find recipes matching diet, intolerances, and calorie goals.
- ``get_recipe_details``: fetch full ingredient list and step-by-step instructions by recipe ID.

All calls are fire-and-forget relative to the caller; the caller owns
error handling and timeouts.
"""

from __future__ import annotations

import logging
import re

import httpx

from bitenary_mcp.domain.schemas import (
    NutrientValue,
    NutritionInformation,
    RecipeSummary,
    RecipeDetails,
    RecipeIngredient,
    RecipeInstructionStep,
)


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
    # Context-manager support (kept for backward-compat / test teardown)
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "SpoonacularClient":
        self._get_client()  # ensure client is open
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _get_client(self) -> httpx.AsyncClient:
        """Return the shared httpx client, creating it on first call (lazy init)."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=_BASE_URL,
                timeout=_TIMEOUT_SECONDS,
                params={"apiKey": self._api_key},
            )
        return self._client

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
        client = self._get_client()

        if is_raw_ingredient:
            logger.debug("Spoonacular parseIngredients: %r", query)
            return await self._parse_ingredients(query)

        logger.debug("Spoonacular guessNutrition: %r", query)
        response = await client.get(
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
        client = self._get_client()
        response = await client.post(
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

    async def search_recipes(
        self,
        *,
        query: str = "",
        diet: str = "",
        intolerances: str = "",
        include_ingredients: str = "",
        max_calories: int | None = None,
        min_protein: int | None = None,
        limit: int = 3,
    ) -> list[RecipeSummary]:
        """Search for recipes using Spoonacular's complexSearch endpoint.

        Args:
            query: Free-text search term (e.g. ``"chicken soup"``).
            diet: Diet label (e.g. ``"vegetarian"``, ``"keto"``, ``"paleo"``).
            intolerances: Comma-separated intolerances to exclude
                (e.g. ``"gluten, dairy"``).
            include_ingredients: Comma-separated ingredients that must appear
                in the recipe (e.g. ``"tomato, garlic"``).
            max_calories: Upper bound on calories per serving.
            min_protein: Lower bound on protein (grams) per serving.
            limit: Maximum number of recipes to return (default 3, max 5).

        Returns:
            A list of :class:`RecipeSummary` objects with title, image,
            prep time, and per-serving macro-nutrients.
        """
        client = self._get_client()
        limit = min(limit, 5)  # Hard-cap to protect free-tier quota
        params: dict[str, str | int] = {
            "number": limit,
            "addRecipeNutrition": "true",
            "addRecipeInformation": "true",
        }
        if query:
            params["query"] = query
        if diet:
            params["diet"] = diet
        if intolerances:
            params["intolerances"] = intolerances
        if include_ingredients:
            params["includeIngredients"] = include_ingredients
        if max_calories is not None:
            params["maxCalories"] = max_calories
        if min_protein is not None:
            params["minProtein"] = min_protein

        logger.debug("Spoonacular complexSearch params: %s", params)
        response = await client.get("/recipes/complexSearch", params=params)

        if response.status_code != 200:
            raise SpoonacularError(
                f"Spoonacular complexSearch error {response.status_code}: {response.text[:200]}"
            )

        data = response.json()
        results = data.get("results", [])
        return [_parse_recipe_summary(item) for item in results]

    async def get_recipe_details(self, recipe_id: int) -> RecipeDetails:
        """Fetch full ingredient list and step-by-step cooking instructions for a recipe.

        Args:
            recipe_id: The numeric Spoonacular recipe ID (obtained from
                ``search_recipes``).

        Returns:
            A :class:`RecipeDetails` object containing the title, source URL,
            all ingredients with quantities, and numbered cooking steps.

        Raises:
            SpoonacularError: If the API returns a non-200 status or the
                recipe ID is not found.
        """
        client = self._get_client()
        logger.debug("Spoonacular recipe information: id=%s", recipe_id)
        response = await client.get(
            f"/recipes/{recipe_id}/information",
            params={"includeNutrition": "false"},
        )

        if response.status_code == 404:
            raise SpoonacularError(f"Recipe with id={recipe_id} was not found.")
        if response.status_code != 200:
            raise SpoonacularError(
                f"Spoonacular recipe info error {response.status_code}: {response.text[:200]}"
            )

        return _parse_recipe_details(response.json())


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


def _get_nutrient_amount(nutrients: list[dict], name: str) -> float:
    """Find and return the amount of a named nutrient from a nutrients list."""
    for n in nutrients:
        if n.get("name", "").lower() == name.lower():
            return round(float(n.get("amount", 0)), 2)
    return 0.0


def _parse_recipe_summary(data: dict) -> RecipeSummary:
    """Convert a single complexSearch result item into a RecipeSummary."""
    try:
        nutrients: list[dict] = (
            data.get("nutrition", {}).get("nutrients", [])
        )
        return RecipeSummary(
            id=int(data["id"]),
            title=str(data.get("title", "")),
            image=str(data.get("image", "")),
            ready_in_minutes=int(data.get("readyInMinutes", 0)),
            calories=_get_nutrient_amount(nutrients, "Calories"),
            protein=_get_nutrient_amount(nutrients, "Protein"),
            fat=_get_nutrient_amount(nutrients, "Fat"),
            carbs=_get_nutrient_amount(nutrients, "Carbohydrates"),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise SpoonacularError(
            f"Unexpected complexSearch recipe format: {exc}"
        ) from exc


def _strip_html(text: str) -> str:
    """Remove HTML tags and decode common HTML entities from a string.

    Spoonacular occasionally embeds HTML markup (e.g. ``<b>``, ``<a href>``
    anchor tags) inside the ``instructions`` field.  Stripping those tags
    produces clean, LLM-friendly plain text.
    """
    # Remove HTML tags
    clean = re.sub(r"<[^>]+>", "", text)
    # Decode common HTML entities
    entities = {
        "&amp;": "&",
        "&lt;": "<",
        "&gt;": ">",
        "&quot;": '"',
        "&#39;": "'",
        "&nbsp;": " ",
    }
    for entity, char in entities.items():
        clean = clean.replace(entity, char)
    # Collapse extra whitespace
    return " ".join(clean.split()).strip()


def _parse_recipe_details(data: dict) -> RecipeDetails:
    """Convert a raw Spoonacular /recipes/{id}/information response into RecipeDetails."""
    try:
        # --- Ingredients ---
        raw_ingredients = data.get("extendedIngredients", [])
        ingredients = tuple(
            RecipeIngredient(
                name=str(ing.get("name", "")),
                original=str(ing.get("original", "")),
                amount=round(float(ing.get("amount", 0)), 2),
                unit=str(ing.get("unit", "")),
            )
            for ing in raw_ingredients
        )

        # --- Instructions ---
        # Spoonacular returns analyzedInstructions as a list of sections.
        # Each section has a list of steps. We flatten all sections into one list.
        steps: list[RecipeInstructionStep] = []
        analyzed = data.get("analyzedInstructions", [])
        step_counter = 1
        for section in analyzed:
            for step in section.get("steps", []):
                raw_text = str(step.get("step", ""))
                steps.append(
                    RecipeInstructionStep(
                        number=step_counter,
                        step=_strip_html(raw_text),
                    )
                )
                step_counter += 1

        # Fallback: use raw instructions string if no analyzed instructions present
        if not steps and data.get("instructions"):
            raw_text = _strip_html(str(data["instructions"]))
            steps.append(RecipeInstructionStep(number=1, step=raw_text))

        return RecipeDetails(
            id=int(data["id"]),
            title=str(data.get("title", "")),
            source_url=str(data.get("sourceUrl", "")),
            image=str(data.get("image", "")),
            ready_in_minutes=int(data.get("readyInMinutes", 0)),
            servings=int(data.get("servings", 1)),
            ingredients=ingredients,
            instructions=tuple(steps),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise SpoonacularError(
            f"Unexpected recipe details format: {exc}"
        ) from exc
