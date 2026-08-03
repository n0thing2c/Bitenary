from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import Settings, get_settings
from core.database import get_db_session
from virtual_fridge.infrastructure.sqlalchemy_fridge import (
    SqlAlchemyFridgeItemRepository,
)
from virtual_fridge.infrastructure.sqlalchemy_notifications import (
    SqlAlchemyNotificationRepository,
)
from virtual_fridge.repository.fridge_items import FridgeItemRepository
from virtual_fridge.repository.notifications import NotificationRepository
from virtual_fridge.service.expiry_notifications import ExpiryNotificationService
from virtual_fridge.service.fridge import VirtualFridgeService


def get_fridge_item_repository(
    session: AsyncSession = Depends(get_db_session),
) -> FridgeItemRepository:
    return SqlAlchemyFridgeItemRepository(session)


def get_virtual_fridge_service(
    repository: FridgeItemRepository = Depends(get_fridge_item_repository),
    settings: Settings = Depends(get_settings),
) -> VirtualFridgeService:
    return VirtualFridgeService(
        repository,
        warning_days=settings.fridge_expiry_warning_days,
    )


def get_notification_repository(
    session: AsyncSession = Depends(get_db_session),
) -> NotificationRepository:
    return SqlAlchemyNotificationRepository(session)


def get_expiry_notification_service(
    repository: NotificationRepository = Depends(get_notification_repository),
    settings: Settings = Depends(get_settings),
) -> ExpiryNotificationService:
    return ExpiryNotificationService(
        repository,
        default_warning_days=settings.fridge_expiry_warning_days,
        default_timezone=settings.fridge_default_timezone,
        default_delivery_hour=settings.fridge_default_delivery_hour,
    )
