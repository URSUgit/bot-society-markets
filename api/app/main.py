from __future__ import annotations

from contextlib import asynccontextmanager
import json
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
    BillingCheckoutSessionRequest,
    BillingSessionLaunch,
    BillingSnapshot,
    BillingPortalSessionRequest,
    BillingWebhookAck,
    BotDetail,
    BotSummary,
    BusinessModelEnvelope,
    ConnectorControlEnvelope,
    CycleResult,
    DashboardSnapshot,
    EdgeSnapshot,
    FollowBotRequest,
    InfrastructureReadinessEnvelope,
    LandingSnapshot,
    LaunchReadinessEnvelope,
    MacroSnapshot,
    NotificationChannel,
    NotificationChannelCreate,
    NotificationHealthSnapshot,
    NotificationRetryResult,
    OperationSnapshot,
    PaperSimulationResult,
    PaperTradingSnapshot,
    PaperVenuesSnapshot,
    PredictionView,
    ProductionCutoverEnvelope,
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


def _request_host(request: Request) -> str:
    forwarded_host = request.headers.get("x-forwarded-host")
    raw_host = forwarded_host.split(",", 1)[0].strip() if forwarded_host else request.headers.get("host", "")
    return raw_host.split(":", 1)[0].strip().lower()


def _request_scheme(request: Request) -> str:
    cf_visitor = request.headers.get("cf-visitor")
    if cf_visitor:
        try:
            visitor_payload = json.loads(cf_visitor)
        except json.JSONDecodeError:
            visitor_payload = {}
        scheme = str(visitor_payload.get("scheme", "")).strip().lower()
        if scheme in {"http", "https"}:
            return scheme
    forwarded_proto = request.headers.get("x-forwarded-proto")
    if forwarded_proto:
        scheme = forwarded_proto.split(",", 1)[0].strip().lower()
        if scheme in {"http", "https"}:
            return scheme
    return request.url.scheme.lower()


def _request_authority(request: Request) -> str:
    forwarded_host = request.headers.get("x-forwarded-host")
    if forwarded_host:
        return forwarded_host.split(",", 1)[0].strip()
    host = request.headers.get("host")
    if host:
        return host.strip()
    return request.url.netloc


def _request_origin(request: Request, settings: Settings) -> str:
    scheme = "https" if settings.force_https else _request_scheme(request)
    host = settings.canonical_host or _request_authority(request)
    return f"{scheme}://{host}"


