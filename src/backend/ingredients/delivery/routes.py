from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db_session
from ingredients.delivery.dto import CategoriesOut, IngredientListOut, IngredientOut
from ingredients.infrastructure.sqlalchemy_ingredients import SqlAlchemyIngredientRepository

router = APIRouter(prefix="/ingredients", tags=["ingredients"])


def get_ingredient_repo(
    session: AsyncSession = Depends(get_db_session),
) -> SqlAlchemyIngredientRepository:
    return SqlAlchemyIngredientRepository(session)


@router.get("", response_model=IngredientListOut)
async def list_ingredients(
    q: str | None = Query(default=None, description="Search term (name or variant)"),
    category: str | None = Query(default=None, description="Filter by category name"),
    only_default: bool = Query(default=True, description="Return only default variants"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    repo: SqlAlchemyIngredientRepository = Depends(get_ingredient_repo),
) -> IngredientListOut:
    """Search ingredients. By default only returns one representative per ingredient."""
    items = await repo.search(
        q=q,
        category=category,
        only_default=only_default,
        page=page,
        size=size,
    )
    return IngredientListOut(
        items=[IngredientOut.model_validate(i.__dict__) for i in items],
        page=page,
        size=size,
        total_in_page=len(items),
    )


@router.get("/categories", response_model=CategoriesOut)
async def list_categories(
    repo: SqlAlchemyIngredientRepository = Depends(get_ingredient_repo),
) -> CategoriesOut:
    """Return all available ingredient categories for filtering UI."""
    cats = await repo.get_categories()
    return CategoriesOut(categories=cats)
