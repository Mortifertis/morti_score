from contextlib import asynccontextmanager
import logging

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.deps import (
    get_match_service,
    get_prediction_service,
    get_standings_service,
    get_team_service,
)
from app.api.router import router as api_router
from app.bot.telegram_bot import launch_bot
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.redis import close_redis
from app.db.session import AsyncSessionLocal
from app.models import MatchStatus
from app.schemas.prediction import PredictionRequest
from app.services.match import MatchService
from app.services.prediction import PredictionService
from app.services.seed import SeedService
from app.services.standings import StandingsService
from app.services.team import TeamService

settings = get_settings()
configure_logging(settings)
logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory="app/templates")


@asynccontextmanager
async def lifespan(_: FastAPI):
    bot_task = None
    async with AsyncSessionLocal() as session:
        if settings.seed_on_startup:
            try:
                result = await SeedService(session).seed_all()
                logger.info("Startup seed result: %s", result)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Failed to seed startup data: %s", exc)
                raise
    if settings.enable_telegram_bot and settings.telegram_bot_token:
        bot_task = launch_bot(AsyncSessionLocal)
    yield
    if bot_task is not None:
        bot_task.cancel()
    await close_redis()


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)
app.include_router(api_router)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


async def _build_dashboard_context(
    team_service: TeamService,
    match_service: MatchService,
    standings_service: StandingsService,
    *,
    prediction=None,
    prediction_error: str | None = None,
    selected_home_team_id: int | None = None,
    selected_away_team_id: int | None = None,
) -> dict[str, object]:
    teams = await team_service.list_teams()
    recent_matches = await match_service.list_matches(
        status=MatchStatus.FINISHED,
        sort_order="desc",
        limit=5,
    )
    upcoming_matches = await match_service.list_matches(
        status=MatchStatus.SCHEDULED,
        sort_order="asc",
        limit=5,
    )
    standings = await standings_service.list_standings()
    return {
        "teams": teams,
        "recent_matches": recent_matches,
        "upcoming_matches": upcoming_matches,
        "standings": standings,
        "prediction": prediction,
        "prediction_error": prediction_error,
        "selected_home_team_id": selected_home_team_id,
        "selected_away_team_id": selected_away_team_id,
    }


@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    team_service: TeamService = Depends(get_team_service),
    match_service: MatchService = Depends(get_match_service),
    standings_service: StandingsService = Depends(get_standings_service),
) -> HTMLResponse:
    context = await _build_dashboard_context(
        team_service,
        match_service,
        standings_service,
    )
    return templates.TemplateResponse(request, "dashboard.html", context)


@app.post("/dashboard", response_class=HTMLResponse)
async def dashboard_prediction(
    request: Request,
    home_team_id: int = Form(...),
    away_team_id: int = Form(...),
    team_service: TeamService = Depends(get_team_service),
    match_service: MatchService = Depends(get_match_service),
    standings_service: StandingsService = Depends(get_standings_service),
    prediction_service: PredictionService = Depends(get_prediction_service),
) -> HTMLResponse:
    prediction = None
    prediction_error = None
    try:
        payload = PredictionRequest(
            home_team_id=home_team_id,
            away_team_id=away_team_id,
        )
        prediction = await prediction_service.predict_match(
            payload.home_team_id,
            payload.away_team_id,
        )
    except HTTPException as exc:
        if isinstance(exc.detail, dict):
            prediction_error = str(exc.detail.get("message", ""))
        else:
            prediction_error = str(exc.detail)

    context = await _build_dashboard_context(
        team_service,
        match_service,
        standings_service,
        prediction=prediction,
        prediction_error=prediction_error,
        selected_home_team_id=home_team_id,
        selected_away_team_id=away_team_id,
    )
    return templates.TemplateResponse(request, "dashboard.html", context)
