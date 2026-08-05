"""Domain entities for the Meal Plan module.

A ``MealPlan`` represents a multi-day eating schedule that the AI generates
and persists on the user's behalf. The structured ``plan_data`` field is
intentionally typed via nested Pydantic-compatible dataclasses so that
the MCP tool can enforce a strict JSON schema before writing to the DB.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from uuid import UUID


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class MealType(StrEnum):
    BREAKFAST = "BREAKFAST"
    LUNCH = "LUNCH"
    DINNER = "DINNER"
    SNACK = "SNACK"


# ---------------------------------------------------------------------------
# Plan data — nested structures that live inside the JSONB column
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MealIngredient:
    """A single ingredient used in a meal."""

    name: str
    quantity: str  # Free text e.g. "200g", "2 eggs"


@dataclass(frozen=True)
class PlannedMeal:
    """One meal in a day's schedule (e.g. Breakfast on Monday)."""

    meal_type: MealType
    dish_name: str
    description: str
    estimated_calories: int
    ingredients: tuple[MealIngredient, ...]


@dataclass(frozen=True)
class DayPlan:
    """All meals planned for a single date."""

    date: date
    meals: tuple[PlannedMeal, ...]

    @property
    def total_calories(self) -> int:
        return sum(m.estimated_calories for m in self.meals)


# ---------------------------------------------------------------------------
# Aggregate root & draft
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MealPlanDraft:
    """Validated input for creating a new MealPlan (no DB identifiers yet)."""

    title: str
    start_date: date
    end_date: date
    days: tuple[DayPlan, ...]

    @property
    def total_calories(self) -> int:
        return sum(d.total_calories for d in self.days)


@dataclass(frozen=True)
class MealPlan:
    """Persisted meal plan as retrieved from the database."""

    plan_id: UUID
    user_id: UUID
    title: str
    start_date: date
    end_date: date
    total_calories: int
    days: tuple[DayPlan, ...]
    created_at: datetime


@dataclass(frozen=True)
class MealPlanSummary:
    """Lightweight projection for list endpoints (no day details)."""

    plan_id: UUID
    user_id: UUID
    title: str
    start_date: date
    end_date: date
    total_calories: int
    created_at: datetime


@dataclass(frozen=True)
class MealPlanPage:
    items: tuple[MealPlanSummary, ...]
    page: int
    size: int
    total: int
