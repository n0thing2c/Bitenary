from typing import Protocol
from uuid import UUID

from meal_plan.domain.entities import MealPlan, MealPlanDraft, MealPlanPage, MealPlanSummary


class MealPlanRepository(Protocol):
    async def create(self, *, user_id: UUID, draft: MealPlanDraft) -> MealPlan:
        raise NotImplementedError

    async def get(self, *, user_id: UUID, plan_id: UUID) -> MealPlan | None:
        raise NotImplementedError

    async def list_plans(
        self,
        *,
        user_id: UUID,
        page: int,
        size: int,
    ) -> MealPlanPage:
        raise NotImplementedError

    async def delete(self, *, user_id: UUID, plan_id: UUID) -> bool:
        raise NotImplementedError
