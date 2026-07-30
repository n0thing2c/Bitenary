from dataclasses import dataclass


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
