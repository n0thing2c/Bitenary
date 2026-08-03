from datetime import date
from typing import Protocol
from uuid import UUID

from virtual_fridge.domain.entities import (
    ExpiryStatus,
    FoodState,
    FridgeItem,
    FridgeItemDraft,
    FridgeItemPage,
    FridgeItemSort,
    FridgeSummary,
)


class FridgeItemRepository(Protocol):
    async def ingredient_exists(self, ingredient_id: UUID) -> bool:
        raise NotImplementedError

    async def create(self, *, user_id: UUID, draft: FridgeItemDraft) -> FridgeItem:
        raise NotImplementedError

    async def get(self, *, user_id: UUID, fridge_item_id: UUID) -> FridgeItem | None:
        raise NotImplementedError

    async def save(
        self,
        *,
        user_id: UUID,
        fridge_item_id: UUID,
        draft: FridgeItemDraft,
    ) -> FridgeItem | None:
        raise NotImplementedError

    async def delete(self, *, user_id: UUID, fridge_item_id: UUID) -> bool:
        raise NotImplementedError

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
        raise NotImplementedError

    async def summarize(
        self,
        *,
        user_id: UUID,
        today: date,
        warning_days: int,
    ) -> FridgeSummary:
        raise NotImplementedError

    async def list_available(
        self,
        *,
        user_id: UUID,
        today: date,
    ) -> tuple[FridgeItem, ...]:
        raise NotImplementedError