def _redirect_target(request: Request, *, scheme: str, host: str) -> str:
    path = request.url.path or "/"
    query = request.url.query
    suffix = f"?{query}" if query else ""
    return f"{scheme}://{host}{path}{suffix}"


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

    @app.middleware("http")
    async def enforce_public_routing(request: Request, call_next):
        request_host = _request_host(request)
        request_scheme = _request_scheme(request)
        public_hosts = {
            host
            for host in (active_settings.canonical_host, *active_settings.canonical_redirect_hosts)
            if host
        }
        if request_host in public_hosts:
            target_host = active_settings.canonical_host if request_host in active_settings.canonical_redirect_hosts and active_settings.canonical_host else request_host
            target_scheme = "https" if active_settings.force_https else request_scheme
            if target_host != request_host or target_scheme != request_scheme:
                return RedirectResponse(
                    url=_redirect_target(request, scheme=target_scheme, host=target_host),
                    status_code=308,
                )

        response = await call_next(request)
        if active_settings.force_https:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        return response

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
            secure=bool(active_settings.secure_session_cookie),
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

    @app.get("/api/business-model", response_model=BusinessModelEnvelope)
    def business_model(request: Request) -> BusinessModelEnvelope:
        return BusinessModelEnvelope(business_model=get_service(request).get_business_model_strategy())

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

    @app.get("/api/me/billing", response_model=BillingSnapshot)
    def me_billing(request: Request) -> BillingSnapshot:
        return get_service(request).get_billing_snapshot(current_user_slug(request) or active_settings.default_user_slug)

    @app.post("/api/me/billing/checkout-session", response_model=BillingSessionLaunch)
    def billing_checkout_session(payload: BillingCheckoutSessionRequest, request: Request) -> BillingSessionLaunch:
        return run_validated(
            lambda: get_service(request).create_billing_checkout_session(
                authenticated_user_slug(request),
                payload,
                base_url=_request_origin(request, active_settings),
            )
        )

    @app.post("/api/me/billing/portal-session", response_model=BillingSessionLaunch)
    def billing_portal_session(payload: BillingPortalSessionRequest, request: Request) -> BillingSessionLaunch:
        return run_validated(
            lambda: get_service(request).create_billing_portal_session(
                authenticated_user_slug(request),
                payload,
                base_url=_request_origin(request, active_settings),
            )
        )

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

    @app.get("/api/paper-venues", response_model=PaperVenuesSnapshot)
    def paper_venues(request: Request) -> PaperVenuesSnapshot:
        return get_service(request).get_paper_venues()

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

    @app.get("/api/simulation/packages/{filename}")
    def simulation_package_download(filename: str, request: Request) -> FileResponse:
        path = run_validated(lambda: get_service(request).get_simulation_package_path(filename))
        return FileResponse(path, media_type="application/zip", filename=path.name)

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

    @app.get("/api/system/launch-readiness", response_model=LaunchReadinessEnvelope)
    def launch_readiness(request: Request) -> LaunchReadinessEnvelope:
        return LaunchReadinessEnvelope(launch_readiness=get_service(request).get_launch_readiness())

    @app.get("/api/system/connectors", response_model=ConnectorControlEnvelope)
    def connector_control(request: Request) -> ConnectorControlEnvelope:
        return ConnectorControlEnvelope(connector_control=get_service(request).get_connector_control())

    @app.get("/api/system/infrastructure", response_model=InfrastructureReadinessEnvelope)
    def infrastructure_readiness(request: Request) -> InfrastructureReadinessEnvelope:
        return InfrastructureReadinessEnvelope(
            infrastructure_readiness=get_service(request).get_infrastructure_readiness()
        )

    @app.get("/api/system/production-cutover", response_model=ProductionCutoverEnvelope)
    def production_cutover(request: Request) -> ProductionCutoverEnvelope:
        return ProductionCutoverEnvelope(
            production_cutover=get_service(request).get_production_cutover()
        )

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

    @app.post("/api/webhooks/stripe", response_model=BillingWebhookAck)
    async def stripe_webhook(request: Request) -> BillingWebhookAck:
        body = await request.body()
        return run_validated(
            lambda: get_service(request).handle_stripe_webhook(
                body,
                request.headers.get("stripe-signature"),
            )
        )

    @app.get("/")
    def home() -> FileResponse:
        if active_settings.site_home_page == "dashboard":
            return FileResponse(STATIC_DIR / "dashboard.html")
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/landing")
    def landing() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/portfolio")
    def portfolio() -> FileResponse:
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

    @app.get("/terms")
    def terms_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "terms.html")

    @app.get("/privacy")
    def privacy_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "privacy.html")

    @app.get("/risk")
    def risk_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "risk.html")

    @app.get("/dashboard/")
    @app.get("/dachboard")
    @app.get("/dashbord")
    @app.get("/app")
    def dashboard_aliases() -> RedirectResponse:
        return RedirectResponse(url="/dashboard", status_code=307)

    @app.get("/landing/")
    @app.get("/home")
    def landing_aliases() -> RedirectResponse:
        return RedirectResponse(url="/landing", status_code=307)

    @app.get("/portfolio/")
    def portfolio_aliases() -> RedirectResponse:
        return RedirectResponse(url="/portfolio", status_code=307)

    @app.get("/simulation/")
    @app.get("/lab")
    def simulation_aliases() -> RedirectResponse:
        return RedirectResponse(url="/simulation", status_code=307)

    @app.get("/status/")
    @app.get("/ops")
    def status_aliases() -> RedirectResponse:
        return RedirectResponse(url="/status", status_code=307)

    @app.get("/terms-of-service")
    @app.get("/legal/terms")
    def terms_aliases() -> RedirectResponse:
        return RedirectResponse(url="/terms", status_code=307)

    @app.get("/privacy-policy")
    @app.get("/legal/privacy")
    def privacy_aliases() -> RedirectResponse:
        return RedirectResponse(url="/privacy", status_code=307)

    @app.get("/risk-disclosure")
    @app.get("/legal/risk")
    def risk_aliases() -> RedirectResponse:
        return RedirectResponse(url="/risk", status_code=307)

    return app


app = create_app()
