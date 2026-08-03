from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID


DEFAULT_EXPIRY_WARNING_DAYS = 3


class FoodState(StrEnum):
    RAW = "RAW"
    COOKED = "COOKED"
    FROZEN = "FROZEN"
    PREPPED = "PREPPED"


class ExpiryStatus(StrEnum):
    FRESH = "FRESH"
    EXPIRING_SOON = "EXPIRING_SOON"
    EXPIRING_TODAY = "EXPIRING_TODAY"
    EXPIRED = "EXPIRED"


class FridgeItemSort(StrEnum):
    EXPIRY_ASC = "expiry_asc"
    EXPIRY_DESC = "expiry_desc"
    NAME_ASC = "name_asc"
    UPDATED_DESC = "updated_desc"


class NotificationType(StrEnum):
    EXPIRING_SOON = "EXPIRING_SOON"
    EXPIRED = "EXPIRED"


class NotificationStatus(StrEnum):
    PENDING = "PENDING"
    SENT = "SENT"
    READ = "READ"
    FAILED = "FAILED"


@dataclass(frozen=True)
class IngredientSummary:
    ingredient_id: UUID
    name: str
    variant: str
    category: str


@dataclass(frozen=True)
class FridgeItemDraft:
    ingredient_id: UUID
    quantity: Decimal
    unit: str
    food_state: FoodState | None
    expiry_date: date


@dataclass(frozen=True)
class FridgeItem:
    fridge_item_id: UUID
    user_id: UUID
    ingredient: IngredientSummary
    quantity: Decimal
    unit: str
    food_state: FoodState | None
    expiry_date: date
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class FridgeItemPage:
    items: tuple[FridgeItem, ...]
    page: int
    size: int
    total: int


@dataclass(frozen=True)
class CategoryCount:
    category: str
    count: int


@dataclass(frozen=True)
class FridgeSummary:
    total_items: int
    fresh: int
    expiring_soon: int
    expiring_today: int
    expired: int
    categories: tuple[CategoryCount, ...]


@dataclass(frozen=True)
class ExpiryNotificationSettings:
    user_id: UUID
    enabled: bool
    warning_days: int
    timezone: str
    delivery_hour: int
    updated_at: datetime | None = None


@dataclass(frozen=True)
class Notification:
    notification_id: UUID
    user_id: UUID
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


@dataclass(frozen=True)
class NotificationDraft:
    user_id: UUID
    fridge_item_id: UUID
    notification_type: NotificationType
    status: NotificationStatus
    title: str
    message: str
    trigger_date: date
    scheduled_for: datetime
    sent_at: datetime | None


@dataclass(frozen=True)
class NotificationPage:
    items: tuple[Notification, ...]
    page: int
    size: int
    total: int


@dataclass(frozen=True)
class ExpiryScanCandidate:
    item: FridgeItem
    settings: ExpiryNotificationSettings | None


@dataclass(frozen=True)
class ExpiryScanResult:
    scanned: int
    created: int
    skipped: int


def expiry_status_for(
    expiry_date: date,
    *,
    today: date,
    warning_days: int = DEFAULT_EXPIRY_WARNING_DAYS,
) -> ExpiryStatus:
    days = (expiry_date - today).days
    if days < 0:
        return ExpiryStatus.EXPIRED
    if days == 0:
        return ExpiryStatus.EXPIRING_TODAY
    if days <= warning_days:
        return ExpiryStatus.EXPIRING_SOON
    return ExpiryStatus.FRESH
