import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import AsyncMock, patch
import httpx

from bitenary_mcp.infrastructure.spoonacular import SpoonacularClient, SpoonacularError, _strip_html
from bitenary_mcp.domain.schemas import RecipeSummary, RecipeDetails


# ------------------------------------------------------------------
# Fixtures / Helpers
# ------------------------------------------------------------------

def _make_recipe_item(
    id: int = 1,
    title: str = "Keto Chicken Salad",
    image: str = "https://img.spoonacular.com/chicken.jpg",
    ready_in_minutes: int = 25,
    calories: float = 380.0,
    protein: float = 42.0,
    fat: float = 18.0,
    carbs: float = 6.0,
) -> dict:
    """Build a fake complexSearch result item."""
    return {
        "id": id,
        "title": title,
        "image": image,
        "readyInMinutes": ready_in_minutes,
        "nutrition": {
            "nutrients": [
                {"name": "Calories", "amount": calories, "unit": "kcal"},
                {"name": "Protein", "amount": protein, "unit": "g"},
                {"name": "Fat", "amount": fat, "unit": "g"},
                {"name": "Carbohydrates", "amount": carbs, "unit": "g"},
            ]
        },
    }


def _make_recipe_details_response(
    id: int = 42,
    title: str = "Grilled Salmon",
) -> dict:
    """Build a fake /recipes/{id}/information API response."""
    return {
        "id": id,
        "title": title,
        "sourceUrl": "https://example.com/grilled-salmon",
        "image": "https://img.spoonacular.com/salmon.jpg",
        "readyInMinutes": 30,
        "servings": 2,
        "extendedIngredients": [
            {"name": "salmon", "original": "2 salmon fillets", "amount": 2.0, "unit": ""},
            {"name": "olive oil", "original": "1 tbsp olive oil", "amount": 1.0, "unit": "tbsp"},
        ],
        "analyzedInstructions": [
            {
                "steps": [
                    {"number": 1, "step": "Heat the grill to <b>medium-high</b>."},
                    {"number": 2, "step": "Brush salmon with olive oil &amp; season with salt."},
                    {"number": 3, "step": "Grill for 4-5 minutes per side."},
                ]
            }
        ],
        "instructions": "",
    }


# ------------------------------------------------------------------
# Tests: search_recipes
# ------------------------------------------------------------------

@pytest.mark.anyio
async def test_search_recipes_returns_summaries() -> None:
    """Test that search_recipes parses complexSearch results into RecipeSummary objects."""
    mock_response = httpx.Response(
        status_code=200,
        json={
            "results": [
                _make_recipe_item(id=1, title="Keto Chicken Salad", calories=380.0, protein=42.0),
                _make_recipe_item(id=2, title="Grilled Salmon", calories=520.0, protein=55.0),
            ],
            "totalResults": 2,
        },
    )
    mock_response.request = httpx.Request("GET", "http://test")

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        async with SpoonacularClient("test-api-key") as client:
            results = await client.search_recipes(query="chicken", diet="ketogenic")

            assert len(results) == 2
            assert all(isinstance(r, RecipeSummary) for r in results)
            assert results[0].title == "Keto Chicken Salad"
            assert results[0].calories == 380.0
            assert results[0].protein == 42.0
            assert results[1].id == 2

            args, kwargs = mock_get.call_args
            assert args[0] == "/recipes/complexSearch"
            assert kwargs["params"]["query"] == "chicken"
            assert kwargs["params"]["diet"] == "ketogenic"
            assert kwargs["params"]["addRecipeNutrition"] == "true"


@pytest.mark.anyio
async def test_search_recipes_optional_filters() -> None:
    """Test that optional filters are sent when provided and omitted when blank."""
    mock_response = httpx.Response(
        status_code=200,
        json={"results": [_make_recipe_item()], "totalResults": 1},
    )
    mock_response.request = httpx.Request("GET", "http://test")

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        async with SpoonacularClient("test-api-key") as client:
            await client.search_recipes(
                query="pasta",
                intolerances="gluten, dairy",
                max_calories=600,
                min_protein=30,
            )

            _, kwargs = mock_get.call_args
            params = kwargs["params"]
            assert params["intolerances"] == "gluten, dairy"
            assert params["maxCalories"] == 600
            assert params["minProtein"] == 30
            assert "diet" not in params
            assert "includeIngredients" not in params


