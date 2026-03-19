from fastapi import APIRouter

from app.api.v1.endpoints.admin import router as admin_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.matches import router as matches_router
from app.api.v1.endpoints.predictions import router as predictions_router
from app.api.v1.endpoints.standings import router as standings_router
from app.api.v1.endpoints.teams import router as teams_router
from app.core.config import get_settings

settings = get_settings()
router = APIRouter()
router.include_router(health_router)
api_router = APIRouter(prefix=settings.api_v1_prefix)
api_router.include_router(teams_router)
api_router.include_router(matches_router)
api_router.include_router(standings_router)
api_router.include_router(predictions_router)
api_router.include_router(admin_router)
router.include_router(api_router)
