from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class IngredientMaster:
    ingredient_id: UUID
    name: str
    variant: str
    category: str
    is_default: bool
