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
    AuditLogEnvelope,
    BillingCheckoutSessionRequest,
    BillingSessionLaunch,
    BillingSnapshot,
    BillingPortalSessionRequest,
    BillingWebhookAck,
    BotDetail,
    BotSummary,
    BusinessModelEnvelope,
    ConnectorControlEnvelope,
    ConnectorDiagnosticEnvelope,
    ConnectorDiagnosticsEnvelope,
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
    BacktestRunView,
    SimulationConfig,
    SimulationExportArtifact,
    SimulationRequest,
    SimulationRunResult,
    StrategyBacktestRequest,
    StrategyCreateRequest,
    StrategyUpdateRequest,
    StrategyView,
    Summary,
    SystemPulseEnvelope,
    TradingOrderRequest,
    TradingOrderView,
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


def _marketing_hosts(settings: Settings) -> set[str]:
    reserved_prefixes = ("app.", "api.", "status.")
    return {
        host
        for host in (settings.canonical_host, *settings.canonical_redirect_hosts)
        if host and not host.startswith(reserved_prefixes)
    }


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

    def request_ip(request: Request) -> str | None:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",", 1)[0].strip()
        cf_ip = request.headers.get("cf-connecting-ip")
        if cf_ip:
            return cf_ip.strip()
        return request.client.host if request.client else None

    def audit_event(
        request: Request,
        *,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        actor_user_slug: str | None = None,
        before_state: dict[str, object] | None = None,
        after_state: dict[str, object] | None = None,
    ) -> None:
        actor = actor_user_slug if actor_user_slug is not None else current_user_slug(request, fallback_to_demo=False)
        get_service(request).record_audit_event(
            actor_user_slug=actor,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=request_ip(request),
            user_agent=request.headers.get("user-agent"),
            before_state=before_state,
            after_state=after_state,
        )

    def run_validated(action):
        try:
            return action()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/health")
    def healthcheck() -> dict[str, str]:
        return {"status": "ok", "service": "bot-society-markets"}

    @app.get("/api/v1/auth/session", response_model=AuthSessionSnapshot)
    @app.get("/api/auth/session", response_model=AuthSessionSnapshot)
    def auth_session(request: Request) -> AuthSessionSnapshot:
        return get_service(request).get_session_snapshot(request.cookies.get(active_settings.auth_cookie_name))

    @app.post("/api/v1/auth/register", response_model=AuthSessionSnapshot)
    @app.post("/api/auth/register", response_model=AuthSessionSnapshot)
    def auth_register(payload: AuthRegisterRequest, request: Request, response: Response) -> AuthSessionSnapshot:
        session, token = run_validated(lambda: get_service(request).register_user(payload))
        set_session_cookie(response, token)
        audit_event(
            request,
            action="auth.register",
            resource_type="user",
            resource_id=session.user.slug if session.user else None,
            actor_user_slug=session.user.slug if session.user else None,
            after_state={"email": payload.email.strip().lower(), "display_name": payload.display_name.strip()},
        )
        return session

    @app.post("/api/v1/auth/login", response_model=AuthSessionSnapshot)
    @app.post("/api/auth/login", response_model=AuthSessionSnapshot)
    def auth_login(payload: AuthLoginRequest, request: Request, response: Response) -> AuthSessionSnapshot:
        session, token = run_validated(lambda: get_service(request).login_user(payload))
        set_session_cookie(response, token)
        audit_event(
            request,
            action="auth.login",
            resource_type="session",
            resource_id=session.user.slug if session.user else None,
            actor_user_slug=session.user.slug if session.user else None,
            after_state={"email": payload.email.strip().lower()},
        )
        return session

    @app.post("/api/v1/auth/logout", response_model=AuthSessionSnapshot)
    @app.post("/api/auth/logout", response_model=AuthSessionSnapshot)
    def auth_logout(request: Request, response: Response) -> AuthSessionSnapshot:
        actor = current_user_slug(request, fallback_to_demo=False)
        get_service(request).logout_session(request.cookies.get(active_settings.auth_cookie_name))
        clear_session_cookie(response)
        audit_event(
            request,
            action="auth.logout",
            resource_type="session",
            resource_id=actor,
            actor_user_slug=actor,
        )
        return AuthSessionSnapshot(authenticated=False, user=None)

    @app.get("/api/v1/landing/stats", response_model=LandingSnapshot)
    @app.get("/api/landing", response_model=LandingSnapshot)
    def landing_snapshot(request: Request) -> LandingSnapshot:
        return get_service(request).get_landing_snapshot(current_user_slug(request))

    @app.get("/api/v1/dashboard/summary", response_model=DashboardSnapshot)
    @app.get("/api/dashboard", response_model=DashboardSnapshot)
    def dashboard_snapshot(request: Request) -> DashboardSnapshot:
        return get_service(request).get_dashboard_snapshot(current_user_slug(request) or active_settings.default_user_slug)

    @app.get("/api/business-model", response_model=BusinessModelEnvelope)
    def business_model(request: Request) -> BusinessModelEnvelope:
        return BusinessModelEnvelope(business_model=get_service(request).get_business_model_strategy())

    @app.get("/api/v1/summary", response_model=Summary)
    @app.get("/api/summary", response_model=Summary)
    def summary(request: Request) -> Summary:
        return get_service(request).get_summary(current_user_slug(request))

    @app.get("/api/v1/assets", response_model=list[AssetSnapshot])
    @app.get("/api/assets", response_model=list[AssetSnapshot])
    def assets(request: Request) -> list[AssetSnapshot]:
        return get_service(request).get_assets()

    @app.get("/api/v1/assets/{asset}/history", response_model=AssetHistoryEnvelope)
    @app.get("/api/assets/{asset}/history", response_model=AssetHistoryEnvelope)
    def asset_history(asset: str, request: Request) -> AssetHistoryEnvelope:
        return run_validated(lambda: get_service(request).get_asset_history(asset))

    @app.get("/api/v1/macro", response_model=MacroSnapshot)
    @app.get("/api/macro", response_model=MacroSnapshot)
    def macro_snapshot(request: Request) -> MacroSnapshot:
        return get_service(request).get_macro_snapshot()

    @app.get("/api/v1/wallet-intelligence", response_model=WalletIntelligenceSnapshot)
    @app.get("/api/wallet-intelligence", response_model=WalletIntelligenceSnapshot)
    def wallet_intelligence(request: Request) -> WalletIntelligenceSnapshot:
        return get_service(request).get_wallet_intelligence()

    @app.get("/api/v1/edge", response_model=EdgeSnapshot)
    @app.get("/api/edge", response_model=EdgeSnapshot)
    def edge_snapshot(request: Request) -> EdgeSnapshot:
        return get_service(request).get_edge_snapshot()

    @app.get("/api/v1/bots", response_model=list[BotSummary])
    @app.get("/api/bots", response_model=list[BotSummary])
    def bots(request: Request) -> list[BotSummary]:
        return get_service(request).get_leaderboard(current_user_slug(request))

    @app.get("/api/v1/bots/{slug}", response_model=BotDetail)
    @app.get("/api/bots/{slug}", response_model=BotDetail)
    def bot_detail(slug: str, request: Request) -> BotDetail:
        bot = get_service(request).get_bot_detail(slug, current_user_slug(request))
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        return bot

    @app.get("/api/v1/signals/traders", response_model=list[BotSummary])
    @app.get("/api/v1/leaderboard", response_model=list[BotSummary])
    @app.get("/api/leaderboard", response_model=list[BotSummary])
    def leaderboard(request: Request) -> list[BotSummary]:
        return get_service(request).get_leaderboard(current_user_slug(request))

    @app.get("/api/v1/predictions", response_model=list[PredictionView])
    @app.get("/api/predictions", response_model=list[PredictionView])
    def predictions(
        request: Request,
        limit: int = Query(default=20, ge=1, le=100),
        status: str | None = Query(default=None, pattern="^(pending|scored)?$"),
    ) -> list[PredictionView]:
        return get_service(request).get_predictions(limit=limit, status=status)

    @app.get("/api/v1/signals", response_model=list[SignalView])
    @app.get("/api/signals", response_model=list[SignalView])
    def signals(request: Request, limit: int = Query(default=12, ge=1, le=100)) -> list[SignalView]:
        return get_service(request).get_signals(limit=limit)

    @app.get("/api/v1/operations/latest", response_model=OperationSnapshot | None)
    @app.get("/api/operations/latest", response_model=OperationSnapshot | None)
    def latest_operation(request: Request) -> OperationSnapshot | None:
        return get_service(request).get_latest_operation()

    @app.get("/api/v1/me", response_model=UserProfile)
    @app.get("/api/me", response_model=UserProfile)
    def me(request: Request) -> UserProfile:
        return get_service(request).get_user_profile(current_user_slug(request) or active_settings.default_user_slug)

    @app.get("/api/v1/me/billing", response_model=BillingSnapshot)
    @app.get("/api/me/billing", response_model=BillingSnapshot)
    def me_billing(request: Request) -> BillingSnapshot:
        return get_service(request).get_billing_snapshot(current_user_slug(request) or active_settings.default_user_slug)

    @app.post("/api/v1/me/billing/checkout-session", response_model=BillingSessionLaunch)
    @app.post("/api/me/billing/checkout-session", response_model=BillingSessionLaunch)
    def billing_checkout_session(payload: BillingCheckoutSessionRequest, request: Request) -> BillingSessionLaunch:
        user_slug = authenticated_user_slug(request)
        launch = run_validated(
            lambda: get_service(request).create_billing_checkout_session(
                user_slug,
                payload,
                base_url=_request_origin(request, active_settings),
            )
        )
        audit_event(
            request,
            action="billing.checkout_session_created",
            resource_type="billing_subscription",
            resource_id=launch.session_id,
            actor_user_slug=user_slug,
            after_state={"provider": launch.provider, "plan_key": launch.plan_key},
        )
        return launch

    @app.post("/api/v1/me/billing/portal-session", response_model=BillingSessionLaunch)
    @app.post("/api/me/billing/portal-session", response_model=BillingSessionLaunch)
    def billing_portal_session(payload: BillingPortalSessionRequest, request: Request) -> BillingSessionLaunch:
        user_slug = authenticated_user_slug(request)
        launch = run_validated(
            lambda: get_service(request).create_billing_portal_session(
                user_slug,
                payload,
                base_url=_request_origin(request, active_settings),
            )
        )
        audit_event(
            request,
            action="billing.portal_session_created",
            resource_type="billing_customer",
            resource_id=launch.session_id,
            actor_user_slug=user_slug,
            after_state={"provider": launch.provider, "return_path": payload.return_path},
        )
        return launch

    @app.get("/api/v1/me/alerts", response_model=AlertInbox)
    @app.get("/api/me/alerts", response_model=AlertInbox)
    def alert_inbox(request: Request, unread_only: bool = False) -> AlertInbox:
        return get_service(request).get_alert_inbox(current_user_slug(request) or active_settings.default_user_slug, unread_only=unread_only)

    @app.post("/api/v1/me/alerts/{alert_id}/read", response_model=AlertInbox)
    @app.post("/api/me/alerts/{alert_id}/read", response_model=AlertInbox)
    def mark_alert_read(alert_id: int, request: Request) -> AlertInbox:
        user_slug = authenticated_user_slug(request)
        inbox = get_service(request).mark_alert_read(user_slug, alert_id)
        audit_event(
            request,
            action="alerts.mark_read",
            resource_type="alert_delivery",
            resource_id=str(alert_id),
            actor_user_slug=user_slug,
        )
        return inbox

    @app.post("/api/v1/me/alerts/read-all", response_model=AlertInbox)
    @app.post("/api/me/alerts/read-all", response_model=AlertInbox)
    def mark_all_alerts_read(request: Request) -> AlertInbox:
        user_slug = authenticated_user_slug(request)
        inbox = get_service(request).mark_all_alerts_read(user_slug)
        audit_event(
            request,
            action="alerts.mark_all_read",
            resource_type="alert_delivery",
            actor_user_slug=user_slug,
            after_state={"unread_count": inbox.unread_count},
        )
        return inbox

    @app.post("/api/v1/me/follows", response_model=UserProfile)
    @app.post("/api/me/follows", response_model=UserProfile)
    def follow_bot(payload: FollowBotRequest, request: Request) -> UserProfile:
        user_slug = authenticated_user_slug(request)
        profile = run_validated(lambda: get_service(request).follow_bot(user_slug, payload.bot_slug))
        audit_event(
            request,
            action="workspace.follow_bot",
            resource_type="bot_follow",
            resource_id=payload.bot_slug,
            actor_user_slug=user_slug,
            after_state={"bot_slug": payload.bot_slug},
        )
        return profile

    @app.delete("/api/v1/me/follows/{bot_slug}", response_model=UserProfile)
    @app.delete("/api/me/follows/{bot_slug}", response_model=UserProfile)
    def unfollow_bot(bot_slug: str, request: Request) -> UserProfile:
        user_slug = authenticated_user_slug(request)
        profile = get_service(request).unfollow_bot(user_slug, bot_slug)
        audit_event(
            request,
            action="workspace.unfollow_bot",
            resource_type="bot_follow",
            resource_id=bot_slug,
            actor_user_slug=user_slug,
            before_state={"bot_slug": bot_slug},
        )
        return profile

    @app.post("/api/v1/me/watchlist", response_model=UserProfile)
    @app.post("/api/me/watchlist", response_model=UserProfile)
    def add_watchlist_asset(payload: WatchlistAssetRequest, request: Request) -> UserProfile:
        user_slug = authenticated_user_slug(request)
        profile = run_validated(lambda: get_service(request).add_watchlist_asset(user_slug, payload.asset))
        audit_event(
            request,
            action="workspace.watchlist_add",
            resource_type="watchlist_item",
            resource_id=payload.asset.upper(),
            actor_user_slug=user_slug,
            after_state={"asset": payload.asset.upper()},
        )
        return profile

    @app.delete("/api/v1/me/watchlist/{asset}", response_model=UserProfile)
    @app.delete("/api/me/watchlist/{asset}", response_model=UserProfile)
    def remove_watchlist_asset(asset: str, request: Request) -> UserProfile:
        user_slug = authenticated_user_slug(request)
        profile = get_service(request).remove_watchlist_asset(user_slug, asset)
        audit_event(
            request,
            action="workspace.watchlist_remove",
            resource_type="watchlist_item",
            resource_id=asset.upper(),
            actor_user_slug=user_slug,
            before_state={"asset": asset.upper()},
        )
        return profile

    @app.post("/api/v1/me/alert-rules", response_model=UserProfile)
    @app.post("/api/me/alert-rules", response_model=UserProfile)
    def add_alert_rule(payload: AlertRuleCreate, request: Request) -> UserProfile:
        user_slug = authenticated_user_slug(request)
        profile = run_validated(lambda: get_service(request).add_alert_rule(user_slug, payload))
        audit_event(
            request,
            action="workspace.alert_rule_create",
            resource_type="alert_rule",
            actor_user_slug=user_slug,
            after_state={
                "bot_slug": payload.bot_slug,
                "asset": payload.asset.upper() if payload.asset else None,
                "min_confidence": payload.min_confidence,
            },
        )
        return profile

    @app.delete("/api/v1/me/alert-rules/{rule_id}", response_model=UserProfile)
    @app.delete("/api/me/alert-rules/{rule_id}", response_model=UserProfile)
    def delete_alert_rule(rule_id: int, request: Request) -> UserProfile:
        user_slug = authenticated_user_slug(request)
        profile = get_service(request).delete_alert_rule(user_slug, rule_id)
        audit_event(
            request,
            action="workspace.alert_rule_delete",
            resource_type="alert_rule",
            resource_id=str(rule_id),
            actor_user_slug=user_slug,
        )
        return profile

    @app.get("/api/v1/me/notification-channels", response_model=list[NotificationChannel])
    @app.get("/api/me/notification-channels", response_model=list[NotificationChannel])
    def notification_channels(request: Request) -> list[NotificationChannel]:
        profile = get_service(request).get_user_profile(current_user_slug(request) or active_settings.default_user_slug)
        return profile.notification_channels

    @app.get("/api/v1/me/notification-health", response_model=NotificationHealthSnapshot)
    @app.get("/api/me/notification-health", response_model=NotificationHealthSnapshot)
    def notification_health(request: Request) -> NotificationHealthSnapshot:
        return get_service(request).get_notification_health(current_user_slug(request) or active_settings.default_user_slug)

    @app.get("/api/v1/paper-trading", response_model=PaperTradingSnapshot)
    @app.get("/api/v1/paper-trading/positions", response_model=PaperTradingSnapshot)
    @app.get("/api/paper-trading", response_model=PaperTradingSnapshot)
    def paper_trading_snapshot(request: Request) -> PaperTradingSnapshot:
        return get_service(request).get_paper_trading_snapshot(current_user_slug(request) or active_settings.default_user_slug)

    @app.get("/api/v1/trading/venues", response_model=PaperVenuesSnapshot)
    @app.get("/api/v1/paper-venues", response_model=PaperVenuesSnapshot)
    @app.get("/api/paper-venues", response_model=PaperVenuesSnapshot)
    def paper_venues(request: Request) -> PaperVenuesSnapshot:
        return get_service(request).get_paper_venues()

    @app.post("/api/v1/trading/orders", response_model=TradingOrderView)
    @app.post("/api/trading/orders", response_model=TradingOrderView)
    def place_trading_order(payload: TradingOrderRequest, request: Request) -> TradingOrderView:
        user_slug = authenticated_user_slug(request)
        order = run_validated(lambda: get_service(request).place_trading_order(user_slug, payload))
        audit_event(
            request,
            action="trading.order_place",
            resource_type="order",
            resource_id=str(order.id),
            actor_user_slug=user_slug,
            after_state={
                "venue": order.venue,
                "asset": order.asset,
                "side": order.side,
                "order_type": order.order_type,
                "is_paper": order.is_paper,
                "status": order.status,
                "notional_usd": order.notional_usd,
            },
        )
        return order

    @app.get("/api/v1/trading/orders", response_model=list[TradingOrderView])
    @app.get("/api/trading/orders", response_model=list[TradingOrderView])
    def list_trading_orders(
        request: Request,
        status: str | None = None,
        limit: int = Query(default=50, ge=1, le=200),
    ) -> list[TradingOrderView]:
        user_slug = authenticated_user_slug(request)
        return run_validated(lambda: get_service(request).list_trading_orders(user_slug, status=status, limit=limit))

    @app.get("/api/v1/trading/orders/{order_id}", response_model=TradingOrderView)
    @app.get("/api/trading/orders/{order_id}", response_model=TradingOrderView)
    def get_trading_order(order_id: int, request: Request) -> TradingOrderView:
        user_slug = authenticated_user_slug(request)
        return run_validated(lambda: get_service(request).get_trading_order(user_slug, order_id))

    @app.delete("/api/v1/trading/orders/{order_id}", response_model=TradingOrderView)
    @app.delete("/api/trading/orders/{order_id}", response_model=TradingOrderView)
    def cancel_trading_order(order_id: int, request: Request) -> TradingOrderView:
        user_slug = authenticated_user_slug(request)
        order = run_validated(lambda: get_service(request).cancel_trading_order(user_slug, order_id))
        audit_event(
            request,
            action="trading.order_cancel",
            resource_type="order",
            resource_id=str(order.id),
            actor_user_slug=user_slug,
            after_state={"status": order.status, "cancelled_at": order.cancelled_at},
        )
        return order

    @app.get("/api/v1/simulation/config", response_model=SimulationConfig)
    @app.get("/api/simulation/config", response_model=SimulationConfig)
    def simulation_config(request: Request) -> SimulationConfig:
        return get_service(request).get_simulation_config()

    @app.post("/api/v1/simulation/run", response_model=SimulationRunResult)
    @app.post("/api/simulation/run", response_model=SimulationRunResult)
    def run_simulation(payload: SimulationRequest, request: Request) -> SimulationRunResult:
        result = run_validated(lambda: get_service(request).run_simulation(payload))
        audit_event(
            request,
            action="simulation.run",
            resource_type="simulation",
            resource_id=f"{payload.asset.upper()}:{payload.strategy_id}",
            after_state={"asset": payload.asset, "strategy_id": payload.strategy_id, "lookback_years": payload.lookback_years},
        )
        return result

    @app.post("/api/v1/simulation/advanced-export", response_model=AdvancedBacktestExport)
    @app.post("/api/simulation/advanced-export", response_model=AdvancedBacktestExport)
    def advanced_simulation_export(payload: SimulationRequest, request: Request) -> AdvancedBacktestExport:
        export = run_validated(lambda: get_service(request).export_advanced_backtest(payload))
        audit_event(
            request,
            action="simulation.advanced_export",
            resource_type="simulation_export",
            resource_id=export.filename,
            after_state={"asset": payload.asset, "strategy_id": payload.strategy_id, "lookback_years": payload.lookback_years},
        )
        return export

    @app.get("/api/v1/simulation/exports", response_model=list[SimulationExportArtifact])
    @app.get("/api/simulation/exports", response_model=list[SimulationExportArtifact])
    def simulation_exports(request: Request, limit: int = Query(default=12, ge=1, le=50)) -> list[SimulationExportArtifact]:
        return get_service(request).list_simulation_exports(limit=limit)

    @app.get("/api/v1/simulation/exports/{filename}")
    @app.get("/api/simulation/exports/{filename}")
    def simulation_export_download(filename: str, request: Request) -> FileResponse:
        path = run_validated(lambda: get_service(request).get_simulation_export_path(filename))
        return FileResponse(path, media_type="application/json", filename=path.name)

    @app.get("/api/v1/simulation/packages/{filename}")
    @app.get("/api/simulation/packages/{filename}")
    def simulation_package_download(filename: str, request: Request) -> FileResponse:
        path = run_validated(lambda: get_service(request).get_simulation_package_path(filename))
        return FileResponse(path, media_type="application/zip", filename=path.name)

    @app.post("/api/v1/strategies", response_model=StrategyView)
    @app.post("/api/strategies", response_model=StrategyView)
    def create_strategy(payload: StrategyCreateRequest, request: Request) -> StrategyView:
        user_slug = authenticated_user_slug(request)
        strategy = run_validated(lambda: get_service(request).create_strategy(user_slug, payload))
        audit_event(
            request,
            action="strategy.create",
            resource_type="strategy",
            resource_id=str(strategy.id),
            actor_user_slug=user_slug,
            after_state={
                "name": strategy.name,
                "asset": strategy.config.asset,
                "strategy_id": strategy.config.strategy_id,
                "lookback_years": strategy.config.lookback_years,
            },
        )
        return strategy

    @app.get("/api/v1/strategies", response_model=list[StrategyView])
    @app.get("/api/strategies", response_model=list[StrategyView])
    def list_strategies(request: Request) -> list[StrategyView]:
        user_slug = authenticated_user_slug(request)
        return run_validated(lambda: get_service(request).list_strategies(user_slug))

    @app.get("/api/v1/strategies/backtests", response_model=list[BacktestRunView])
    @app.get("/api/strategies/backtests", response_model=list[BacktestRunView])
    def list_strategy_backtests(
        request: Request,
        strategy_id: int | None = Query(default=None, ge=1),
        limit: int = Query(default=20, ge=1, le=100),
    ) -> list[BacktestRunView]:
        user_slug = authenticated_user_slug(request)
        return run_validated(lambda: get_service(request).list_backtest_runs(user_slug, strategy_id=strategy_id, limit=limit))

    @app.get("/api/v1/strategies/backtests/{run_id}", response_model=BacktestRunView)
    @app.get("/api/strategies/backtests/{run_id}", response_model=BacktestRunView)
    def get_strategy_backtest(run_id: int, request: Request) -> BacktestRunView:
        user_slug = authenticated_user_slug(request)
        return run_validated(lambda: get_service(request).get_backtest_run(user_slug, run_id))

    @app.get("/api/v1/strategies/{strategy_id}", response_model=StrategyView)
    @app.get("/api/strategies/{strategy_id}", response_model=StrategyView)
    def get_strategy(strategy_id: int, request: Request) -> StrategyView:
        user_slug = authenticated_user_slug(request)
        return run_validated(lambda: get_service(request).get_strategy(user_slug, strategy_id))

    @app.put("/api/v1/strategies/{strategy_id}", response_model=StrategyView)
    @app.put("/api/strategies/{strategy_id}", response_model=StrategyView)
    def update_strategy(strategy_id: int, payload: StrategyUpdateRequest, request: Request) -> StrategyView:
        user_slug = authenticated_user_slug(request)
        before = run_validated(lambda: get_service(request).get_strategy(user_slug, strategy_id))
        strategy = run_validated(lambda: get_service(request).update_strategy(user_slug, strategy_id, payload))
        audit_event(
            request,
            action="strategy.update",
            resource_type="strategy",
            resource_id=str(strategy.id),
            actor_user_slug=user_slug,
            before_state={
                "name": before.name,
                "asset": before.config.asset,
                "strategy_id": before.config.strategy_id,
                "is_active": before.is_active,
            },
            after_state={
                "name": strategy.name,
                "asset": strategy.config.asset,
                "strategy_id": strategy.config.strategy_id,
                "is_active": strategy.is_active,
            },
        )
        return strategy

    @app.delete("/api/v1/strategies/{strategy_id}", response_model=StrategyView)
    @app.delete("/api/strategies/{strategy_id}", response_model=StrategyView)
    def delete_strategy(strategy_id: int, request: Request) -> StrategyView:
        user_slug = authenticated_user_slug(request)
        strategy = run_validated(lambda: get_service(request).delete_strategy(user_slug, strategy_id))
        audit_event(
            request,
            action="strategy.delete",
            resource_type="strategy",
            resource_id=str(strategy.id),
            actor_user_slug=user_slug,
            after_state={"name": strategy.name, "is_active": strategy.is_active},
        )
        return strategy

    @app.post("/api/v1/strategies/{strategy_id}/backtest", response_model=BacktestRunView)
    @app.post("/api/strategies/{strategy_id}/backtest", response_model=BacktestRunView)
    def run_strategy_backtest(
        strategy_id: int,
        request: Request,
        payload: StrategyBacktestRequest | None = None,
    ) -> BacktestRunView:
        user_slug = authenticated_user_slug(request)
        run = run_validated(lambda: get_service(request).run_strategy_backtest(user_slug, strategy_id, payload))
        audit_event(
            request,
            action="strategy.backtest_run",
            resource_type="backtest_run",
            resource_id=str(run.id),
            actor_user_slug=user_slug,
            after_state={
                "strategy_id": run.strategy_id,
                "asset": run.asset,
                "strategy_key": run.strategy_key,
                "lookback_years": run.lookback_years,
                "status": run.status,
                "total_return": run.summary.get("total_return"),
            },
        )
        return run

    @app.post("/api/v1/me/notification-channels", response_model=UserProfile)
    @app.post("/api/me/notification-channels", response_model=UserProfile)
    def add_notification_channel(payload: NotificationChannelCreate, request: Request) -> UserProfile:
        user_slug = authenticated_user_slug(request)
        profile = run_validated(lambda: get_service(request).add_notification_channel(user_slug, payload))
        audit_event(
            request,
            action="workspace.notification_channel_create",
            resource_type="notification_channel",
            actor_user_slug=user_slug,
            after_state={"channel_type": payload.channel_type, "target": payload.target},
        )
        return profile

    @app.delete("/api/v1/me/notification-channels/{channel_id}", response_model=UserProfile)
    @app.delete("/api/me/notification-channels/{channel_id}", response_model=UserProfile)
    def delete_notification_channel(channel_id: int, request: Request) -> UserProfile:
        user_slug = authenticated_user_slug(request)
        profile = get_service(request).delete_notification_channel(user_slug, channel_id)
        audit_event(
            request,
            action="workspace.notification_channel_delete",
            resource_type="notification_channel",
            resource_id=str(channel_id),
            actor_user_slug=user_slug,
        )
        return profile

    @app.get("/api/v1/system/providers", response_model=ProviderStatusEnvelope)
    @app.get("/api/system/providers", response_model=ProviderStatusEnvelope)
    def provider_status(request: Request) -> ProviderStatusEnvelope:
        return ProviderStatusEnvelope(provider_status=get_service(request).get_provider_status())

    @app.get("/api/v1/system/pulse", response_model=SystemPulseEnvelope)
    @app.get("/api/system/pulse", response_model=SystemPulseEnvelope)
    def system_pulse(request: Request) -> SystemPulseEnvelope:
        return SystemPulseEnvelope(system_pulse=get_service(request).get_system_pulse())

    @app.get("/api/v1/system/launch-readiness", response_model=LaunchReadinessEnvelope)
    @app.get("/api/system/launch-readiness", response_model=LaunchReadinessEnvelope)
    def launch_readiness(request: Request) -> LaunchReadinessEnvelope:
        return LaunchReadinessEnvelope(launch_readiness=get_service(request).get_launch_readiness())

    @app.get("/api/v1/system/connectors", response_model=ConnectorControlEnvelope)
    @app.get("/api/system/connectors", response_model=ConnectorControlEnvelope)
    def connector_control(request: Request) -> ConnectorControlEnvelope:
        return ConnectorControlEnvelope(connector_control=get_service(request).get_connector_control())

    @app.get("/api/v1/system/connectors/diagnostics", response_model=ConnectorDiagnosticsEnvelope)
    @app.get("/api/system/connectors/diagnostics", response_model=ConnectorDiagnosticsEnvelope)
    def connector_diagnostics(request: Request) -> ConnectorDiagnosticsEnvelope:
        return ConnectorDiagnosticsEnvelope(connector_diagnostics=get_service(request).get_connector_diagnostics())

    @app.get("/api/v1/system/connectors/{connector_id}/diagnostics", response_model=ConnectorDiagnosticEnvelope)
    @app.get("/api/system/connectors/{connector_id}/diagnostics", response_model=ConnectorDiagnosticEnvelope)
    def connector_diagnostic(connector_id: str, request: Request) -> ConnectorDiagnosticEnvelope:
        return ConnectorDiagnosticEnvelope(
            connector_diagnostic=run_validated(lambda: get_service(request).get_connector_diagnostic(connector_id))
        )

    @app.get("/api/v1/system/infrastructure", response_model=InfrastructureReadinessEnvelope)
    @app.get("/api/system/infrastructure", response_model=InfrastructureReadinessEnvelope)
    def infrastructure_readiness(request: Request) -> InfrastructureReadinessEnvelope:
        return InfrastructureReadinessEnvelope(
            infrastructure_readiness=get_service(request).get_infrastructure_readiness()
        )

    @app.get("/api/v1/system/production-cutover", response_model=ProductionCutoverEnvelope)
    @app.get("/api/system/production-cutover", response_model=ProductionCutoverEnvelope)
    def production_cutover(request: Request) -> ProductionCutoverEnvelope:
        return ProductionCutoverEnvelope(
            production_cutover=get_service(request).get_production_cutover()
        )

    @app.get("/api/v1/system/audit", response_model=AuditLogEnvelope)
    @app.get("/api/system/audit", response_model=AuditLogEnvelope)
    def audit_logs(
        request: Request,
        limit: int = Query(default=50, ge=1, le=200),
        actor_user_slug: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
    ) -> AuditLogEnvelope:
        requester_slug = authenticated_user_slug(request)
        if actor_user_slug and actor_user_slug != requester_slug:
            raise HTTPException(status_code=403, detail="Audit logs are scoped to the authenticated workspace")
        return AuditLogEnvelope(
            audit_logs=get_service(request).get_audit_logs(
                actor_user_slug=requester_slug,
                action=action,
                resource_type=resource_type,
                limit=limit,
            )
        )

    @app.post("/api/v1/admin/run-cycle", response_model=CycleResult)
    @app.post("/api/admin/run-cycle", response_model=CycleResult)
    def run_cycle(request: Request) -> CycleResult:
        result = get_service(request).run_pipeline_cycle()
        audit_event(
            request,
            action="admin.run_cycle",
            resource_type="pipeline_run",
            resource_id=str(result.operation.id) if result.operation else None,
            after_state={
                "generated_predictions": result.operation.generated_predictions if result.operation else 0,
                "ingested_signals": result.operation.ingested_signals if result.operation else 0,
                "scored_predictions": result.operation.scored_predictions if result.operation else 0,
            },
        )
        return result

    @app.post("/api/v1/me/paper-trading/simulate", response_model=PaperSimulationResult)
    @app.post("/api/me/paper-trading/simulate", response_model=PaperSimulationResult)
    def simulate_my_paper_trading(request: Request) -> PaperSimulationResult:
        user_slug = authenticated_user_slug(request)
        result = get_service(request).simulate_paper_trading(user_slug)
        audit_event(
            request,
            action="paper_trading.simulate",
            resource_type="paper_position",
            actor_user_slug=user_slug,
            after_state={"created_positions": result.created_positions, "closed_positions": result.closed_positions},
        )
        return result

    @app.post("/api/v1/admin/simulate-paper-trading", response_model=PaperSimulationResult)
    @app.post("/api/admin/simulate-paper-trading", response_model=PaperSimulationResult)
    def simulate_demo_paper_trading(request: Request) -> PaperSimulationResult:
        result = get_service(request).simulate_paper_trading(active_settings.default_user_slug)
        audit_event(
            request,
            action="admin.simulate_paper_trading",
            resource_type="paper_position",
            actor_user_slug=active_settings.default_user_slug,
            after_state={"created_positions": result.created_positions, "closed_positions": result.closed_positions},
        )
        return result

    @app.post("/api/v1/admin/retry-notifications", response_model=NotificationRetryResult)
    @app.post("/api/admin/retry-notifications", response_model=NotificationRetryResult)
    def retry_notifications(request: Request) -> NotificationRetryResult:
        result = get_service(request).retry_failed_notifications()
        audit_event(
            request,
            action="admin.retry_notifications",
            resource_type="notification_delivery",
            after_state={
                "scanned_events": result.scanned_events,
                "delivered": result.delivered,
                "rescheduled": result.rescheduled,
                "exhausted": result.exhausted,
            },
        )
        return result

    @app.post("/api/v1/webhooks/stripe", response_model=BillingWebhookAck)
    @app.post("/api/webhooks/stripe", response_model=BillingWebhookAck)
    async def stripe_webhook(request: Request) -> BillingWebhookAck:
        body = await request.body()
        ack = run_validated(
            lambda: get_service(request).handle_stripe_webhook(
                body,
                request.headers.get("stripe-signature"),
            )
        )
        audit_event(
            request,
            action="billing.webhook_processed",
            resource_type="billing_event",
            resource_id=ack.event_type,
            after_state={"event_type": ack.event_type, "duplicate": ack.duplicate, "status": ack.status},
        )
        return ack

    @app.get("/")
    def home(request: Request) -> FileResponse:
        request_host = _request_host(request)
        if request_host == "status.bitprivat.com":
            return FileResponse(STATIC_DIR / "status.html")
        if request_host in _marketing_hosts(active_settings):
            return FileResponse(STATIC_DIR / "index.html")
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
