from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from virtual_fridge.domain.entities import (
    DEFAULT_EXPIRY_WARNING_DAYS,
    ExpiryStatus,
    FoodState,
    FridgeItem,
    FridgeItemDraft,
    FridgeItemPage,
    FridgeItemSort,
    FridgeSummary,
)
from virtual_fridge.domain.errors import (
    FridgeItemNotFoundError,
    IngredientNotFoundError,
    InvalidFridgeItemError,
)
from virtual_fridge.repository.fridge_items import FridgeItemRepository


class VirtualFridgeService:
    def __init__(
        self,
        repository: FridgeItemRepository,
        *,
        warning_days: int = DEFAULT_EXPIRY_WARNING_DAYS,
    ) -> None:
        self._repository = repository
        self._warning_days = warning_days

    async def create_item(
        self,
        *,
        user_id: UUID,
        ingredient_id: UUID,
        quantity: Decimal,
        unit: str,
        food_state: FoodState | None,
        expiry_date: date,
    ) -> FridgeItem:
        if not await self._repository.ingredient_exists(ingredient_id):
            raise IngredientNotFoundError("Ingredient was not found")
        draft = make_draft(
            ingredient_id=ingredient_id,
            quantity=quantity,
            unit=unit,
            food_state=food_state,
            expiry_date=expiry_date,
        )
        return await self._repository.create(user_id=user_id, draft=draft)

    async def get_item(self, *, user_id: UUID, fridge_item_id: UUID) -> FridgeItem:
        item = await self._repository.get(
            user_id=user_id,
            fridge_item_id=fridge_item_id,
        )
        if item is None:
            raise FridgeItemNotFoundError("Fridge item was not found")
        return item

    async def update_item(
        self,
        *,
        user_id: UUID,
        fridge_item_id: UUID,
        changes: Mapping[str, Any],
    ) -> FridgeItem:
        item = await self.get_item(user_id=user_id, fridge_item_id=fridge_item_id)
        ingredient_id = changes.get("ingredient_id", item.ingredient.ingredient_id)
        if ingredient_id != item.ingredient.ingredient_id and not await self._repository.ingredient_exists(
            ingredient_id
        ):
            raise IngredientNotFoundError("Ingredient was not found")

        draft = make_draft(
            ingredient_id=ingredient_id,
            quantity=changes.get("quantity", item.quantity),
            unit=changes.get("unit", item.unit),
            food_state=changes.get("food_state", item.food_state),
            expiry_date=changes.get("expiry_date", item.expiry_date),
        )
        saved = await self._repository.save(
            user_id=user_id,
            fridge_item_id=fridge_item_id,
            draft=draft,
        )
        if saved is None:
            raise FridgeItemNotFoundError("Fridge item was not found")
        return saved

    async def delete_item(self, *, user_id: UUID, fridge_item_id: UUID) -> None:
        deleted = await self._repository.delete(
            user_id=user_id,
            fridge_item_id=fridge_item_id,
        )
        if not deleted:
            raise FridgeItemNotFoundError("Fridge item was not found")

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
        today: date | None = None,
    ) -> FridgeItemPage:
        normalized_q = normalize_optional_text(q)
        normalized_category = normalize_optional_text(category)
        return await self._repository.list_items(
            user_id=user_id,
            q=normalized_q,
            category=normalized_category,
            expiry_status=expiry_status,
            food_state=food_state,
            sort=sort,
            page=page,
            size=size,
            today=today or date.today(),
            warning_days=self._warning_days,
        )

    async def get_summary(
        self,
        *,
        user_id: UUID,
        today: date | None = None,
    ) -> FridgeSummary:
        return await self._repository.summarize(
            user_id=user_id,
            today=today or date.today(),
            warning_days=self._warning_days,
        )

    async def get_available_ingredients(
        self,
        *,
        user_id: UUID,
        today: date | None = None,
    ) -> tuple[FridgeItem, ...]:
        return await self._repository.list_available(
            user_id=user_id,
            today=today or date.today(),
        )


def make_draft(
    *,
    ingredient_id: UUID,
    quantity: Decimal,
    unit: str,
    food_state: FoodState | None,
    expiry_date: date,
) -> FridgeItemDraft:
    if not quantity.is_finite() or quantity <= 0:
        raise InvalidFridgeItemError("quantity must be greater than zero")
    normalized_unit = " ".join(unit.split())
    if not normalized_unit:
        raise InvalidFridgeItemError("unit must not be blank")
    if len(normalized_unit) > 32:
        raise InvalidFridgeItemError("unit must contain at most 32 characters")
    return FridgeItemDraft(
        ingredient_id=ingredient_id,
        quantity=quantity,
        unit=normalized_unit,
        food_state=food_state,
        expiry_date=expiry_date,
    )


def normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split())
    return normalized or None
