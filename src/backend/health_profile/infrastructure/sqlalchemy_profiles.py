from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    delete,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base
from health_profile.domain.entities import (
    HealthPreference,
    HealthPreferenceType,
    HealthProfile,
    HealthProfileActivityLevel,
    HealthProfileDraft,
    HealthProfileGender,
    HealthProfileOnboardingState,
    HealthProfilePrimaryGoal,
    HealthProfileState,
)
from health_profile.domain.errors import HealthProfileOwnerNotFoundError
from health_profile.repository.profiles import HealthProfileRepository
from identity.infrastructure.sqlalchemy_users import UserModel


class HealthProfileModel(Base):
    __tablename__ = "health_profiles"
    __table_args__ = (
        CheckConstraint("weight_kg > 0", name="health_profiles_weight_positive"),
        CheckConstraint("height_cm > 0", name="health_profiles_height_positive"),
        CheckConstraint(
            "target_weight_kg IS NULL OR target_weight_kg > 0",
            name="health_profiles_target_weight_positive",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    gender: Mapped[HealthProfileGender] = mapped_column(
        Enum(HealthProfileGender, name="health_profile_gender"),
        nullable=False,
    )
    weight_kg: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    height_cm: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    activity_level: Mapped[HealthProfileActivityLevel] = mapped_column(
        Enum(HealthProfileActivityLevel, name="health_profile_activity_level"),
        nullable=False,
    )
    primary_goal: Mapped[HealthProfilePrimaryGoal] = mapped_column(
        Enum(HealthProfilePrimaryGoal, name="health_profile_primary_goal"),
        nullable=False,
    )
    target_weight_kg: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 2),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class HealthProfilePreferenceModel(Base):
    __tablename__ = "health_profile_preferences"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "preference_type",
            "normalized_value",
            name="uq_health_profile_preferences_owner_type_value",
        ),
    )

    preference_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    preference_type: Mapped[HealthPreferenceType] = mapped_column(
        Enum(HealthPreferenceType, name="health_profile_preference_type"),
        nullable=False,
    )
    value: Mapped[str] = mapped_column(String(100), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


def to_domain(
    profile: HealthProfileModel,
    preferences: list[HealthProfilePreferenceModel],
) -> HealthProfile:
    return HealthProfile(
        user_id=profile.user_id,
        date_of_birth=profile.date_of_birth,
        gender=profile.gender,
        weight_kg=profile.weight_kg,
        height_cm=profile.height_cm,
        activity_level=profile.activity_level,
        primary_goal=profile.primary_goal,
        target_weight_kg=profile.target_weight_kg,
        preferences=tuple(
            HealthPreference(
                preference_id=preference.preference_id,
                preference_type=preference.preference_type,
                value=preference.value,
                normalized_value=preference.normalized_value,
                created_at=preference.created_at,
            )
            for preference in preferences
        ),
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


class SqlAlchemyHealthProfileRepository(HealthProfileRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_state(self, user_id: UUID) -> HealthProfileState:
        user = await self._session.get(UserModel, user_id)
        if user is None:
            raise HealthProfileOwnerNotFoundError("Health-profile owner was not found")

        profile = await self._session.get(HealthProfileModel, user_id)
        if profile is None:
            onboarding_state = (
                HealthProfileOnboardingState.SKIPPED
                if user.profile_onboarding_dismissed_at is not None
                else HealthProfileOnboardingState.NOT_STARTED
            )
            return HealthProfileState(
                onboarding_state=onboarding_state,
                profile=None,
            )

        preferences = await self._load_preferences(user_id)
        return HealthProfileState(
            onboarding_state=HealthProfileOnboardingState.COMPLETED,
            profile=to_domain(profile, preferences),
        )

    async def save(
        self,
        *,
        user_id: UUID,
        draft: HealthProfileDraft,
    ) -> HealthProfile:
        user = await self._session.get(UserModel, user_id)
        if user is None:
            raise HealthProfileOwnerNotFoundError("Health-profile owner was not found")

        profile = await self._session.get(HealthProfileModel, user_id)
        if profile is None:
            profile = HealthProfileModel(user_id=user_id)
            self._session.add(profile)
        else:
            profile.updated_at = datetime.now(UTC)

        profile.date_of_birth = draft.date_of_birth
        profile.gender = draft.gender
        profile.weight_kg = draft.weight_kg
        profile.height_cm = draft.height_cm
        profile.activity_level = draft.activity_level
        profile.primary_goal = draft.primary_goal
        profile.target_weight_kg = draft.target_weight_kg
        user.profile_onboarding_dismissed_at = None

        await self._session.execute(
            delete(HealthProfilePreferenceModel).where(
                HealthProfilePreferenceModel.user_id == user_id
            )
        )
        self._session.add_all(
            [
                HealthProfilePreferenceModel(
                    user_id=user_id,
                    preference_type=preference.preference_type,
                    value=preference.value,
                    normalized_value=preference.normalized_value,
                )
                for preference in draft.preferences
            ]
        )
        await self._session.commit()
        await self._session.refresh(profile)
        preferences = await self._load_preferences(user_id)
        return to_domain(profile, preferences)

    async def mark_onboarding_skipped(
        self,
        *,
        user_id: UUID,
        skipped_at: datetime,
    ) -> HealthProfileState:
        user = await self._session.get(UserModel, user_id)
        if user is None:
            raise HealthProfileOwnerNotFoundError("Health-profile owner was not found")

        profile = await self._session.get(HealthProfileModel, user_id)
        if profile is None:
            user.profile_onboarding_dismissed_at = skipped_at
            await self._session.commit()
            return HealthProfileState(
                onboarding_state=HealthProfileOnboardingState.SKIPPED,
                profile=None,
            )

        preferences = await self._load_preferences(user_id)
        return HealthProfileState(
            onboarding_state=HealthProfileOnboardingState.COMPLETED,
            profile=to_domain(profile, preferences),
        )

    async def _load_preferences(
        self,
        user_id: UUID,
    ) -> list[HealthProfilePreferenceModel]:
        result = await self._session.execute(
            select(HealthProfilePreferenceModel)
            .where(HealthProfilePreferenceModel.user_id == user_id)
            .order_by(
                HealthProfilePreferenceModel.created_at,
                HealthProfilePreferenceModel.preference_id,
            )
        )
        return list(result.scalars().all())