@pytest.mark.anyio
async def test_search_recipes_limit_hard_capped_at_5() -> None:
    """Test that requesting more than 5 recipes is silently capped at 5."""
    mock_response = httpx.Response(
        status_code=200,
        json={"results": [], "totalResults": 0},
    )
    mock_response.request = httpx.Request("GET", "http://test")

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        async with SpoonacularClient("test-api-key") as client:
            await client.search_recipes(query="salad", limit=99)

            _, kwargs = mock_get.call_args
            assert kwargs["params"]["number"] == 5


@pytest.mark.anyio
async def test_search_recipes_raises_on_api_error() -> None:
    """Test that SpoonacularError is raised on a non-200 API response."""
    mock_response = httpx.Response(
        status_code=402,
        text='{"message": "Your daily API quota has been exceeded."}',
    )
    mock_response.request = httpx.Request("GET", "http://test")

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        async with SpoonacularClient("test-api-key") as client:
            with pytest.raises(SpoonacularError) as exc:
                await client.search_recipes(query="pasta")

            assert "complexSearch error 402" in str(exc.value)


# ------------------------------------------------------------------
# Tests: _strip_html
# ------------------------------------------------------------------

def test_strip_html_removes_tags() -> None:
    """Test that HTML tags are stripped from instruction text."""
    assert _strip_html("<b>Heat</b> the grill") == "Heat the grill"
    assert _strip_html('Add <a href="x">olive oil</a>') == "Add olive oil"


def test_strip_html_decodes_entities() -> None:
    """Test that HTML entities are decoded to plain characters."""
    assert _strip_html("salt &amp; pepper") == "salt & pepper"
    assert _strip_html("temp &gt; 200&nbsp;C") == "temp > 200 C"


def test_strip_html_collapses_whitespace() -> None:
    """Test that multiple spaces/newlines are collapsed into one space."""
    assert _strip_html("  Season   with   salt.  ") == "Season with salt."


# ------------------------------------------------------------------
# Tests: get_recipe_details
# ------------------------------------------------------------------

@pytest.mark.anyio
async def test_get_recipe_details_success() -> None:
    """Test that get_recipe_details parses a full recipe information response."""
    mock_response = httpx.Response(
        status_code=200,
        json=_make_recipe_details_response(id=42, title="Grilled Salmon"),
    )
    mock_response.request = httpx.Request("GET", "http://test")

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        async with SpoonacularClient("test-api-key") as client:
            details = await client.get_recipe_details(42)

            assert isinstance(details, RecipeDetails)
            assert details.id == 42
            assert details.title == "Grilled Salmon"
            assert details.source_url == "https://example.com/grilled-salmon"
            assert details.servings == 2

            assert len(details.ingredients) == 2
            assert details.ingredients[0].name == "salmon"
            assert details.ingredients[1].amount == 1.0

            # HTML must have been stripped from instructions
            assert len(details.instructions) == 3
            assert details.instructions[0].step == "Heat the grill to medium-high."
            assert details.instructions[1].step == "Brush salmon with olive oil & season with salt."

            args, _ = mock_get.call_args
            assert args[0] == "/recipes/42/information"


@pytest.mark.anyio
async def test_get_recipe_details_raises_on_404() -> None:
    """Test that SpoonacularError is raised when the recipe ID is not found."""
    mock_response = httpx.Response(status_code=404, text="Not found")
    mock_response.request = httpx.Request("GET", "http://test")

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        async with SpoonacularClient("test-api-key") as client:
            with pytest.raises(SpoonacularError) as exc:
                await client.get_recipe_details(99999)

            assert "not found" in str(exc.value).lower()
