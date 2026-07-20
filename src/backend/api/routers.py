from fastapi import APIRouter, Depends

from core.config import Settings, get_settings


router = APIRouter(prefix="/api")


@router.get("/health", tags=["health"])
def health(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.service_name,
        "environment": settings.environment,
    }
