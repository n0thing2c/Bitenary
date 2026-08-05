from meal_plan.domain.entities import (
    MealPlan,
    MealPlanDraft,
    MealPlanPage,
    MealPlanSummary,
)


class MealPlanNotFoundError(Exception):
    """Raised when a requested MealPlan does not exist for the user."""


class InvalidMealPlanError(Exception):
    """Raised when business-rule validation fails on a MealPlanDraft."""
