from uuid import UUID

from pydantic import BaseModel


class IngredientOut(BaseModel):
    ingredient_id: UUID
    name: str
    variant: str
    category: str
    is_default: bool

    model_config = {"from_attributes": True}


class IngredientListOut(BaseModel):
    items: list[IngredientOut]
    page: int
    size: int
    total_in_page: int


class CategoriesOut(BaseModel):
    categories: list[str]
