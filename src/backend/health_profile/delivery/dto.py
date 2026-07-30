from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from health_profile.domain.entities import (
    HealthPreference,
    HealthPreferenceType,
    HealthProfile,
    HealthProfileActivityLevel,
    HealthProfileGender,
    HealthProfileOnboardingState,
    HealthProfilePrimaryGoal,
    HealthProfileState,
)
from identity.domain.entities import CurrentUser, UserStatus


class HealthPreferenceRequest(BaseModel):
    preference_type: HealthPreferenceType
    value: str = Field(min_length=1, max_length=100)

    @field_validator("value")
    @classmethod
    def normalize_value(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized


class UpsertHealthProfileRequest(BaseModel):
    date_of_birth: date
    gender: HealthProfileGender
    weight_kg: Decimal = Field(gt=0, max_digits=6, decimal_places=2)
    height_cm: Decimal = Field(gt=0, max_digits=6, decimal_places=2)
    activity_level: HealthProfileActivityLevel
    primary_goal: HealthProfilePrimaryGoal
    target_weight_kg: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=6,
        decimal_places=2,
    )
    preferences: list[HealthPreferenceRequest] = Field(
        default_factory=list,
        max_length=100,
    )

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, value: date) -> date:
        if value >= date.today():
            raise ValueError("date_of_birth must be in the past")
        return value


class AccountSummaryResponse(BaseModel):
    user_id: UUID
    username: str
    email: str | None
    status: UserStatus


class HealthPreferenceResponse(BaseModel):
    preference_type: HealthPreferenceType
    value: str


class HealthProfileResponse(BaseModel):
    date_of_birth: date
    gender: HealthProfileGender
    weight_kg: float
    height_cm: float
    activity_level: HealthProfileActivityLevel
    primary_goal: HealthProfilePrimaryGoal
    target_weight_kg: float | None
    preferences: list[HealthPreferenceResponse]
    created_at: datetime
    updated_at: datetime


class HealthProfileEnvelopeResponse(BaseModel):
    onboarding_state: HealthProfileOnboardingState
    account: AccountSummaryResponse
    health_profile: HealthProfileResponse | None


def envelope_response(
    state: HealthProfileState,
    *,
    current_user: CurrentUser,
) -> HealthProfileEnvelopeResponse:
    return HealthProfileEnvelopeResponse(
        onboarding_state=state.onboarding_state,
        account=AccountSummaryResponse(
            user_id=current_user.user_id,
            username=current_user.username,
            email=current_user.email,
            status=current_user.status,
        ),
        health_profile=(
            profile_response(state.profile) if state.profile is not None else None
        ),
    )


def profile_response(profile: HealthProfile) -> HealthProfileResponse:
    return HealthProfileResponse(
        date_of_birth=profile.date_of_birth,
        gender=profile.gender,
        weight_kg=float(profile.weight_kg),
        height_cm=float(profile.height_cm),
        activity_level=profile.activity_level,
        primary_goal=profile.primary_goal,
        target_weight_kg=(
            float(profile.target_weight_kg)
            if profile.target_weight_kg is not None
            else None
        ),
        preferences=[
            preference_response(preference) for preference in profile.preferences
        ],
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


def preference_response(preference: HealthPreference) -> HealthPreferenceResponse:
    return HealthPreferenceResponse(
        preference_type=preference.preference_type,
        value=preference.value,
    )
