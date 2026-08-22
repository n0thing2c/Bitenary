"""Data Transfer Objects for the Meal Plan delivery layer."""

from __future__ import annotations

from datetime import date, datetime
from math import ceil
from uuid import UUID

from pydantic import BaseModel

from meal_plan.domain.entities import (
    MealPlan,
    MealPlanPage,
    MealPlanSummary,
    MealType,
)


# ---------------------------------------------------------------------------
# Response models (API → Client)
# ---------------------------------------------------------------------------


class MealIngredientResponse(BaseModel):
    name: str
    quantity: str


class PlannedMealResponse(BaseModel):
    meal_type: MealType
    dish_name: str
    description: str
    estimated_calories: int
    ingredients: list[MealIngredientResponse]


class DayPlanResponse(BaseModel):
    date: date
    total_calories: int
    meals: list[PlannedMealResponse]


class MealPlanDetailResponse(BaseModel):
    plan_id: UUID
    title: str
    start_date: date
    end_date: date
    total_calories: int
    days: list[DayPlanResponse]
    created_at: datetime


class MealPlanSummaryResponse(BaseModel):
    plan_id: UUID
    title: str
    start_date: date
    end_date: date
    total_calories: int
    created_at: datetime


class MealPlanListResponse(BaseModel):
    items: list[MealPlanSummaryResponse]
    page: int
    size: int
    total: int
    total_pages: int


# ---------------------------------------------------------------------------
# Mappers (Domain → Response)
# ---------------------------------------------------------------------------


def plan_detail_response(plan: MealPlan) -> MealPlanDetailResponse:
    return MealPlanDetailResponse(
        plan_id=plan.plan_id,
        title=plan.title,
        start_date=plan.start_date,
        end_date=plan.end_date,
        total_calories=plan.total_calories,
        days=[
            DayPlanResponse(
                date=day.date,
                total_calories=day.total_calories,
                meals=[
                    PlannedMealResponse(
                        meal_type=meal.meal_type,
                        dish_name=meal.dish_name,
                        description=meal.description,
                        estimated_calories=meal.estimated_calories,
                        ingredients=[
                            MealIngredientResponse(name=ing.name, quantity=ing.quantity)
                            for ing in meal.ingredients
                        ],
                    )
                    for meal in day.meals
                ],
            )
            for day in plan.days
        ],
        created_at=plan.created_at,
    )


def plan_summary_response(summary: MealPlanSummary) -> MealPlanSummaryResponse:
    return MealPlanSummaryResponse(
        plan_id=summary.plan_id,
        title=summary.title,
        start_date=summary.start_date,
        end_date=summary.end_date,
        total_calories=summary.total_calories,
        created_at=summary.created_at,
    )


def plan_list_response(result: MealPlanPage) -> MealPlanListResponse:
    return MealPlanListResponse(
        items=[plan_summary_response(item) for item in result.items],
        page=result.page,
        size=result.size,
        total=result.total,
        total_pages=ceil(result.total / result.size) if result.total else 0,
    )
