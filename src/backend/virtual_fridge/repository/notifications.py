from datetime import date
from typing import Protocol
from uuid import UUID

from virtual_fridge.domain.entities import (
    ExpiryNotificationSettings,
    ExpiryScanCandidate,
    Notification,
    NotificationDraft,
    NotificationPage,
    NotificationType,
)


class NotificationRepository(Protocol):
    async def get_settings(self, user_id: UUID) -> ExpiryNotificationSettings | None:
        raise NotImplementedError

    async def save_settings(
        self,
        settings: ExpiryNotificationSettings,
    ) -> ExpiryNotificationSettings:
        raise NotImplementedError

    async def list_notifications(
        self,
        *,
        user_id: UUID,
        unread_only: bool,
        notification_type: NotificationType | None,
        page: int,
        size: int,
    ) -> NotificationPage:
        raise NotImplementedError

    async def mark_read(
        self,
        *,
        user_id: UUID,
        notification_id: UUID,
    ) -> Notification | None:
        raise NotImplementedError

    async def mark_all_read(self, *, user_id: UUID) -> int:
        raise NotImplementedError

    async def list_scan_candidates(
        self,
        *,
        cutoff_date: date,
    ) -> tuple[ExpiryScanCandidate, ...]:
        raise NotImplementedError

    async def create_if_absent(self, draft: NotificationDraft) -> bool:
        raise NotImplementedError
