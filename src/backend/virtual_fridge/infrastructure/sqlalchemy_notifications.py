from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base
from identity.infrastructure.sqlalchemy_users import UserModel
from ingredients.infrastructure.sqlalchemy_ingredients import IngredientMasterModel
from virtual_fridge.domain.entities import (
    ExpiryNotificationSettings,
    ExpiryScanCandidate,
    Notification,
    NotificationDraft,
    NotificationPage,
    NotificationStatus,
    NotificationType,
)
from virtual_fridge.infrastructure.sqlalchemy_fridge import FridgeItemModel, to_domain
from virtual_fridge.repository.notifications import NotificationRepository


class ExpiryNotificationSettingsModel(Base):
    __tablename__ = "expiry_notification_settings"
    __table_args__ = (
        CheckConstraint(
            "warning_days BETWEEN 1 AND 30",
            name="expiry_notification_settings_warning_days_range",
        ),
        CheckConstraint(
            "delivery_hour BETWEEN 0 AND 23",
            name="expiry_notification_settings_delivery_hour_range",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey(UserModel.user_id, ondelete="CASCADE"),
        primary_key=True,
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    warning_days: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=3,
        server_default="3",
    )
    timezone: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="Asia/Ho_Chi_Minh",
        server_default="Asia/Ho_Chi_Minh",
    )
    delivery_hour: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=9,
        server_default="9",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class NotificationModel(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint(
            "fridge_item_id",
            "notification_type",
            "trigger_date",
            name="uq_notifications_fridge_type_trigger",
        ),
        Index("ix_notifications_user_created", "user_id", "created_at"),
        Index("ix_notifications_user_status", "user_id", "status"),
    )

    notification_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey(UserModel.user_id, ondelete="CASCADE"),
        nullable=False,
    )
    fridge_item_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey(FridgeItemModel.fridge_item_id, ondelete="CASCADE"),
        nullable=False,
    )
    notification_type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, name="expiry_notification_type"),
        nullable=False,
    )
    status: Mapped[NotificationStatus] = mapped_column(
        Enum(NotificationStatus, name="notification_status"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    trigger_date: Mapped[date] = mapped_column(Date, nullable=False)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


def settings_to_domain(
    model: ExpiryNotificationSettingsModel,
) -> ExpiryNotificationSettings:
    return ExpiryNotificationSettings(
        user_id=model.user_id,
        enabled=model.enabled,
        warning_days=model.warning_days,
        timezone=model.timezone,
        delivery_hour=model.delivery_hour,
        updated_at=model.updated_at,
    )


def notification_to_domain(model: NotificationModel) -> Notification:
    return Notification(
        notification_id=model.notification_id,
        user_id=model.user_id,
        fridge_item_id=model.fridge_item_id,
        notification_type=model.notification_type,
        status=model.status,
        title=model.title,
        message=model.message,
        trigger_date=model.trigger_date,
        scheduled_for=model.scheduled_for,
        sent_at=model.sent_at,
        read_at=model.read_at,
        created_at=model.created_at,
    )


class SqlAlchemyNotificationRepository(NotificationRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_settings(self, user_id: UUID) -> ExpiryNotificationSettings | None:
        model = await self._session.get(ExpiryNotificationSettingsModel, user_id)
        return settings_to_domain(model) if model is not None else None

    async def save_settings(
        self,
        settings: ExpiryNotificationSettings,
    ) -> ExpiryNotificationSettings:
        model = await self._session.get(
            ExpiryNotificationSettingsModel,
            settings.user_id,
        )
        if model is None:
            model = ExpiryNotificationSettingsModel(user_id=settings.user_id)
            self._session.add(model)
        model.enabled = settings.enabled
        model.warning_days = settings.warning_days
        model.timezone = settings.timezone
        model.delivery_hour = settings.delivery_hour
        model.updated_at = datetime.now(UTC)
        await self._session.commit()
        await self._session.refresh(model)
        return settings_to_domain(model)

    async def list_notifications(
        self,
        *,
        user_id: UUID,
        unread_only: bool,
        notification_type: NotificationType | None,
        page: int,
        size: int,
    ) -> NotificationPage:
        conditions = [NotificationModel.user_id == user_id]
        if unread_only:
            conditions.append(NotificationModel.status != NotificationStatus.READ)
        if notification_type is not None:
            conditions.append(NotificationModel.notification_type == notification_type)

        total = (
            await self._session.execute(
                select(func.count()).select_from(NotificationModel).where(*conditions)
            )
        ).scalar_one()
        rows = (
            await self._session.execute(
                select(NotificationModel)
                .where(*conditions)
                .order_by(NotificationModel.created_at.desc())
                .offset((page - 1) * size)
                .limit(size)
            )
        ).scalars().all()
        return NotificationPage(
            items=tuple(notification_to_domain(row) for row in rows),
            page=page,
            size=size,
            total=total,
        )

    async def mark_read(
        self,
        *,
        user_id: UUID,
        notification_id: UUID,
    ) -> Notification | None:
        model = (
            await self._session.execute(
                select(NotificationModel).where(
                    NotificationModel.notification_id == notification_id,
                    NotificationModel.user_id == user_id,
                )
            )
        ).scalar_one_or_none()
        if model is None:
            return None
        if model.status != NotificationStatus.READ:
            model.status = NotificationStatus.READ
            model.read_at = datetime.now(UTC)
            await self._session.commit()
            await self._session.refresh(model)
        return notification_to_domain(model)

    async def mark_all_read(self, *, user_id: UUID) -> int:
        result = await self._session.execute(
            update(NotificationModel)
            .where(
                NotificationModel.user_id == user_id,
                NotificationModel.status != NotificationStatus.READ,
            )
            .values(status=NotificationStatus.READ, read_at=datetime.now(UTC))
        )
        await self._session.commit()
        return int(result.rowcount or 0)

    async def list_scan_candidates(
        self,
        *,
        cutoff_date: date,
    ) -> tuple[ExpiryScanCandidate, ...]:
        rows = (
            await self._session.execute(
                select(
                    FridgeItemModel,
                    IngredientMasterModel,
                    ExpiryNotificationSettingsModel,
                )
                .join(
                    IngredientMasterModel,
                    IngredientMasterModel.ingredient_id
                    == FridgeItemModel.ingredient_id,
                )
                .outerjoin(
                    ExpiryNotificationSettingsModel,
                    ExpiryNotificationSettingsModel.user_id == FridgeItemModel.user_id,
                )
                .where(FridgeItemModel.expiry_date <= cutoff_date)
                .order_by(FridgeItemModel.user_id, FridgeItemModel.expiry_date)
            )
        ).all()
        return tuple(
            ExpiryScanCandidate(
                item=to_domain(item, ingredient),
                settings=(
                    settings_to_domain(settings) if settings is not None else None
                ),
            )
            for item, ingredient, settings in rows
        )

    async def create_if_absent(self, draft: NotificationDraft) -> bool:
        notification_id = uuid4()
        stmt = (
            pg_insert(NotificationModel)
            .values(
                notification_id=notification_id,
                user_id=draft.user_id,
                fridge_item_id=draft.fridge_item_id,
                notification_type=draft.notification_type,
                status=draft.status,
                title=draft.title,
                message=draft.message,
                trigger_date=draft.trigger_date,
                scheduled_for=draft.scheduled_for,
                sent_at=draft.sent_at,
            )
            .on_conflict_do_nothing(
                constraint="uq_notifications_fridge_type_trigger"
            )
            .returning(NotificationModel.notification_id)
        )
        inserted_id = (await self._session.execute(stmt)).scalar_one_or_none()
        await self._session.commit()
        return inserted_id is not None
