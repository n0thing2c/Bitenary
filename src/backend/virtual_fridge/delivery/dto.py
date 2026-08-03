from datetime import date, datetime
from decimal import Decimal
from math import ceil
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from virtual_fridge.domain.entities import (
    ExpiryNotificationSettings,
    ExpiryStatus,
    FoodState,
    FridgeItem,
    FridgeItemPage,
    FridgeSummary,
    Notification,
    NotificationPage,
    NotificationStatus,
    NotificationType,
    expiry_status_for,
)


class CreateFridgeItemRequest(BaseModel):
    ingredient_id: UUID
    quantity: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    unit: str = Field(min_length=1, max_length=32)
    food_state: FoodState | None = None
    expiry_date: date

    @field_validator("unit")
    @classmethod
    def normalize_unit(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("unit must not be blank")
        return normalized


class UpdateFridgeItemRequest(BaseModel):
    ingredient_id: UUID | None = None
    quantity: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=12,
        decimal_places=3,
    )
    unit: str | None = Field(default=None, min_length=1, max_length=32)
    food_state: FoodState | None = None
    expiry_date: date | None = None

    @field_validator("unit")
    @classmethod
    def normalize_unit(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("unit must not be blank")
        return normalized

    @model_validator(mode="after")
    def reject_empty_or_null_required_fields(self) -> "UpdateFridgeItemRequest":
        if not self.model_fields_set:
            raise ValueError("at least one field must be provided")
        for field_name in ("ingredient_id", "quantity", "unit", "expiry_date"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} must not be null")
        return self


class IngredientSummaryResponse(BaseModel):
    ingredient_id: UUID
    name: str
    variant: str
    category: str


class FridgeItemResponse(BaseModel):
    fridge_item_id: UUID
    ingredient: IngredientSummaryResponse
    quantity: float
    unit: str
    food_state: FoodState | None
    expiry_date: date
    expiry_status: ExpiryStatus
    days_until_expiry: int
    created_at: datetime
    updated_at: datetime


class FridgeItemListResponse(BaseModel):
    items: list[FridgeItemResponse]
    page: int
    size: int
    total: int
    total_pages: int


class CategoryCountResponse(BaseModel):
    category: str
    count: int


class FridgeSummaryResponse(BaseModel):
    total_items: int
    fresh: int
    expiring_soon: int
    expiring_today: int
    expired: int
    categories: list[CategoryCountResponse]


class ExpiryNotificationSettingsRequest(BaseModel):
    enabled: bool = True
    warning_days: int = Field(default=3, ge=1, le=30)
    timezone: str = Field(default="Asia/Ho_Chi_Minh", min_length=1, max_length=64)
    delivery_hour: int = Field(default=9, ge=0, le=23)


class ExpiryNotificationSettingsResponse(BaseModel):
    enabled: bool
    warning_days: int
    timezone: str
    delivery_hour: int
    updated_at: datetime | None


class NotificationResponse(BaseModel):
    notification_id: UUID
    fridge_item_id: UUID
    notification_type: NotificationType
    status: NotificationStatus
    title: str
    message: str
    trigger_date: date
    scheduled_for: datetime
    sent_at: datetime | None
    read_at: datetime | None
    created_at: datetime


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    page: int
    size: int
    total: int
    total_pages: int


class MarkAllReadResponse(BaseModel):
    updated: int


def item_response(
    item: FridgeItem,
    *,
    today: date,
    warning_days: int,
) -> FridgeItemResponse:
    return FridgeItemResponse(
        fridge_item_id=item.fridge_item_id,
        ingredient=IngredientSummaryResponse(
            ingredient_id=item.ingredient.ingredient_id,
            name=item.ingredient.name,
            variant=item.ingredient.variant,
            category=item.ingredient.category,
        ),
        quantity=float(item.quantity),
        unit=item.unit,
        food_state=item.food_state,
        expiry_date=item.expiry_date,
        expiry_status=expiry_status_for(
            item.expiry_date,
            today=today,
            warning_days=warning_days,
        ),
        days_until_expiry=(item.expiry_date - today).days,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def item_list_response(
    result: FridgeItemPage,
    *,
    today: date,
    warning_days: int,
) -> FridgeItemListResponse:
    return FridgeItemListResponse(
        items=[
            item_response(item, today=today, warning_days=warning_days)
            for item in result.items
        ],
        page=result.page,
        size=result.size,
        total=result.total,
        total_pages=ceil(result.total / result.size) if result.total else 0,
    )


def summary_response(summary: FridgeSummary) -> FridgeSummaryResponse:
    return FridgeSummaryResponse(
        total_items=summary.total_items,
        fresh=summary.fresh,
        expiring_soon=summary.expiring_soon,
        expiring_today=summary.expiring_today,
        expired=summary.expired,
        categories=[
            CategoryCountResponse(category=item.category, count=item.count)
            for item in summary.categories
        ],
    )


def settings_response(
    settings: ExpiryNotificationSettings,
) -> ExpiryNotificationSettingsResponse:
    return ExpiryNotificationSettingsResponse(
        enabled=settings.enabled,
        warning_days=settings.warning_days,
        timezone=settings.timezone,
        delivery_hour=settings.delivery_hour,
        updated_at=settings.updated_at,
    )


def notification_response(notification: Notification) -> NotificationResponse:
    return NotificationResponse(
        notification_id=notification.notification_id,
        fridge_item_id=notification.fridge_item_id,
        notification_type=notification.notification_type,
        status=notification.status,
        title=notification.title,
        message=notification.message,
        trigger_date=notification.trigger_date,
        scheduled_for=notification.scheduled_for,
        sent_at=notification.sent_at,
        read_at=notification.read_at,
        created_at=notification.created_at,
    )


def notification_list_response(result: NotificationPage) -> NotificationListResponse:
    return NotificationListResponse(
        items=[notification_response(item) for item in result.items],
        page=result.page,
        size=result.size,
        total=result.total,
        total_pages=ceil(result.total / result.size) if result.total else 0,
    )
