from datetime import datetime
from typing import Protocol
from uuid import UUID

from health_profile.domain.entities import (
    HealthProfile,
    HealthProfileDraft,
    HealthProfileState,
)


class HealthProfileRepository(Protocol):
    async def get_state(self, user_id: UUID) -> HealthProfileState:
        raise NotImplementedError

    async def save(self, *, user_id: UUID, draft: HealthProfileDraft) -> HealthProfile:
        raise NotImplementedError

    async def mark_onboarding_skipped(
        self,
        *,
        user_id: UUID,
        skipped_at: datetime,
    ) -> HealthProfileState:
        raise NotImplementedError
