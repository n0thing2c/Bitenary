import pytest

from unittest.mock import AsyncMock, patch
import httpx

from bitenary_mcp.infrastructure.spoonacular import SpoonacularClient, SpoonacularError
from bitenary_mcp.domain.schemas import NutritionInformation


@pytest.fixture
def mock_settings(monkeypatch):
    monkeypatch.setenv("SPOONACULAR_API_KEY", "test-api-key")


@pytest.mark.anyio
async def test_get_nutrition_info_dish_success(mock_settings) -> None:
    """Test getting nutrition for a dish name using guessNutrition."""
    
    mock_response = httpx.Response(
        status_code=200, 
        json={
            "recipesUsed": 1,
            "calories": {"value": 391.0, "unit": "calories"},
            "fat": {"value": 9.0, "unit": "g"},
            "protein": {"value": 31.0, "unit": "g"},
            "carbs": {"value": 68.0, "unit": "g"},
        }
    )
    mock_response.request = httpx.Request("GET", "http://test")

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        async with SpoonacularClient("test-api-key") as client:
            info = await client.get_nutrition_info("pho", is_raw_ingredient=False)
            
            assert isinstance(info, NutritionInformation)
            assert info.calories.amount == 391.0
            assert info.protein.amount == 31.0
            
            # Verify the correct endpoint and params were called
            mock_get.assert_called_once()
            args, kwargs = mock_get.call_args
            assert args[0] == "/recipes/guessNutrition"
            assert kwargs["params"]["title"] == "pho"


@pytest.mark.anyio
async def test_get_nutrition_info_dish_error(mock_settings) -> None:
    """Test guessNutrition raising an error on bad response."""
    
    mock_response = httpx.Response(
        status_code=200, 
        json={"status": "error", "message": "Not enough data"}
    )
    mock_response.request = httpx.Request("GET", "http://test")

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        async with SpoonacularClient("test-api-key") as client:
            with pytest.raises(SpoonacularError) as exc:
                await client.get_nutrition_info("unknown dish", is_raw_ingredient=False)
            
            assert "guessNutrition error" in str(exc.value)


@pytest.mark.anyio
async def test_get_nutrition_info_ingredients_success(mock_settings) -> None:
    """Test getting nutrition for raw ingredients using parseIngredients."""
    
    mock_response = httpx.Response(
        status_code=200, 
        json=[
            {
                "nutrition": {
                    "nutrients": [
                        {"name": "Calories", "amount": 100.5, "unit": "kcal"},
                        {"name": "Protein", "amount": 10.0, "unit": "g"},
                        {"name": "Fat", "amount": 2.5, "unit": "g"},
                        {"name": "Carbohydrates", "amount": 1.0, "unit": "g"},
                    ]
                }
            },
            {
                "nutrition": {
                    "nutrients": [
                        {"name": "Calories", "amount": 50.0, "unit": "kcal"},
                        {"name": "Protein", "amount": 5.0, "unit": "g"},
                    ]
                }
            }
        ]
    )
    mock_response.request = httpx.Request("POST", "http://test")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        async with SpoonacularClient("test-api-key") as client:
            info = await client.get_nutrition_info("chicken and egg", is_raw_ingredient=True)
            
            assert isinstance(info, NutritionInformation)
            assert info.calories.amount == 150.5  # 100.5 + 50.0
            assert info.protein.amount == 15.0    # 10.0 + 5.0
            assert info.fat.amount == 2.5
            assert info.carbs.amount == 1.0
            
            # Verify the correct endpoint and data were called
            mock_post.assert_called_once()
            args, kwargs = mock_post.call_args
            assert args[0] == "/recipes/parseIngredients"
            assert kwargs["data"]["ingredientList"] == "chicken and egg"
            assert kwargs["data"]["includeNutrition"] == "true"
