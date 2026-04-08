from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import Settings, get_settings
from .database import Database
from .models import BotDetail, BotSummary, CycleResult, DashboardSnapshot, LandingSnapshot, OperationSnapshot, PredictionView, SignalView, Summary, AssetSnapshot
from .services import BotSocietyService

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"



def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or get_settings()
    database = Database(active_settings.database_path)
    service = BotSocietyService(database, active_settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        service.bootstrap()
        app.state.bot_society_service = service
        yield

    app = FastAPI(
        title=active_settings.project_name,
        version=active_settings.version,
        description="Professional MVP foundation for Bot Society Markets.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    def get_service(request: Request) -> BotSocietyService:
        return request.app.state.bot_society_service

    @app.get("/health")
    def healthcheck() -> dict[str, str]:
        return {"status": "ok", "service": "bot-society-markets"}

    @app.get("/api/landing", response_model=LandingSnapshot)
    def landing_snapshot(request: Request) -> LandingSnapshot:
        return get_service(request).get_landing_snapshot()

    @app.get("/api/dashboard", response_model=DashboardSnapshot)
    def dashboard_snapshot(request: Request) -> DashboardSnapshot:
        return get_service(request).get_dashboard_snapshot()

    @app.get("/api/summary", response_model=Summary)
    def summary(request: Request) -> Summary:
        return get_service(request).get_summary()

    @app.get("/api/assets", response_model=list[AssetSnapshot])
    def assets(request: Request) -> list[AssetSnapshot]:
        return get_service(request).get_assets()

    @app.get("/api/bots", response_model=list[BotSummary])
    def bots(request: Request) -> list[BotSummary]:
        return get_service(request).get_leaderboard()

    @app.get("/api/bots/{slug}", response_model=BotDetail)
    def bot_detail(slug: str, request: Request) -> BotDetail:
        bot = get_service(request).get_bot_detail(slug)
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        return bot

    @app.get("/api/leaderboard", response_model=list[BotSummary])
    def leaderboard(request: Request) -> list[BotSummary]:
        return get_service(request).get_leaderboard()

    @app.get("/api/predictions", response_model=list[PredictionView])
    def predictions(
        request: Request,
        limit: int = Query(default=20, ge=1, le=100),
        status: str | None = Query(default=None, pattern="^(pending|scored)?$"),
    ) -> list[PredictionView]:
        return get_service(request).get_predictions(limit=limit, status=status)

    @app.get("/api/signals", response_model=list[SignalView])
    def signals(request: Request, limit: int = Query(default=12, ge=1, le=100)) -> list[SignalView]:
        return get_service(request).get_signals(limit=limit)

    @app.get("/api/operations/latest", response_model=OperationSnapshot | None)
    def latest_operation(request: Request) -> OperationSnapshot | None:
        return get_service(request).get_latest_operation()

    @app.post("/api/admin/run-cycle", response_model=CycleResult)
    def run_cycle(request: Request) -> CycleResult:
        return get_service(request).run_pipeline_cycle()

    @app.get("/")
    def landing() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/dashboard")
    def dashboard() -> FileResponse:
        return FileResponse(STATIC_DIR / "dashboard.html")

    return app


app = create_app()
