from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from identity.domain.entities import CurrentUser
from identity.wiring import get_current_user
from meal_plan.delivery.dto import (
    MealPlanDetailResponse,
    MealPlanListResponse,
    plan_detail_response,
    plan_list_response,
)
from meal_plan.domain.errors import MealPlanNotFoundError
from meal_plan.service.meal_plans import MealPlanService
from meal_plan.wiring import get_meal_plan_service


router = APIRouter(prefix="/meal-plans", tags=["meal-plans"])


@router.get("", response_model=MealPlanListResponse)
async def list_meal_plans(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
    service: MealPlanService = Depends(get_meal_plan_service),
) -> MealPlanListResponse:
    """List all meal plans saved by the authenticated user.

    Returns a paginated list of summaries (no day-by-day details).
    Ordered by start date descending — most recent plan first.
    """
    result = await service.list_plans(
        user_id=current_user.user_id,
        page=page,
        size=size,
    )
    return plan_list_response(result)


@router.get("/{plan_id}", response_model=MealPlanDetailResponse)
async def get_meal_plan(
    plan_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: MealPlanService = Depends(get_meal_plan_service),
) -> MealPlanDetailResponse:
    """Retrieve the full details of a single meal plan, including all days and meals."""
    try:
        plan = await service.get_plan(
            user_id=current_user.user_id,
            plan_id=plan_id,
        )
    except MealPlanNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Meal plan was not found") from exc
    return plan_detail_response(plan)


@router.delete("/{plan_id}", status_code=204)
async def delete_meal_plan(
    plan_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: MealPlanService = Depends(get_meal_plan_service),
) -> None:
    """Delete a meal plan owned by the authenticated user."""
    try:
        await service.delete_plan(
            user_id=current_user.user_id,
            plan_id=plan_id,
        )
    except MealPlanNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Meal plan was not found") from exc
