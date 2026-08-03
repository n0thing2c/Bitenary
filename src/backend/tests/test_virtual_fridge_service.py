from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

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
    expiry_status_for,
)
from virtual_fridge.domain.errors import (
    FridgeItemNotFoundError,
    IngredientNotFoundError,
    InvalidFridgeItemError,
)
from virtual_fridge.service.fridge import VirtualFridgeService


def make_item(
    *,
    user_id: UUID | None = None,
    ingredient_id: UUID | None = None,
    expiry_date: date | None = None,
) -> FridgeItem:
    now = datetime.now(UTC)
    return FridgeItem(
        fridge_item_id=uuid4(),
        user_id=user_id or uuid4(),
        ingredient=IngredientSummary(
            ingredient_id=ingredient_id or uuid4(),
            name="Spinach",
            variant="raw",
            category="Vegetables",
        ),
        quantity=Decimal("250.000"),
        unit="g",
        food_state=FoodState.RAW,
        expiry_date=expiry_date or date.today() + timedelta(days=2),
        created_at=now,
        updated_at=now,
    )


class FakeFridgeRepository:
    def __init__(self) -> None:
        self.ingredients: set[UUID] = set()
        self.items: dict[tuple[UUID, UUID], FridgeItem] = {}
        self.last_draft: FridgeItemDraft | None = None
        self.last_list_args: dict[str, object] | None = None

    async def ingredient_exists(self, ingredient_id: UUID) -> bool:
        return ingredient_id in self.ingredients

    async def create(self, *, user_id: UUID, draft: FridgeItemDraft) -> FridgeItem:
        self.last_draft = draft
        item = make_item(
            user_id=user_id,
            ingredient_id=draft.ingredient_id,
            expiry_date=draft.expiry_date,
        )
        item = FridgeItem(
            **{
                **item.__dict__,
                "quantity": draft.quantity,
                "unit": draft.unit,
                "food_state": draft.food_state,
            }
        )
        self.items[(user_id, item.fridge_item_id)] = item
        return item

    async def get(self, *, user_id: UUID, fridge_item_id: UUID) -> FridgeItem | None:
        return self.items.get((user_id, fridge_item_id))

    async def save(
        self,
        *,
        user_id: UUID,
        fridge_item_id: UUID,
        draft: FridgeItemDraft,
    ) -> FridgeItem | None:
        existing = self.items.get((user_id, fridge_item_id))
        if existing is None:
            return None
        self.last_draft = draft
        updated = FridgeItem(
            fridge_item_id=existing.fridge_item_id,
            user_id=user_id,
            ingredient=IngredientSummary(
                ingredient_id=draft.ingredient_id,
                name=existing.ingredient.name,
                variant=existing.ingredient.variant,
                category=existing.ingredient.category,
            ),
            quantity=draft.quantity,
            unit=draft.unit,
            food_state=draft.food_state,
            expiry_date=draft.expiry_date,
            created_at=existing.created_at,
            updated_at=datetime.now(UTC),
        )
        self.items[(user_id, fridge_item_id)] = updated
        return updated

    async def delete(self, *, user_id: UUID, fridge_item_id: UUID) -> bool:
        return self.items.pop((user_id, fridge_item_id), None) is not None

    async def list_items(self, **kwargs: object) -> FridgeItemPage:
        self.last_list_args = kwargs
        return FridgeItemPage(items=tuple(), page=int(kwargs["page"]), size=int(kwargs["size"]), total=0)

    async def summarize(self, **_kwargs: object) -> FridgeSummary:
        return FridgeSummary(
            total_items=0,
            fresh=0,
            expiring_soon=0,
            expiring_today=0,
            expired=0,
            categories=(CategoryCount(category="Vegetables", count=0),),
        )

    async def list_available(self, **_kwargs: object) -> tuple[FridgeItem, ...]:
        return tuple()


def test_expiry_status_boundaries() -> None:
    today = date(2026, 8, 2)
    assert expiry_status_for(today - timedelta(days=1), today=today) == ExpiryStatus.EXPIRED
    assert expiry_status_for(today, today=today) == ExpiryStatus.EXPIRING_TODAY
    assert expiry_status_for(today + timedelta(days=3), today=today) == ExpiryStatus.EXPIRING_SOON
    assert expiry_status_for(today + timedelta(days=4), today=today) == ExpiryStatus.FRESH


@pytest.mark.asyncio
async def test_create_rejects_unknown_ingredient() -> None:
    repository = FakeFridgeRepository()
    service = VirtualFridgeService(repository)

    with pytest.raises(IngredientNotFoundError):
        await service.create_item(
            user_id=uuid4(),
            ingredient_id=uuid4(),
            quantity=Decimal("1"),
            unit="kg",
            food_state=None,
            expiry_date=date.today(),
        )


@pytest.mark.asyncio
async def test_create_normalizes_unit_and_keeps_decimal() -> None:
    repository = FakeFridgeRepository()
    ingredient_id = uuid4()
    repository.ingredients.add(ingredient_id)
    service = VirtualFridgeService(repository)

    await service.create_item(
        user_id=uuid4(),
        ingredient_id=ingredient_id,
        quantity=Decimal("1.250"),
        unit="  fluid   oz ",
        food_state=FoodState.PREPPED,
        expiry_date=date.today(),
    )

    assert repository.last_draft is not None
    assert repository.last_draft.unit == "fluid oz"
    assert repository.last_draft.quantity == Decimal("1.250")


@pytest.mark.asyncio
async def test_create_rejects_non_positive_quantity() -> None:
    repository = FakeFridgeRepository()
    ingredient_id = uuid4()
    repository.ingredients.add(ingredient_id)
    service = VirtualFridgeService(repository)

    with pytest.raises(InvalidFridgeItemError):
        await service.create_item(
            user_id=uuid4(),
            ingredient_id=ingredient_id,
            quantity=Decimal("0"),
            unit="g",
            food_state=None,
            expiry_date=date.today(),
        )


@pytest.mark.asyncio
async def test_owner_isolation_returns_not_found() -> None:
    repository = FakeFridgeRepository()
    owner = uuid4()
    stranger = uuid4()
    item = make_item(user_id=owner)
    repository.items[(owner, item.fridge_item_id)] = item
    service = VirtualFridgeService(repository)

    with pytest.raises(FridgeItemNotFoundError):
        await service.get_item(user_id=stranger, fridge_item_id=item.fridge_item_id)


@pytest.mark.asyncio
async def test_update_only_changes_provided_fields() -> None:
    repository = FakeFridgeRepository()
    user_id = uuid4()
    item = make_item(user_id=user_id)
    repository.items[(user_id, item.fridge_item_id)] = item
    service = VirtualFridgeService(repository)

    updated = await service.update_item(
        user_id=user_id,
        fridge_item_id=item.fridge_item_id,
        changes={"quantity": Decimal("125")},
    )

    assert updated.quantity == Decimal("125")
    assert updated.unit == item.unit
    assert updated.expiry_date == item.expiry_date


@pytest.mark.asyncio
async def test_list_normalizes_blank_query_and_category() -> None:
    repository = FakeFridgeRepository()
    service = VirtualFridgeService(repository)

    await service.list_items(
        user_id=uuid4(),
        q="   ",
        category="  Vegetables   and Fruit ",
        expiry_status=None,
        food_state=None,
        sort=FridgeItemSort.NAME_ASC,
        page=1,
        size=20,
        today=date(2026, 8, 2),
    )

    assert repository.last_list_args is not None
    assert repository.last_list_args["q"] is None
    assert repository.last_list_args["category"] == "Vegetables and Fruit"
