"""MCP tool: save_meal_plan

Allows authenticated AI agents to persist a structured multi-day meal plan
into the Bitenary database on behalf of the current user. The tool enforces
a strict JSON schema via Pydantic so the LLM cannot write malformed data.

Security
--------
Uses ``current_principal()`` to resolve the caller's ``user_id`` from the
verified MCP Bearer token — a plan can only be saved for the authenticated
user, never for someone else.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import date
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from bitenary_mcp.service.auditing import MCPInvocationAuditor
from bitenary_mcp.tools.status import current_principal
from meal_plan.domain.entities import (
    DayPlan,
    MealIngredient,
    MealPlanDraft,
    MealType,
    PlannedMeal,
)
from meal_plan.domain.errors import InvalidMealPlanError
from meal_plan.infrastructure.sqlalchemy_meal_plan import SqlAlchemyMealPlanRepository
from meal_plan.service.meal_plans import MealPlanService, make_draft


TOOL_NAME = "save_meal_plan"


# ---------------------------------------------------------------------------
# Strict input schema — the LLM MUST conform to this
# ---------------------------------------------------------------------------


class IngredientInput(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    quantity: str = Field(
        min_length=1,
        max_length=64,
        description="Human-readable quantity string, e.g. '200g', '2 eggs', '1 cup'",
    )


class MealInput(BaseModel):
    meal_type: MealType
    dish_name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=512)
    estimated_calories: int = Field(ge=0, le=5000)
    ingredients: list[IngredientInput] = Field(default_factory=list, max_length=30)


class DayInput(BaseModel):
    date: date
    meals: list[MealInput] = Field(min_length=1, max_length=6)


class SaveMealPlanInput(BaseModel):
    """Structured input for the save_meal_plan MCP tool."""

    title: str = Field(
        min_length=1,
        max_length=100,
        description="Short descriptive name for this meal plan, e.g. 'Weight-loss week plan'",
    )
    days: list[DayInput] = Field(
        min_length=1,
        max_length=14,
        description="List of days in the plan, each with one or more meals.",
    )

    @model_validator(mode="after")
    def dates_must_be_consecutive_range(self) -> "SaveMealPlanInput":
        """Ensure no duplicate dates."""
        seen = set()
        for day in self.days:
            if day.date in seen:
                raise ValueError(f"Duplicate date in meal plan: {day.date}")
            seen.add(day.date)
        return self


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def build_save_meal_plan_tool(
    auditor: MCPInvocationAuditor,
    session_factory: Any,
) -> Callable[..., Awaitable[dict]]:
    """Return a ready-to-register ``save_meal_plan`` MCP tool function.

    Args:
        auditor: Shared invocation auditor that logs every tool call to the DB.
        session_factory: Async SQLAlchemy session factory (``AsyncSessionLocal``).

    Returns:
        An async callable suitable for ``mcp_server.add_tool(...)``.
    """

    @asynccontextmanager
    async def _session_scope():
        async with session_factory() as session:
            repo = SqlAlchemyMealPlanRepository(session)
            yield MealPlanService(repo)

    async def save_meal_plan(
        title: str,
        days: str,
    ) -> dict:
        """Save a structured multi-day meal plan to the user's Bitenary account.

        Call this tool ONLY after the user has explicitly confirmed and approved
        a meal plan. Do NOT save a plan unless the user says something like
        "save this", "lock it in", "looks good, save it", or equivalent.

        Args:
            title: A short, descriptive name for this meal plan.
                Example: ``"High-protein week plan"``
            days: A JSON string representing a list of day objects.
                Each day must follow this exact schema::

                    [
                      {
                        "date": "YYYY-MM-DD",
                        "meals": [
                          {
                            "meal_type": "BREAKFAST",
                            "dish_name": "Oatmeal with banana",
                            "description": "Healthy fibre-rich breakfast",
                            "estimated_calories": 350,
                            "ingredients": [
                              {"name": "Rolled oats", "quantity": "80g"},
                              {"name": "Banana", "quantity": "1 medium"}
                            ]
                          }
                        ]
                      }
                    ]

                Valid ``meal_type`` values: ``BREAKFAST``, ``LUNCH``, ``DINNER``, ``SNACK``.

        Returns:
            A confirmation dict::

                {
                    "success": true,
                    "plan_id": "<uuid>",
                    "title": "High-protein week plan",
                    "start_date": "2026-08-05",
                    "end_date": "2026-08-11",
                    "total_calories": 12600,
                    "num_days": 7
                }

        Raises:
            ValueError: If the ``days`` JSON is malformed or fails validation.
        """
        principal = current_principal()

        async def save_operation() -> dict:
            # Parse and validate the JSON input from the LLM
            try:
                days_data = json.loads(days)
            except json.JSONDecodeError as exc:
                raise ValueError(f"days must be a valid JSON string: {exc}") from exc

            try:
                parsed = SaveMealPlanInput(title=title, days=days_data)
            except Exception as exc:
                raise ValueError(f"Meal plan validation failed: {exc}") from exc

            # Convert Pydantic input → Domain objects
            domain_days = tuple(
                DayPlan(
                    date=day_input.date,
                    meals=tuple(
                        PlannedMeal(
                            meal_type=meal_input.meal_type,
                            dish_name=meal_input.dish_name,
                            description=meal_input.description,
                            estimated_calories=meal_input.estimated_calories,
                            ingredients=tuple(
                                MealIngredient(
                                    name=ing.name,
                                    quantity=ing.quantity,
                                )
                                for ing in meal_input.ingredients
                            ),
                        )
                        for meal_input in day_input.meals
                    ),
                )
                for day_input in parsed.days
            )

            try:
                draft: MealPlanDraft = make_draft(title=parsed.title, days=domain_days)
            except InvalidMealPlanError as exc:
                raise ValueError(str(exc)) from exc

            async with _session_scope() as service:
                plan = await service.create_plan(
                    user_id=principal.user_id,
                    draft=draft,
                )

            return {
                "success": True,
                "plan_id": str(plan.plan_id),
                "title": plan.title,
                "start_date": plan.start_date.isoformat(),
                "end_date": plan.end_date.isoformat(),
                "total_calories": plan.total_calories,
                "num_days": len(plan.days),
            }

        return await auditor.invoke(
            principal=principal,
            tool_name=TOOL_NAME,
            operation=save_operation,
        )

    save_meal_plan.__name__ = TOOL_NAME
    return save_meal_plan
