"""Business logic for creating and retrieving Meal Plans."""

from __future__ import annotations

from uuid import UUID

from meal_plan.domain.entities import (
    DayPlan,
    MealPlan,
    MealPlanDraft,
    MealPlanPage,
    MealPlanSummary,
    PlannedMeal,
)
from meal_plan.domain.errors import InvalidMealPlanError, MealPlanNotFoundError
from meal_plan.repository.meal_plans import MealPlanRepository

_MAX_DAYS = 14
_MAX_TITLE_LEN = 100


class MealPlanService:
    def __init__(self, repository: MealPlanRepository) -> None:
        self._repository = repository

    async def create_plan(
        self,
        *,
        user_id: UUID,
        draft: MealPlanDraft,
    ) -> MealPlan:
        """Validate and persist a new meal plan."""
        _validate_draft(draft)
        return await self._repository.create(user_id=user_id, draft=draft)

    async def get_plan(self, *, user_id: UUID, plan_id: UUID) -> MealPlan:
        plan = await self._repository.get(user_id=user_id, plan_id=plan_id)
        if plan is None:
            raise MealPlanNotFoundError("Meal plan was not found")
        return plan

    async def list_plans(
        self,
        *,
        user_id: UUID,
        page: int = 1,
        size: int = 20,
    ) -> MealPlanPage:
        return await self._repository.list_plans(user_id=user_id, page=page, size=size)

    async def delete_plan(self, *, user_id: UUID, plan_id: UUID) -> None:
        deleted = await self._repository.delete(user_id=user_id, plan_id=plan_id)
        if not deleted:
            raise MealPlanNotFoundError("Meal plan was not found")


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_draft(draft: MealPlanDraft) -> None:
    title = " ".join(draft.title.split())
    if not title:
        raise InvalidMealPlanError("title must not be blank")
    if len(title) > _MAX_TITLE_LEN:
        raise InvalidMealPlanError(f"title must not exceed {_MAX_TITLE_LEN} characters")
    if draft.start_date > draft.end_date:
        raise InvalidMealPlanError("start_date must be on or before end_date")
    num_days = (draft.end_date - draft.start_date).days + 1
    if num_days > _MAX_DAYS:
        raise InvalidMealPlanError(
            f"A meal plan may span at most {_MAX_DAYS} days; "
            f"this one spans {num_days}."
        )
    if not draft.days:
        raise InvalidMealPlanError("days must not be empty")
    for day in draft.days:
        if not day.meals:
            raise InvalidMealPlanError(
                f"Day {day.date.isoformat()} must have at least one meal"
            )


def make_draft(
    *,
    title: str,
    days: tuple[DayPlan, ...],
) -> MealPlanDraft:
    """Construct a ``MealPlanDraft`` from raw AI tool input."""
    if not days:
        raise InvalidMealPlanError("days must not be empty")
    sorted_days = tuple(sorted(days, key=lambda d: d.date))
    start_date = sorted_days[0].date
    end_date = sorted_days[-1].date
    return MealPlanDraft(
        title=" ".join(title.split()),
        start_date=start_date,
        end_date=end_date,
        days=sorted_days,
    )
