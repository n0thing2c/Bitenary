from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from virtual_fridge.domain.entities import (
    ExpiryNotificationSettings,
    ExpiryScanCandidate,
    FoodState,
    FridgeItem,
    IngredientSummary,
    Notification,
    NotificationDraft,
    NotificationPage,
    NotificationStatus,
    NotificationType,
)
from virtual_fridge.domain.errors import InvalidNotificationSettingsError
from virtual_fridge.service.expiry_notifications import ExpiryNotificationService


def candidate(
    *,
    expiry_date: date,
    settings: ExpiryNotificationSettings | None = None,
) -> ExpiryScanCandidate:
    user_id = settings.user_id if settings is not None else uuid4()
    now = datetime.now(UTC)
    item = FridgeItem(
        fridge_item_id=uuid4(),
        user_id=user_id,
        ingredient=IngredientSummary(
            ingredient_id=uuid4(),
            name="Milk",
            variant="whole",
            category="Dairy",
        ),
        quantity=Decimal("1"),
        unit="l",
        food_state=FoodState.RAW,
        expiry_date=expiry_date,
        created_at=now,
        updated_at=now,
    )
    return ExpiryScanCandidate(item=item, settings=settings)


class FakeNotificationRepository:
    def __init__(self) -> None:
        self.settings: dict[UUID, ExpiryNotificationSettings] = {}
        self.candidates: tuple[ExpiryScanCandidate, ...] = tuple()
        self.drafts: list[NotificationDraft] = []
        self._dedupe: set[tuple[UUID, NotificationType, date]] = set()

    async def get_settings(self, user_id: UUID) -> ExpiryNotificationSettings | None:
        return self.settings.get(user_id)

    async def save_settings(
        self, settings: ExpiryNotificationSettings
    ) -> ExpiryNotificationSettings:
        self.settings[settings.user_id] = settings
        return settings

    async def list_notifications(self, **kwargs: object) -> NotificationPage:
        return NotificationPage(items=tuple(), page=int(kwargs["page"]), size=int(kwargs["size"]), total=0)

    async def mark_read(self, **_kwargs: object) -> Notification | None:
        return None

    async def mark_all_read(self, **_kwargs: object) -> int:
        return 0

    async def list_scan_candidates(self, **_kwargs: object) -> tuple[ExpiryScanCandidate, ...]:
        return self.candidates

    async def create_if_absent(self, draft: NotificationDraft) -> bool:
        key = (draft.fridge_item_id, draft.notification_type, draft.trigger_date)
        if key in self._dedupe:
            return False
        self._dedupe.add(key)
        self.drafts.append(draft)
        return True


@pytest.mark.asyncio
async def test_default_settings_are_returned_without_database_row() -> None:
    repository = FakeNotificationRepository()
    service = ExpiryNotificationService(repository)
    user_id = uuid4()

    settings = await service.get_settings(user_id)

    assert settings.enabled is True
    assert settings.warning_days == 3
    assert settings.timezone == "Asia/Ho_Chi_Minh"


@pytest.mark.asyncio
async def test_invalid_timezone_is_rejected() -> None:
    repository = FakeNotificationRepository()
    service = ExpiryNotificationService(repository)

    with pytest.raises(InvalidNotificationSettingsError):
        await service.save_settings(
            user_id=uuid4(),
            enabled=True,
            warning_days=3,
            timezone="Not/A_Timezone",
            delivery_hour=9,
        )


@pytest.mark.asyncio
async def test_scan_is_idempotent_for_same_item_and_trigger() -> None:
    repository = FakeNotificationRepository()
    service = ExpiryNotificationService(
        repository,
        default_timezone="UTC",
        default_delivery_hour=0,
    )
    now = datetime(2026, 8, 2, 9, tzinfo=UTC)
    repository.candidates = (candidate(expiry_date=now.date() + timedelta(days=2)),)

    first = await service.scan(now=now)
    second = await service.scan(now=now)

    assert first.created == 1
    assert second.created == 0
    assert second.skipped == 1
    assert repository.drafts[0].notification_type == NotificationType.EXPIRING_SOON
    assert repository.drafts[0].status == NotificationStatus.SENT


@pytest.mark.asyncio
async def test_disabled_user_is_skipped() -> None:
    repository = FakeNotificationRepository()
    now = datetime(2026, 8, 2, 9, tzinfo=UTC)
    settings = ExpiryNotificationSettings(
        user_id=uuid4(),
        enabled=False,
        warning_days=3,
        timezone="UTC",
        delivery_hour=0,
    )
    repository.candidates = (candidate(expiry_date=now.date(), settings=settings),)
    service = ExpiryNotificationService(repository)

    result = await service.scan(now=now)

    assert result.created == 0
    assert result.skipped == 1


@pytest.mark.asyncio
async def test_expired_item_creates_expired_notification() -> None:
    repository = FakeNotificationRepository()
    now = datetime(2026, 8, 2, 9, tzinfo=UTC)
    repository.candidates = (candidate(expiry_date=now.date() - timedelta(days=1)),)
    service = ExpiryNotificationService(
        repository,
        default_timezone="UTC",
        default_delivery_hour=0,
    )

    result = await service.scan(now=now)

    assert result.created == 1
    assert repository.drafts[0].notification_type == NotificationType.EXPIRED
