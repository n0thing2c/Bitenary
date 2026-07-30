from fastapi import APIRouter, Depends, HTTPException, Request, status

from core.csrf import verify_csrf_token
from health_profile.delivery.dto import (
    HealthProfileEnvelopeResponse,
    UpsertHealthProfileRequest,
    envelope_response,
)
from health_profile.domain.errors import (
    HealthProfileOwnerNotFoundError,
    InvalidHealthProfileError,
)
from health_profile.service.profiles import HealthProfileService
from health_profile.wiring import get_health_profile_service
from identity.domain.entities import CurrentUser
from identity.wiring import get_current_user


router = APIRouter(prefix="/health-profile", tags=["health-profile"])


@router.get("", response_model=HealthProfileEnvelopeResponse)
async def get_health_profile(
    current_user: CurrentUser = Depends(get_current_user),
    service: HealthProfileService = Depends(get_health_profile_service),
) -> HealthProfileEnvelopeResponse:
    try:
        state = await service.get_state(current_user.user_id)
    except HealthProfileOwnerNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User was not found",
        ) from exc
    return envelope_response(state, current_user=current_user)


@router.put("", response_model=HealthProfileEnvelopeResponse)
async def upsert_health_profile(
    payload: UpsertHealthProfileRequest,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    service: HealthProfileService = Depends(get_health_profile_service),
) -> HealthProfileEnvelopeResponse:
    verify_csrf_token(request)
    try:
        await service.save(
            user_id=current_user.user_id,
            date_of_birth=payload.date_of_birth,
            gender=payload.gender,
            weight_kg=payload.weight_kg,
            height_cm=payload.height_cm,
            activity_level=payload.activity_level,
            primary_goal=payload.primary_goal,
            target_weight_kg=payload.target_weight_kg,
            preferences=[
                (preference.preference_type, preference.value)
                for preference in payload.preferences
            ],
        )
        state = await service.get_state(current_user.user_id)
    except InvalidHealthProfileError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except HealthProfileOwnerNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User was not found",
        ) from exc
    return envelope_response(state, current_user=current_user)


@router.post("/onboarding/skip", status_code=status.HTTP_204_NO_CONTENT)
async def skip_health_profile_onboarding(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    service: HealthProfileService = Depends(get_health_profile_service),
) -> None:
    verify_csrf_token(request)
    try:
        await service.skip_onboarding(current_user.user_id)
    except HealthProfileOwnerNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User was not found",
        ) from exc
