from datetime import UTC, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from virtual_fridge.domain.entities import (
    ExpiryNotificationSettings,
    ExpiryScanResult,
    Notification,
    NotificationDraft,
    NotificationPage,
    NotificationStatus,
    NotificationType,
)
from virtual_fridge.domain.errors import (
    InvalidNotificationSettingsError,
    NotificationNotFoundError,
)
from virtual_fridge.repository.notifications import NotificationRepository


class ExpiryNotificationService:
    def __init__(
        self,
        repository: NotificationRepository,
        *,
        default_warning_days: int = 3,
        default_timezone: str = "Asia/Ho_Chi_Minh",
        default_delivery_hour: int = 9,
    ) -> None:
        self._repository = repository
        self._default_warning_days = default_warning_days
        self._default_timezone = default_timezone
        self._default_delivery_hour = default_delivery_hour

    async def get_settings(self, user_id: UUID) -> ExpiryNotificationSettings:
        settings = await self._repository.get_settings(user_id)
        if settings is not None:
            return settings
        return self._default_settings(user_id)

    async def save_settings(
        self,
        *,
        user_id: UUID,
        enabled: bool,
        warning_days: int,
        timezone: str,
        delivery_hour: int,
    ) -> ExpiryNotificationSettings:
        validate_settings(
            warning_days=warning_days,
            timezone=timezone,
            delivery_hour=delivery_hour,
        )
        settings = ExpiryNotificationSettings(
            user_id=user_id,
            enabled=enabled,
            warning_days=warning_days,
            timezone=timezone,
            delivery_hour=delivery_hour,
        )
        return await self._repository.save_settings(settings)

    async def list_notifications(
        self,
        *,
        user_id: UUID,
        unread_only: bool,
        notification_type: NotificationType | None,
        page: int,
        size: int,
    ) -> NotificationPage:
        return await self._repository.list_notifications(
            user_id=user_id,
            unread_only=unread_only,
            notification_type=notification_type,
            page=page,
            size=size,
        )

    async def mark_read(
        self,
        *,
        user_id: UUID,
        notification_id: UUID,
    ) -> Notification:
        notification = await self._repository.mark_read(
            user_id=user_id,
            notification_id=notification_id,
        )
        if notification is None:
            raise NotificationNotFoundError("Notification was not found")
        return notification

    async def mark_all_read(self, *, user_id: UUID) -> int:
        return await self._repository.mark_all_read(user_id=user_id)

    async def scan(self, *, now: datetime | None = None) -> ExpiryScanResult:
        scan_time = now or datetime.now(UTC)
        if scan_time.tzinfo is None:
            raise InvalidNotificationSettingsError("scan time must include a timezone")

        candidates = await self._repository.list_scan_candidates(
            cutoff_date=scan_time.date() + timedelta(days=30),
        )
        created = 0
        skipped = 0

        for candidate in candidates:
            settings = candidate.settings or self._default_settings(candidate.item.user_id)
            if not settings.enabled:
                skipped += 1
                continue

            local_now = scan_time.astimezone(ZoneInfo(settings.timezone))
            if local_now.hour < settings.delivery_hour:
                skipped += 1
                continue

            local_date = local_now.date()
            days_until_expiry = (candidate.item.expiry_date - local_date).days
            if days_until_expiry > settings.warning_days:
                skipped += 1
                continue

            if days_until_expiry < 0:
                notification_type = NotificationType.EXPIRED
                trigger_date = candidate.item.expiry_date + timedelta(days=1)
                title = "Food item expired"
                message = f"{candidate.item.ingredient.name} expired on {candidate.item.expiry_date.isoformat()}."
            else:
                notification_type = NotificationType.EXPIRING_SOON
                trigger_date = candidate.item.expiry_date - timedelta(
                    days=settings.warning_days
                )
                title = "Food item expiring soon"
                if days_until_expiry == 0:
                    message = f"{candidate.item.ingredient.name} expires today."
                else:
                    message = (
                        f"{candidate.item.ingredient.name} expires in "
                        f"{days_until_expiry} day(s)."
                    )

            inserted = await self._repository.create_if_absent(
                NotificationDraft(
                    user_id=candidate.item.user_id,
                    fridge_item_id=candidate.item.fridge_item_id,
                    notification_type=notification_type,
                    status=NotificationStatus.SENT,
                    title=title,
                    message=message,
                    trigger_date=trigger_date,
                    scheduled_for=scan_time,
                    sent_at=scan_time,
                )
            )
            if inserted:
                created += 1
            else:
                skipped += 1

        return ExpiryScanResult(
            scanned=len(candidates),
            created=created,
            skipped=skipped,
        )

    def _default_settings(self, user_id: UUID) -> ExpiryNotificationSettings:
        return ExpiryNotificationSettings(
            user_id=user_id,
            enabled=True,
            warning_days=self._default_warning_days,
            timezone=self._default_timezone,
            delivery_hour=self._default_delivery_hour,
        )


def validate_settings(*, warning_days: int, timezone: str, delivery_hour: int) -> None:
    if not 1 <= warning_days <= 30:
        raise InvalidNotificationSettingsError("warning_days must be between 1 and 30")
    if not 0 <= delivery_hour <= 23:
        raise InvalidNotificationSettingsError("delivery_hour must be between 0 and 23")
    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise InvalidNotificationSettingsError("timezone must be a valid IANA timezone") from exc
