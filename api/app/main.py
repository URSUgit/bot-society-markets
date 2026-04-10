from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .config import Settings, get_settings
from .database import Database
from .models import (
    AdvancedBacktestExport,
    AlertInbox,
    AlertRuleCreate,
    AssetHistoryEnvelope,
    AssetSnapshot,
    AuthLoginRequest,
    AuthRegisterRequest,
    AuthSessionSnapshot,
    BotDetail,
    BotSummary,
    CycleResult,
    DashboardSnapshot,
    EdgeSnapshot,
    FollowBotRequest,
    LandingSnapshot,
    MacroSnapshot,
    NotificationChannel,
    NotificationChannelCreate,
    NotificationHealthSnapshot,
    NotificationRetryResult,
    OperationSnapshot,
    PaperSimulationResult,
    PaperTradingSnapshot,
    PredictionView,
    ProviderStatusEnvelope,
    SignalView,
    SimulationConfig,
    SimulationExportArtifact,
    SimulationRequest,
    SimulationRunResult,
    Summary,
    SystemPulseEnvelope,
    UserProfile,
    WalletIntelligenceSnapshot,
    WatchlistAssetRequest,
)
from .services import BotSocietyService

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or get_settings()
    database = Database(path=active_settings.database_path, url=active_settings.database_url)
    service = BotSocietyService(database, active_settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        service.bootstrap()
        app.state.bot_society_service = service
        try:
            yield
        finally:
            database.dispose()

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

    def current_user_slug(request: Request, *, fallback_to_demo: bool = True) -> str | None:
        return get_service(request).resolve_user_slug(
            request.cookies.get(active_settings.auth_cookie_name),
            fallback_to_demo=fallback_to_demo,
        )

    def authenticated_user_slug(request: Request) -> str:
        user_slug = current_user_slug(request, fallback_to_demo=False)
        if not user_slug:
            raise HTTPException(status_code=401, detail="Sign in to modify a personal workspace")
        return user_slug

    def set_session_cookie(response: Response, token: str) -> None:
        response.set_cookie(
            key=active_settings.auth_cookie_name,
            value=token,
            httponly=True,
            samesite="lax",
            max_age=active_settings.session_ttl_hours * 3600,
        )

    def clear_session_cookie(response: Response) -> None:
        response.delete_cookie(active_settings.auth_cookie_name)

    def run_validated(action):
        try:
            return action()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/health")
    def healthcheck() -> dict[str, str]:
        return {"status": "ok", "service": "bot-society-markets"}

    @app.get("/api/auth/session", response_model=AuthSessionSnapshot)
    def auth_session(request: Request) -> AuthSessionSnapshot:
        return get_service(request).get_session_snapshot(request.cookies.get(active_settings.auth_cookie_name))

    @app.post("/api/auth/register", response_model=AuthSessionSnapshot)
    def auth_register(payload: AuthRegisterRequest, request: Request, response: Response) -> AuthSessionSnapshot:
        session, token = run_validated(lambda: get_service(request).register_user(payload))
        set_session_cookie(response, token)
        return session

    @app.post("/api/auth/login", response_model=AuthSessionSnapshot)
    def auth_login(payload: AuthLoginRequest, request: Request, response: Response) -> AuthSessionSnapshot:
        session, token = run_validated(lambda: get_service(request).login_user(payload))
        set_session_cookie(response, token)
        return session

    @app.post("/api/auth/logout", response_model=AuthSessionSnapshot)
    def auth_logout(request: Request, response: Response) -> AuthSessionSnapshot:
        get_service(request).logout_session(request.cookies.get(active_settings.auth_cookie_name))
        clear_session_cookie(response)
        return AuthSessionSnapshot(authenticated=False, user=None)

    @app.get("/api/landing", response_model=LandingSnapshot)
    def landing_snapshot(request: Request) -> LandingSnapshot:
        return get_service(request).get_landing_snapshot(current_user_slug(request))

    @app.get("/api/dashboard", response_model=DashboardSnapshot)
    def dashboard_snapshot(request: Request) -> DashboardSnapshot:
        return get_service(request).get_dashboard_snapshot(current_user_slug(request) or active_settings.default_user_slug)

    @app.get("/api/summary", response_model=Summary)
    def summary(request: Request) -> Summary:
        return get_service(request).get_summary(current_user_slug(request))

    @app.get("/api/assets", response_model=list[AssetSnapshot])
    def assets(request: Request) -> list[AssetSnapshot]:
        return get_service(request).get_assets()

    @app.get("/api/assets/{asset}/history", response_model=AssetHistoryEnvelope)
    def asset_history(asset: str, request: Request) -> AssetHistoryEnvelope:
        return run_validated(lambda: get_service(request).get_asset_history(asset))

    @app.get("/api/macro", response_model=MacroSnapshot)
    def macro_snapshot(request: Request) -> MacroSnapshot:
        return get_service(request).get_macro_snapshot()

    @app.get("/api/wallet-intelligence", response_model=WalletIntelligenceSnapshot)
    def wallet_intelligence(request: Request) -> WalletIntelligenceSnapshot:
        return get_service(request).get_wallet_intelligence()

    @app.get("/api/edge", response_model=EdgeSnapshot)
    def edge_snapshot(request: Request) -> EdgeSnapshot:
        return get_service(request).get_edge_snapshot()

    @app.get("/api/bots", response_model=list[BotSummary])
    def bots(request: Request) -> list[BotSummary]:
        return get_service(request).get_leaderboard(current_user_slug(request))

    @app.get("/api/bots/{slug}", response_model=BotDetail)
    def bot_detail(slug: str, request: Request) -> BotDetail:
        bot = get_service(request).get_bot_detail(slug, current_user_slug(request))
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        return bot

    @app.get("/api/leaderboard", response_model=list[BotSummary])
    def leaderboard(request: Request) -> list[BotSummary]:
        return get_service(request).get_leaderboard(current_user_slug(request))

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

    @app.get("/api/me", response_model=UserProfile)
    def me(request: Request) -> UserProfile:
        return get_service(request).get_user_profile(current_user_slug(request) or active_settings.default_user_slug)

    @app.get("/api/me/alerts", response_model=AlertInbox)
    def alert_inbox(request: Request, unread_only: bool = False) -> AlertInbox:
        return get_service(request).get_alert_inbox(current_user_slug(request) or active_settings.default_user_slug, unread_only=unread_only)

    @app.post("/api/me/alerts/{alert_id}/read", response_model=AlertInbox)
    def mark_alert_read(alert_id: int, request: Request) -> AlertInbox:
        return get_service(request).mark_alert_read(authenticated_user_slug(request), alert_id)

    @app.post("/api/me/alerts/read-all", response_model=AlertInbox)
    def mark_all_alerts_read(request: Request) -> AlertInbox:
        return get_service(request).mark_all_alerts_read(authenticated_user_slug(request))

    @app.post("/api/me/follows", response_model=UserProfile)
    def follow_bot(payload: FollowBotRequest, request: Request) -> UserProfile:
        return run_validated(lambda: get_service(request).follow_bot(authenticated_user_slug(request), payload.bot_slug))

    @app.delete("/api/me/follows/{bot_slug}", response_model=UserProfile)
    def unfollow_bot(bot_slug: str, request: Request) -> UserProfile:
        return get_service(request).unfollow_bot(authenticated_user_slug(request), bot_slug)

    @app.post("/api/me/watchlist", response_model=UserProfile)
    def add_watchlist_asset(payload: WatchlistAssetRequest, request: Request) -> UserProfile:
        return run_validated(lambda: get_service(request).add_watchlist_asset(authenticated_user_slug(request), payload.asset))

    @app.delete("/api/me/watchlist/{asset}", response_model=UserProfile)
    def remove_watchlist_asset(asset: str, request: Request) -> UserProfile:
        return get_service(request).remove_watchlist_asset(authenticated_user_slug(request), asset)

    @app.post("/api/me/alert-rules", response_model=UserProfile)
    def add_alert_rule(payload: AlertRuleCreate, request: Request) -> UserProfile:
        return run_validated(lambda: get_service(request).add_alert_rule(authenticated_user_slug(request), payload))

    @app.delete("/api/me/alert-rules/{rule_id}", response_model=UserProfile)
    def delete_alert_rule(rule_id: int, request: Request) -> UserProfile:
        return get_service(request).delete_alert_rule(authenticated_user_slug(request), rule_id)

    @app.get("/api/me/notification-channels", response_model=list[NotificationChannel])
    def notification_channels(request: Request) -> list[NotificationChannel]:
        profile = get_service(request).get_user_profile(current_user_slug(request) or active_settings.default_user_slug)
        return profile.notification_channels

    @app.get("/api/me/notification-health", response_model=NotificationHealthSnapshot)
    def notification_health(request: Request) -> NotificationHealthSnapshot:
        return get_service(request).get_notification_health(current_user_slug(request) or active_settings.default_user_slug)

    @app.get("/api/paper-trading", response_model=PaperTradingSnapshot)
    def paper_trading_snapshot(request: Request) -> PaperTradingSnapshot:
        return get_service(request).get_paper_trading_snapshot(current_user_slug(request) or active_settings.default_user_slug)

    @app.get("/api/simulation/config", response_model=SimulationConfig)
    def simulation_config(request: Request) -> SimulationConfig:
        return get_service(request).get_simulation_config()

    @app.post("/api/simulation/run", response_model=SimulationRunResult)
    def run_simulation(payload: SimulationRequest, request: Request) -> SimulationRunResult:
        return run_validated(lambda: get_service(request).run_simulation(payload))

    @app.post("/api/simulation/advanced-export", response_model=AdvancedBacktestExport)
    def advanced_simulation_export(payload: SimulationRequest, request: Request) -> AdvancedBacktestExport:
        return run_validated(lambda: get_service(request).export_advanced_backtest(payload))

    @app.get("/api/simulation/exports", response_model=list[SimulationExportArtifact])
    def simulation_exports(request: Request, limit: int = Query(default=12, ge=1, le=50)) -> list[SimulationExportArtifact]:
        return get_service(request).list_simulation_exports(limit=limit)

    @app.get("/api/simulation/exports/{filename}")
    def simulation_export_download(filename: str, request: Request) -> FileResponse:
        path = run_validated(lambda: get_service(request).get_simulation_export_path(filename))
        return FileResponse(path, media_type="application/json", filename=path.name)

    @app.post("/api/me/notification-channels", response_model=UserProfile)
    def add_notification_channel(payload: NotificationChannelCreate, request: Request) -> UserProfile:
        return run_validated(lambda: get_service(request).add_notification_channel(authenticated_user_slug(request), payload))

    @app.delete("/api/me/notification-channels/{channel_id}", response_model=UserProfile)
    def delete_notification_channel(channel_id: int, request: Request) -> UserProfile:
        return get_service(request).delete_notification_channel(authenticated_user_slug(request), channel_id)

    @app.get("/api/system/providers", response_model=ProviderStatusEnvelope)
    def provider_status(request: Request) -> ProviderStatusEnvelope:
        return ProviderStatusEnvelope(provider_status=get_service(request).get_provider_status())

    @app.get("/api/system/pulse", response_model=SystemPulseEnvelope)
    def system_pulse(request: Request) -> SystemPulseEnvelope:
        return SystemPulseEnvelope(system_pulse=get_service(request).get_system_pulse())

    @app.post("/api/admin/run-cycle", response_model=CycleResult)
    def run_cycle(request: Request) -> CycleResult:
        return get_service(request).run_pipeline_cycle()

    @app.post("/api/me/paper-trading/simulate", response_model=PaperSimulationResult)
    def simulate_my_paper_trading(request: Request) -> PaperSimulationResult:
        return get_service(request).simulate_paper_trading(authenticated_user_slug(request))

    @app.post("/api/admin/simulate-paper-trading", response_model=PaperSimulationResult)
    def simulate_demo_paper_trading(request: Request) -> PaperSimulationResult:
        return get_service(request).simulate_paper_trading(active_settings.default_user_slug)

    @app.post("/api/admin/retry-notifications", response_model=NotificationRetryResult)
    def retry_notifications(request: Request) -> NotificationRetryResult:
        return get_service(request).retry_failed_notifications()

    @app.get("/")
    def landing() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/dashboard")
    def dashboard() -> FileResponse:
        return FileResponse(STATIC_DIR / "dashboard.html")

    @app.get("/simulation")
    def simulation_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "simulation.html")

    @app.get("/status")
    def status_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "status.html")

    @app.get("/dashboard/")
    @app.get("/dachboard")
    @app.get("/dashbord")
    @app.get("/app")
    def dashboard_aliases() -> RedirectResponse:
        return RedirectResponse(url="/dashboard", status_code=307)

    @app.get("/simulation/")
    @app.get("/lab")
    def simulation_aliases() -> RedirectResponse:
        return RedirectResponse(url="/simulation", status_code=307)

    @app.get("/status/")
    @app.get("/ops")
    def status_aliases() -> RedirectResponse:
        return RedirectResponse(url="/status", status_code=307)

    return app


app = create_app()
