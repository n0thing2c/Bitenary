from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID


class HealthProfileGender(StrEnum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    OTHER = "OTHER"
    PREFER_NOT_TO_SAY = "PREFER_NOT_TO_SAY"


class HealthProfileActivityLevel(StrEnum):
    SEDENTARY = "SEDENTARY"
    LIGHT = "LIGHT"
    MODERATE = "MODERATE"
    ACTIVE = "ACTIVE"
    VERY_ACTIVE = "VERY_ACTIVE"


class HealthProfilePrimaryGoal(StrEnum):
    MAINTAIN = "MAINTAIN"
    WEIGHT_LOSS = "WEIGHT_LOSS"
    WEIGHT_GAIN = "WEIGHT_GAIN"
    MUSCLE_GAIN = "MUSCLE_GAIN"


class HealthPreferenceType(StrEnum):
    ALLERGY = "ALLERGY"
    DIETARY_RESTRICTION = "DIETARY_RESTRICTION"
    TASTE = "TASTE"
    DISLIKE = "DISLIKE"


class HealthProfileOnboardingState(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    SKIPPED = "SKIPPED"
    COMPLETED = "COMPLETED"


@dataclass(frozen=True)
class HealthPreference:
    preference_id: UUID
    preference_type: HealthPreferenceType
    value: str
    normalized_value: str
    created_at: datetime


@dataclass(frozen=True)
class HealthPreferenceDraft:
    preference_type: HealthPreferenceType
    value: str
    normalized_value: str


@dataclass(frozen=True)
class HealthProfileDraft:
    date_of_birth: date
    gender: HealthProfileGender
    weight_kg: Decimal
    height_cm: Decimal
    activity_level: HealthProfileActivityLevel
    primary_goal: HealthProfilePrimaryGoal
    target_weight_kg: Decimal | None
    preferences: tuple[HealthPreferenceDraft, ...]


@dataclass(frozen=True)
class HealthProfile:
    user_id: UUID
    date_of_birth: date
    gender: HealthProfileGender
    weight_kg: Decimal
    height_cm: Decimal
    activity_level: HealthProfileActivityLevel
    primary_goal: HealthProfilePrimaryGoal
    target_weight_kg: Decimal | None
    preferences: tuple[HealthPreference, ...]
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class HealthProfileState:
    onboarding_state: HealthProfileOnboardingState
    profile: HealthProfile | None
