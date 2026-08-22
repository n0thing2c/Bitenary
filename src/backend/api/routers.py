from fastapi import APIRouter, Depends

from api.chat import router as chat_router
from bitenary_mcp.delivery.routes import router as mcp_connections_router
from core.config import Settings, get_settings
from health_profile.delivery.routes import router as health_profile_router
from identity.delivery.routes import router as auth_router
from ingredients.delivery.routes import router as ingredients_router
from meal_plan.delivery.routes import router as meal_plan_router
from virtual_fridge.delivery.routes import notifications_router, router as virtual_fridge_router


router = APIRouter(prefix="/api")
router.include_router(auth_router)
router.include_router(mcp_connections_router)
router.include_router(health_profile_router)
router.include_router(chat_router)
router.include_router(ingredients_router)
router.include_router(virtual_fridge_router)
router.include_router(notifications_router)
router.include_router(meal_plan_router)



@router.get("/health", tags=["health"])
def health(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.service_name,
        "environment": settings.environment,
    }
