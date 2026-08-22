from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db_session
from meal_plan.infrastructure.sqlalchemy_meal_plan import SqlAlchemyMealPlanRepository
from meal_plan.repository.meal_plans import MealPlanRepository
from meal_plan.service.meal_plans import MealPlanService


def get_meal_plan_repository(
    session: AsyncSession = Depends(get_db_session),
) -> MealPlanRepository:
    return SqlAlchemyMealPlanRepository(session)


def get_meal_plan_service(
    repository: MealPlanRepository = Depends(get_meal_plan_repository),
) -> MealPlanService:
    return MealPlanService(repository)
