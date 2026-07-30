from fastapi import APIRouter, Depends

from bitenary_mcp.delivery.routes import router as mcp_connections_router
from core.config import Settings, get_settings
from health_profile.delivery.routes import router as health_profile_router
from identity.delivery.routes import router as auth_router


router = APIRouter(prefix="/api")
router.include_router(auth_router)
router.include_router(mcp_connections_router)
router.include_router(health_profile_router)


@router.get("/health", tags=["health"])
def health(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.service_name,
        "environment": settings.environment,
    }
