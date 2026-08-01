"""Tests for ingredient master API endpoints.

Strategy: use Fake repository (no real DB needed) injected via
FastAPI dependency_overrides, following the same pattern as
test_health_profile_routes.py.
"""
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from ingredients.delivery.routes import get_ingredient_repo
from ingredients.domain.entities import IngredientMaster


# ---------------------------------------------------------------------------
# Fake repository
# ---------------------------------------------------------------------------

class FakeIngredientRepo:
    """In-memory stand-in for SqlAlchemyIngredientRepository."""

    def __init__(self, records: list[IngredientMaster] | None = None) -> None:
        self._records = records or _make_sample_data()

    async def search(
        self,
        *,
        q: str | None = None,
        category: str | None = None,
        only_default: bool = True,
        page: int = 1,
        size: int = 20,
    ) -> list[IngredientMaster]:
        results = list(self._records)

        if only_default:
            results = [r for r in results if r.is_default]

        if category:
            results = [r for r in results if r.category.lower() == category.lower()]

        if q:
            q_lower = q.lower()
            results = [
                r for r in results
                if q_lower in r.name.lower() or q_lower in r.variant.lower()
            ]

        start = (page - 1) * size
        return results[start : start + size]

    async def get_categories(self) -> list[str]:
        cats = sorted({r.category for r in self._records})
        return cats

    async def count(self) -> int:
        return len(self._records)


def _make_sample_data() -> list[IngredientMaster]:
    return [
        IngredientMaster(
            ingredient_id=uuid4(),
            name="Apples",
            variant="raw, with skin",
            category="Fruits and Fruit Juices",
            is_default=True,
        ),
        IngredientMaster(
            ingredient_id=uuid4(),
            name="Apples",
            variant="dried, sulfured, uncooked",
            category="Fruits and Fruit Juices",
            is_default=False,
        ),
        IngredientMaster(
            ingredient_id=uuid4(),
            name="Beef",
            variant="brisket, whole, separable lean only, all grades, raw",
            category="Beef Products",
            is_default=True,
        ),
        IngredientMaster(
            ingredient_id=uuid4(),
            name="Beef",
            variant="cured, dried",
            category="Sausages and Luncheon Meats",
            is_default=False,
        ),
        IngredientMaster(
            ingredient_id=uuid4(),
            name="Chicken",
            variant="broilers or fryers, meat only, raw",
            category="Poultry Products",
            is_default=True,
        ),
        IngredientMaster(
            ingredient_id=uuid4(),
            name="Milk",
            variant="whole, 3.25% milkfat, with added vitamin D",
            category="Dairy and Egg Products",
            is_default=True,
        ),
        IngredientMaster(
            ingredient_id=uuid4(),
            name="Garlic",
            variant="raw",
            category="Vegetables and Vegetable Products",
            is_default=True,
        ),
    ]


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def ingredients_client() -> tuple[TestClient, FakeIngredientRepo]:
    repo = FakeIngredientRepo()
    app = create_app()
    app.dependency_overrides[get_ingredient_repo] = lambda: repo
    with TestClient(app) as client:
        yield client, repo
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /api/ingredients (default behaviour)
# ---------------------------------------------------------------------------

def test_list_ingredients_returns_only_defaults_by_default(
    ingredients_client: tuple[TestClient, FakeIngredientRepo],
) -> None:
    client, _ = ingredients_client

    response = client.get("/api/ingredients")

    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 1
    assert all(item["is_default"] for item in data["items"]), (
        "only_default=true should return only default items"
    )


def test_list_ingredients_only_default_false_returns_all_variants(
    ingredients_client: tuple[TestClient, FakeIngredientRepo],
) -> None:
    client, repo = ingredients_client

    response = client.get("/api/ingredients?only_default=false")

    assert response.status_code == 200
    data = response.json()
    # Should include non-default variants too
    assert data["total_in_page"] == len(repo._records)


def test_search_by_name_returns_matching_items(
    ingredients_client: tuple[TestClient, FakeIngredientRepo],
) -> None:
    client, _ = ingredients_client

    response = client.get("/api/ingredients?q=apple&only_default=false")

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 2
    assert all("apple" in item["name"].lower() for item in items)


def test_search_by_variant_also_matches(
    ingredients_client: tuple[TestClient, FakeIngredientRepo],
) -> None:
    """Searching 'brisket' (which lives in the variant field) should still match."""
    client, _ = ingredients_client

    response = client.get("/api/ingredients?q=brisket&only_default=false")

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["name"] == "Beef"


def test_filter_by_category(
    ingredients_client: tuple[TestClient, FakeIngredientRepo],
) -> None:
    client, _ = ingredients_client

    response = client.get("/api/ingredients?category=Poultry Products&only_default=false")

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["name"] == "Chicken"


def test_filter_by_category_case_insensitive(
    ingredients_client: tuple[TestClient, FakeIngredientRepo],
) -> None:
    client, _ = ingredients_client

    response = client.get("/api/ingredients?category=poultry products&only_default=false")

    assert response.status_code == 200
    assert len(response.json()["items"]) == 1


def test_pagination_limits_results(
    ingredients_client: tuple[TestClient, FakeIngredientRepo],
) -> None:
    client, _ = ingredients_client

    response = client.get("/api/ingredients?only_default=false&size=2&page=1")

    assert response.status_code == 200
    data = response.json()
    assert data["size"] == 2
    assert len(data["items"]) == 2


def test_pagination_second_page(
    ingredients_client: tuple[TestClient, FakeIngredientRepo],
) -> None:
    client, repo = ingredients_client
    total = len(repo._records)

    response = client.get(f"/api/ingredients?only_default=false&size=5&page=2")

    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 2
    assert len(data["items"]) == total - 5  # remaining items


def test_empty_search_returns_no_results(
    ingredients_client: tuple[TestClient, FakeIngredientRepo],
) -> None:
    client, _ = ingredients_client

    response = client.get("/api/ingredients?q=xyznonexistent123")

    assert response.status_code == 200
    assert response.json()["items"] == []


def test_response_schema_contains_required_fields(
    ingredients_client: tuple[TestClient, FakeIngredientRepo],
) -> None:
    client, _ = ingredients_client

    response = client.get("/api/ingredients?q=garlic")

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert set(item.keys()) == {"ingredient_id", "name", "variant", "category", "is_default"}
    # ingredient_id must be a valid UUID
    UUID(item["ingredient_id"])


# ---------------------------------------------------------------------------
# GET /api/ingredients/categories
# ---------------------------------------------------------------------------

def test_categories_returns_sorted_unique_list(
    ingredients_client: tuple[TestClient, FakeIngredientRepo],
) -> None:
    client, _ = ingredients_client

    response = client.get("/api/ingredients/categories")

    assert response.status_code == 200
    cats = response.json()["categories"]
    assert isinstance(cats, list)
    assert len(cats) > 0
    # Must be sorted
    assert cats == sorted(cats)
    # Must be unique
    assert len(cats) == len(set(cats))


def test_categories_contains_expected_values(
    ingredients_client: tuple[TestClient, FakeIngredientRepo],
) -> None:
    client, _ = ingredients_client

    response = client.get("/api/ingredients/categories")

    cats = response.json()["categories"]
    assert "Fruits and Fruit Juices" in cats
    assert "Beef Products" in cats
    assert "Poultry Products" in cats
    assert "Dairy and Egg Products" in cats
