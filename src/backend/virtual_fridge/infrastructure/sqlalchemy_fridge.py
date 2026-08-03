from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    case,
    delete,
    func,
    or_,
    select,
)
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base
from identity.infrastructure.sqlalchemy_users import UserModel
from ingredients.infrastructure.sqlalchemy_ingredients import (
    IngredientMasterModel,
)
from virtual_fridge.domain.entities import (
    CategoryCount,
    ExpiryStatus,
    FoodState,
    FridgeItem,
    FridgeItemDraft,
    FridgeItemPage,
    FridgeItemSort,
    FridgeSummary,
    IngredientSummary,
)
from virtual_fridge.repository.fridge_items import FridgeItemRepository


class FridgeItemModel(Base):
    __tablename__ = "fridge_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="fridge_items_quantity_positive"),
        Index("ix_fridge_items_user_expiry", "user_id", "expiry_date"),
        Index("ix_fridge_items_user_ingredient", "user_id", "ingredient_id"),
        Index("ix_fridge_items_user_updated", "user_id", "updated_at"),
    )

    fridge_item_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey(UserModel.user_id, ondelete="CASCADE"),
        nullable=False,
    )
    ingredient_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey(IngredientMasterModel.ingredient_id, ondelete="RESTRICT"),
        nullable=False,
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    food_state: Mapped[FoodState | None] = mapped_column(
        Enum(FoodState, name="virtual_fridge_food_state"),
        nullable=True,
    )
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


