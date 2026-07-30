from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db_session
from health_profile.infrastructure.sqlalchemy_profiles import (
    SqlAlchemyHealthProfileRepository,
)
from health_profile.repository.profiles import HealthProfileRepository
from health_profile.service.profiles import HealthProfileService


def get_health_profile_repository(
    session: AsyncSession = Depends(get_db_session),
) -> HealthProfileRepository:
    return SqlAlchemyHealthProfileRepository(session)


def get_health_profile_service(
    repository: HealthProfileRepository = Depends(get_health_profile_repository),
) -> HealthProfileService:
    return HealthProfileService(repository)
