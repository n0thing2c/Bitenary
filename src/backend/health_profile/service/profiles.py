from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from health_profile.domain.entities import (
    HealthPreferenceDraft,
    HealthPreferenceType,
    HealthProfile,
    HealthProfileActivityLevel,
    HealthProfileDraft,
    HealthProfileGender,
    HealthProfilePrimaryGoal,
    HealthProfileState,
)
from health_profile.domain.errors import InvalidHealthProfileError
from health_profile.repository.profiles import HealthProfileRepository


class HealthProfileService:
    def __init__(self, repository: HealthProfileRepository) -> None:
        self._repository = repository

    async def get_state(self, user_id: UUID) -> HealthProfileState:
        return await self._repository.get_state(user_id)

    async def save(
        self,
        *,
        user_id: UUID,
        date_of_birth: date,
        gender: HealthProfileGender,
        weight_kg: Decimal,
        height_cm: Decimal,
        activity_level: HealthProfileActivityLevel,
        primary_goal: HealthProfilePrimaryGoal,
        target_weight_kg: Decimal | None,
        preferences: Sequence[tuple[HealthPreferenceType, str]],
    ) -> HealthProfile:
        validate_profile_values(
            date_of_birth=date_of_birth,
            weight_kg=weight_kg,
            height_cm=height_cm,
            target_weight_kg=target_weight_kg,
        )
        draft = HealthProfileDraft(
            date_of_birth=date_of_birth,
            gender=gender,
            weight_kg=weight_kg,
            height_cm=height_cm,
            activity_level=activity_level,
            primary_goal=primary_goal,
            target_weight_kg=target_weight_kg,
            preferences=normalize_preferences(preferences),
        )
        return await self._repository.save(user_id=user_id, draft=draft)

    async def skip_onboarding(self, user_id: UUID) -> HealthProfileState:
        return await self._repository.mark_onboarding_skipped(
            user_id=user_id,
            skipped_at=datetime.now(UTC),
        )


def validate_profile_values(
    *,
    date_of_birth: date,
    weight_kg: Decimal,
    height_cm: Decimal,
    target_weight_kg: Decimal | None,
) -> None:
    if date_of_birth >= date.today():
        raise InvalidHealthProfileError("Date of birth must be in the past")
    validate_positive_decimal("weight_kg", weight_kg)
    validate_positive_decimal("height_cm", height_cm)
    if target_weight_kg is not None:
        validate_positive_decimal("target_weight_kg", target_weight_kg)


def validate_positive_decimal(name: str, value: Decimal) -> None:
    if not value.is_finite() or value <= 0:
        raise InvalidHealthProfileError(f"{name} must be greater than zero")


def normalize_preferences(
    preferences: Sequence[tuple[HealthPreferenceType, str]],
) -> tuple[HealthPreferenceDraft, ...]:
    normalized_preferences: list[HealthPreferenceDraft] = []
    seen: set[tuple[HealthPreferenceType, str]] = set()
    for preference_type, raw_value in preferences:
        value = " ".join(raw_value.split())
        if not value:
            raise InvalidHealthProfileError("Preference value must not be blank")
        if len(value) > 100:
            raise InvalidHealthProfileError(
                "Preference value must contain at most 100 characters"
            )
        normalized_value = value.casefold()
        key = preference_type, normalized_value
        if key in seen:
            continue
        seen.add(key)
        normalized_preferences.append(
            HealthPreferenceDraft(
                preference_type=preference_type,
                value=value,
                normalized_value=normalized_value,
            )
        )
    return tuple(normalized_preferences)
