from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

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
from health_profile.domain.errors import InvalidHealthProfileError
from health_profile.service.profiles import HealthProfileService


class FakeHealthProfileRepository:
    def __init__(self) -> None:
        self.state = HealthProfileState(
            onboarding_state=HealthProfileOnboardingState.NOT_STARTED,
            profile=None,
        )
        self.saved_draft: HealthProfileDraft | None = None
        self.skipped_at: datetime | None = None

    async def get_state(self, _user_id: UUID) -> HealthProfileState:
        return self.state

    async def save(
        self,
        *,
        user_id: UUID,
        draft: HealthProfileDraft,
    ) -> HealthProfile:
        self.saved_draft = draft
        now = datetime.now(UTC)
        profile = HealthProfile(
            user_id=user_id,
            date_of_birth=draft.date_of_birth,
            gender=draft.gender,
            weight_kg=draft.weight_kg,
            height_cm=draft.height_cm,
            activity_level=draft.activity_level,
            primary_goal=draft.primary_goal,
            target_weight_kg=draft.target_weight_kg,
            preferences=tuple(
                HealthPreference(
                    preference_id=uuid4(),
                    preference_type=preference.preference_type,
                    value=preference.value,
                    normalized_value=preference.normalized_value,
                    created_at=now,
                )
                for preference in draft.preferences
            ),
            created_at=now,
            updated_at=now,
        )
        self.state = HealthProfileState(
            onboarding_state=HealthProfileOnboardingState.COMPLETED,
            profile=profile,
        )
        return profile

    async def mark_onboarding_skipped(
        self,
        *,
        user_id: UUID,
        skipped_at: datetime,
    ) -> HealthProfileState:
        self.skipped_at = skipped_at
        self.state = HealthProfileState(
            onboarding_state=HealthProfileOnboardingState.SKIPPED,
            profile=None,
        )
        return self.state


@pytest.mark.anyio
async def test_save_normalizes_and_deduplicates_preferences() -> None:
    repository = FakeHealthProfileRepository()
    service = HealthProfileService(repository)
    user_id = uuid4()

    profile = await service.save(
        user_id=user_id,
        date_of_birth=date(1995, 4, 12),
        gender=HealthProfileGender.FEMALE,
        weight_kg=Decimal("62.50"),
        height_cm=Decimal("168.00"),
        activity_level=HealthProfileActivityLevel.MODERATE,
        primary_goal=HealthProfilePrimaryGoal.MAINTAIN,
        target_weight_kg=None,
        preferences=[
            (HealthPreferenceType.ALLERGY, "  Tree   Nuts "),
            (HealthPreferenceType.ALLERGY, "tree nuts"),
            (HealthPreferenceType.TASTE, "Spicy"),
        ],
    )

    assert profile.user_id == user_id
    assert repository.saved_draft is not None
    assert [
        (preference.preference_type, preference.value, preference.normalized_value)
        for preference in repository.saved_draft.preferences
    ] == [
        (HealthPreferenceType.ALLERGY, "Tree Nuts", "tree nuts"),
        (HealthPreferenceType.TASTE, "Spicy", "spicy"),
    ]


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("date_of_birth", "weight_kg", "height_cm", "target_weight_kg"),
    [
        (date.today(), Decimal("70"), Decimal("175"), None),
        (date(1990, 1, 1), Decimal("0"), Decimal("175"), None),
        (date(1990, 1, 1), Decimal("70"), Decimal("-1"), None),
        (date(1990, 1, 1), Decimal("70"), Decimal("175"), Decimal("0")),
    ],
)
async def test_save_rejects_invalid_profile_values(
    date_of_birth: date,
    weight_kg: Decimal,
    height_cm: Decimal,
    target_weight_kg: Decimal | None,
) -> None:
    service = HealthProfileService(FakeHealthProfileRepository())

    with pytest.raises(InvalidHealthProfileError):
        await service.save(
            user_id=uuid4(),
            date_of_birth=date_of_birth,
            gender=HealthProfileGender.OTHER,
            weight_kg=weight_kg,
            height_cm=height_cm,
            activity_level=HealthProfileActivityLevel.LIGHT,
            primary_goal=HealthProfilePrimaryGoal.WEIGHT_LOSS,
            target_weight_kg=target_weight_kg,
            preferences=[],
        )


@pytest.mark.anyio
async def test_skip_onboarding_persists_skipped_state() -> None:
    repository = FakeHealthProfileRepository()
    service = HealthProfileService(repository)

    state = await service.skip_onboarding(uuid4())

    assert state.onboarding_state == HealthProfileOnboardingState.SKIPPED
    assert state.profile is None
    assert repository.skipped_at is not None
