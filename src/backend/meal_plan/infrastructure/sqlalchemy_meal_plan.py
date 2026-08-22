"""SQLAlchemy ORM model and repository for the Meal Plan module.

``plan_data`` is stored as JSONB and serialised/deserialised using the
helper functions ``_days_to_json`` / ``_days_from_json``. This keeps the
DB column fully typed while letting the domain layer stay free of ORM deps.
"""

from __future__ import annotations

from datetime import date, datetime
from math import ceil
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, Index, Integer, String, delete, func, select
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgresUUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base
from identity.infrastructure.sqlalchemy_users import UserModel
from meal_plan.domain.entities import (
    DayPlan,
    MealIngredient,
    MealPlan,
    MealPlanDraft,
    MealPlanPage,
    MealPlanSummary,
    MealType,
    PlannedMeal,
)
from meal_plan.repository.meal_plans import MealPlanRepository


class MealPlanModel(Base):
    __tablename__ = "meal_plans"
    __table_args__ = (
        Index("ix_meal_plans_user_start", "user_id", "start_date"),
        Index("ix_meal_plans_user_created", "user_id", "created_at"),
    )

    plan_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        # No FK enforced at DB level for now — avoids hard dependency on UserModel
        # being in the same Alembic revision. Can be added later.
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_calories: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    plan_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


# ---------------------------------------------------------------------------
# JSON serialisation helpers (Domain <-> JSONB)
# ---------------------------------------------------------------------------


def _days_to_json(days: tuple[DayPlan, ...]) -> list[dict]:
    return [
        {
            "date": day.date.isoformat(),
            "meals": [
                {
                    "meal_type": meal.meal_type.value,
                    "dish_name": meal.dish_name,
                    "description": meal.description,
                    "estimated_calories": meal.estimated_calories,
                    "ingredients": [
                        {"name": ing.name, "quantity": ing.quantity}
                        for ing in meal.ingredients
                    ],
                }
                for meal in day.meals
            ],
        }
        for day in days
    ]


def _days_from_json(data: list[dict]) -> tuple[DayPlan, ...]:
    days = []
    for day_dict in data:
        meals = []
        for m in day_dict["meals"]:
            ingredients = tuple(
                MealIngredient(name=ing["name"], quantity=ing["quantity"])
                for ing in m.get("ingredients", [])
            )
            meals.append(
                PlannedMeal(
                    meal_type=MealType(m["meal_type"]),
                    dish_name=m["dish_name"],
                    description=m.get("description", ""),
                    estimated_calories=int(m.get("estimated_calories", 0)),
                    ingredients=ingredients,
                )
            )
        days.append(
            DayPlan(
                date=date.fromisoformat(day_dict["date"]),
                meals=tuple(meals),
            )
        )
    return tuple(days)


def _to_domain(model: MealPlanModel) -> MealPlan:
    days = _days_from_json(model.plan_data.get("days", []))
    return MealPlan(
        plan_id=model.plan_id,
        user_id=model.user_id,
        title=model.title,
        start_date=model.start_date,
        end_date=model.end_date,
        total_calories=model.total_calories,
        days=days,
        created_at=model.created_at,
    )


def _to_summary(model: MealPlanModel) -> MealPlanSummary:
    return MealPlanSummary(
        plan_id=model.plan_id,
        user_id=model.user_id,
        title=model.title,
        start_date=model.start_date,
        end_date=model.end_date,
        total_calories=model.total_calories,
        created_at=model.created_at,
    )


# ---------------------------------------------------------------------------
# Repository implementation
# ---------------------------------------------------------------------------


class SqlAlchemyMealPlanRepository(MealPlanRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, *, user_id: UUID, draft: MealPlanDraft) -> MealPlan:
        model = MealPlanModel(
            user_id=user_id,
            title=draft.title,
            start_date=draft.start_date,
            end_date=draft.end_date,
            total_calories=draft.total_calories,
            plan_data={"days": _days_to_json(draft.days)},
        )
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return _to_domain(model)

    async def get(self, *, user_id: UUID, plan_id: UUID) -> MealPlan | None:
        model = await self._session.get(MealPlanModel, plan_id)
        if model is None or model.user_id != user_id:
            return None
        return _to_domain(model)

    async def list_plans(
        self,
        *,
        user_id: UUID,
        page: int,
        size: int,
    ) -> MealPlanPage:
        count_stmt = (
            select(func.count())
            .select_from(MealPlanModel)
            .where(MealPlanModel.user_id == user_id)
        )
        total = (await self._session.execute(count_stmt)).scalar_one()

        stmt = (
            select(MealPlanModel)
            .where(MealPlanModel.user_id == user_id)
            .order_by(MealPlanModel.start_date.desc(), MealPlanModel.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        rows = (await self._session.scalars(stmt)).all()
        return MealPlanPage(
            items=tuple(_to_summary(r) for r in rows),
            page=page,
            size=size,
            total=total,
        )

    async def delete(self, *, user_id: UUID, plan_id: UUID) -> bool:
        result = await self._session.execute(
            delete(MealPlanModel).where(
                MealPlanModel.plan_id == plan_id,
                MealPlanModel.user_id == user_id,
            )
        )
        await self._session.commit()
        return bool(result.rowcount)