def to_domain(model: FridgeItemModel, ingredient: IngredientMasterModel) -> FridgeItem:
    return FridgeItem(
        fridge_item_id=model.fridge_item_id,
        user_id=model.user_id,
        ingredient=IngredientSummary(
            ingredient_id=ingredient.ingredient_id,
            name=ingredient.name,
            variant=ingredient.variant,
            category=ingredient.category,
        ),
        quantity=model.quantity,
        unit=model.unit,
        food_state=model.food_state,
        expiry_date=model.expiry_date,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SqlAlchemyFridgeItemRepository(FridgeItemRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def ingredient_exists(self, ingredient_id: UUID) -> bool:
        return await self._session.get(IngredientMasterModel, ingredient_id) is not None

    async def create(self, *, user_id: UUID, draft: FridgeItemDraft) -> FridgeItem:
        model = FridgeItemModel(
            user_id=user_id,
            ingredient_id=draft.ingredient_id,
            quantity=draft.quantity,
            unit=draft.unit,
            food_state=draft.food_state,
            expiry_date=draft.expiry_date,
        )
        self._session.add(model)
        await self._session.commit()
        item = await self.get(user_id=user_id, fridge_item_id=model.fridge_item_id)
        if item is None:  # pragma: no cover - defensive invariant
            raise RuntimeError("Created fridge item could not be reloaded")
        return item

    async def get(self, *, user_id: UUID, fridge_item_id: UUID) -> FridgeItem | None:
        stmt = (
            select(FridgeItemModel, IngredientMasterModel)
            .join(
                IngredientMasterModel,
                IngredientMasterModel.ingredient_id == FridgeItemModel.ingredient_id,
            )
            .where(
                FridgeItemModel.fridge_item_id == fridge_item_id,
                FridgeItemModel.user_id == user_id,
            )
        )
        row = (await self._session.execute(stmt)).one_or_none()
        return to_domain(*row) if row is not None else None

    async def save(
        self,
        *,
        user_id: UUID,
        fridge_item_id: UUID,
        draft: FridgeItemDraft,
    ) -> FridgeItem | None:
        result = await self._session.execute(
            select(FridgeItemModel).where(
                FridgeItemModel.fridge_item_id == fridge_item_id,
                FridgeItemModel.user_id == user_id,
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        model.ingredient_id = draft.ingredient_id
        model.quantity = draft.quantity
        model.unit = draft.unit
        model.food_state = draft.food_state
        model.expiry_date = draft.expiry_date
        model.updated_at = func.now()
        await self._session.commit()
        return await self.get(user_id=user_id, fridge_item_id=fridge_item_id)

    async def delete(self, *, user_id: UUID, fridge_item_id: UUID) -> bool:
        result = await self._session.execute(
            delete(FridgeItemModel).where(
                FridgeItemModel.fridge_item_id == fridge_item_id,
                FridgeItemModel.user_id == user_id,
            )
        )
        await self._session.commit()
        return bool(result.rowcount)

    async def list_items(
        self,
        *,
        user_id: UUID,
        q: str | None,
        category: str | None,
        expiry_status: ExpiryStatus | None,
        food_state: FoodState | None,
        sort: FridgeItemSort,
        page: int,
        size: int,
        today: date,
        warning_days: int,
    ) -> FridgeItemPage:
        conditions = [FridgeItemModel.user_id == user_id]
        if q:
            pattern = f"%{q.casefold()}%"
            conditions.append(
                or_(
                    func.lower(IngredientMasterModel.name).like(pattern),
                    func.lower(IngredientMasterModel.variant).like(pattern),
                )
            )
        if category:
            conditions.append(
                func.lower(IngredientMasterModel.category) == category.casefold()
            )
        if food_state is not None:
            conditions.append(FridgeItemModel.food_state == food_state)
        if expiry_status is not None:
            conditions.append(
                _expiry_condition(
                    expiry_status,
                    today=today,
                    warning_days=warning_days,
                )
            )

        count_stmt = (
            select(func.count())
            .select_from(FridgeItemModel)
            .join(
                IngredientMasterModel,
                IngredientMasterModel.ingredient_id == FridgeItemModel.ingredient_id,
            )
            .where(*conditions)
        )
        total = (await self._session.execute(count_stmt)).scalar_one()

        order_by = {
            FridgeItemSort.EXPIRY_ASC: (
                FridgeItemModel.expiry_date.asc(),
                IngredientMasterModel.name.asc(),
            ),
            FridgeItemSort.EXPIRY_DESC: (
                FridgeItemModel.expiry_date.desc(),
                IngredientMasterModel.name.asc(),
            ),
            FridgeItemSort.NAME_ASC: (
                IngredientMasterModel.name.asc(),
                FridgeItemModel.expiry_date.asc(),
            ),
            FridgeItemSort.UPDATED_DESC: (
                FridgeItemModel.updated_at.desc(),
                FridgeItemModel.fridge_item_id.asc(),
            ),
        }[sort]
        stmt = (
            select(FridgeItemModel, IngredientMasterModel)
            .join(
                IngredientMasterModel,
                IngredientMasterModel.ingredient_id == FridgeItemModel.ingredient_id,
            )
            .where(*conditions)
            .order_by(*order_by)
            .offset((page - 1) * size)
            .limit(size)
        )
        rows = (await self._session.execute(stmt)).all()
        return FridgeItemPage(
            items=tuple(to_domain(*row) for row in rows),
            page=page,
            size=size,
            total=total,
        )

    async def summarize(
        self,
        *,
        user_id: UUID,
        today: date,
        warning_days: int,
    ) -> FridgeSummary:
        soon_date = today + timedelta(days=warning_days)
        summary_stmt = select(
            func.count(FridgeItemModel.fridge_item_id),
            func.sum(case((FridgeItemModel.expiry_date > soon_date, 1), else_=0)),
            func.sum(
                case(
                    (
                        (FridgeItemModel.expiry_date > today)
                        & (FridgeItemModel.expiry_date <= soon_date),
                        1,
                    ),
                    else_=0,
                )
            ),
            func.sum(case((FridgeItemModel.expiry_date == today, 1), else_=0)),
            func.sum(case((FridgeItemModel.expiry_date < today, 1), else_=0)),
        ).where(FridgeItemModel.user_id == user_id)
        total, fresh, soon, today_count, expired = (
            await self._session.execute(summary_stmt)
        ).one()

        category_stmt = (
            select(IngredientMasterModel.category, func.count())
            .select_from(FridgeItemModel)
            .join(
                IngredientMasterModel,
                IngredientMasterModel.ingredient_id == FridgeItemModel.ingredient_id,
            )
            .where(FridgeItemModel.user_id == user_id)
            .group_by(IngredientMasterModel.category)
            .order_by(IngredientMasterModel.category)
        )
        category_rows = (await self._session.execute(category_stmt)).all()
        return FridgeSummary(
            total_items=int(total or 0),
            fresh=int(fresh or 0),
            expiring_soon=int(soon or 0),
            expiring_today=int(today_count or 0),
            expired=int(expired or 0),
            categories=tuple(
                CategoryCount(category=category, count=int(count))
                for category, count in category_rows
            ),
        )

    async def list_available(
        self,
        *,
        user_id: UUID,
        today: date,
    ) -> tuple[FridgeItem, ...]:
        stmt = (
            select(FridgeItemModel, IngredientMasterModel)
            .join(
                IngredientMasterModel,
                IngredientMasterModel.ingredient_id == FridgeItemModel.ingredient_id,
            )
            .where(
                FridgeItemModel.user_id == user_id,
                FridgeItemModel.expiry_date >= today,
            )
            .order_by(FridgeItemModel.expiry_date, IngredientMasterModel.name)
        )
        rows = (await self._session.execute(stmt)).all()
        return tuple(to_domain(*row) for row in rows)


def _expiry_condition(
    status: ExpiryStatus,
    *,
    today: date,
    warning_days: int,
):
    soon_date = today + timedelta(days=warning_days)
    if status == ExpiryStatus.EXPIRED:
        return FridgeItemModel.expiry_date < today
    if status == ExpiryStatus.EXPIRING_TODAY:
        return FridgeItemModel.expiry_date == today
    if status == ExpiryStatus.EXPIRING_SOON:
        return (FridgeItemModel.expiry_date > today) & (
            FridgeItemModel.expiry_date <= soon_date
        )
    return FridgeItemModel.expiry_date > soon_date
