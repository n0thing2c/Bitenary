from dataclasses import dataclass, field


@dataclass(frozen=True)
class NutrientValue:
    """A single nutrient measurement returned by Spoonacular."""

    amount: float
    unit: str


@dataclass(frozen=True)
class NutritionInformation:
    """Complete nutritional breakdown for a dish or ingredient query."""

    calories: NutrientValue
    protein: NutrientValue
    fat: NutrientValue
    carbs: NutrientValue

    def to_dict(self) -> dict[str, dict[str, float | str]]:
        return {
            "calories": {"amount": self.calories.amount, "unit": self.calories.unit},
            "protein": {"amount": self.protein.amount, "unit": self.protein.unit},
            "fat": {"amount": self.fat.amount, "unit": self.fat.unit},
            "carbs": {"amount": self.carbs.amount, "unit": self.carbs.unit},
        }


@dataclass(frozen=True)
class RecipeSummary:
    """A brief overview of a recipe returned by the search tool."""

    id: int
    title: str
    image: str
    ready_in_minutes: int
    calories: float
    protein: float
    fat: float
    carbs: float

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "image": self.image,
            "ready_in_minutes": self.ready_in_minutes,
            "nutrition": {
                "calories": self.calories,
                "protein_g": self.protein,
                "fat_g": self.fat,
                "carbs_g": self.carbs,
            },
        }


@dataclass(frozen=True)
class RecipeIngredient:
    """A single ingredient entry in a recipe."""

    name: str
    original: str  # e.g. "2 cups of all-purpose flour"
    amount: float
    unit: str


@dataclass(frozen=True)
class RecipeInstructionStep:
    """A single step in a recipe's instructions."""

    number: int
    step: str


@dataclass(frozen=True)
class RecipeDetails:
    """Full recipe information including ingredients and step-by-step instructions."""

    id: int
    title: str
    source_url: str
    image: str
    ready_in_minutes: int
    servings: int
    ingredients: tuple[RecipeIngredient, ...]
    instructions: tuple[RecipeInstructionStep, ...]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "source_url": self.source_url,
            "image": self.image,
            "ready_in_minutes": self.ready_in_minutes,
            "servings": self.servings,
            "ingredients": [
                {
                    "name": ing.name,
                    "original": ing.original,
                    "amount": ing.amount,
                    "unit": ing.unit,
                }
                for ing in self.ingredients
            ],
            "instructions": [
                {"step_number": s.number, "description": s.step}
                for s in self.instructions
            ],
        }
