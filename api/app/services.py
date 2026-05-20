from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
import re
from textwrap import dedent
from datetime import datetime, timedelta, timezone
from statistics import mean, median, pstdev
import zipfile

from sqlalchemy.exc import IntegrityError

from .auth import AuthManager
from .billing import StripeClient, StripeClientError, StripeSignatureError
from .config import Settings
from .database import Database
from .models import (
    AdvancedBacktestExport,
    AlertDelivery,
    AlertInbox,
    AuditLogEntry,
    AlertRule,
    AlertRuleCreate,
    AssetHistoryEnvelope,
    AssetHistoryPoint,
    AssetSnapshot,
    BillingCheckoutSessionRequest,
    BillingPlanView,
    BillingPortalSessionRequest,
    BillingSessionLaunch,
    BillingSnapshot,
    BillingWebhookAck,
    AuthLoginRequest,
    AuthRegisterRequest,
    AuthSessionSnapshot,
    BusinessModelMilestone,
    BusinessModelMoatStep,
    BusinessModelProduct,
    BusinessModelRevenueStream,
    BusinessModelSnapshot,
    BusinessModelStrategyFamily,
    BusinessModelTeamRole,
    BotDetail,
    BotSummary,
    ConnectorDiagnosticCheck,
    ConnectorDiagnosticResult,
    CycleResult,
    DashboardSnapshot,
    EdgeOpportunityView,
    EdgeSnapshot,
    FollowedBot,
    ConnectorControlSnapshot,
    ConnectorStatusItem,
    InfrastructureReadinessSnapshot,
    InfrastructureTask,
    LandingSnapshot,
    LaunchReadinessSnapshot,
    LaunchReadinessTrack,
    MacroObservationPoint,
    MacroSeriesSnapshot,
    MacroSnapshot,
    NotificationChannel,
    NotificationChannelHealth,
    NotificationChannelCreate,
    NotificationHealthSnapshot,
    NotificationRetryResult,
    OperationSnapshot,
    PaperPortfolioSummary,
    PaperPositionView,
    PaperSimulationResult,
    PaperTradingSnapshot,
    PaperVenueCapability,
    PaperVenuesSnapshot,
    PaperVenueView,
    PredictionView,
    ProviderComponentStatus,
    ProviderStatus,
    ProductionCutoverSnapshot,
    ProductionCutoverStep,
    SignalView,
    SignalMixItem,
    SocialDiscoveryRunView,
    SocialDiscoveryRunResult,
    SocialEvidenceItem,
    SocialManagedPaperExecutionRequest,
    SocialManagedPaperExecutionResult,
    SocialMonitoringStatus,
    SocialPortfolioDiversifyRequest,
    SocialRoiWindow,
    SocialTraderAnalyzeRequest,
    SocialTraderAllocation,
    SocialTraderAssetExposure,
    SocialTraderDecision,
    SocialTraderFollowRequest,
    SocialTraderScorecard,
    SocialTradingSnapshot,
    SimulationConfig,
    SimulationDataSourceOption,
    SimulationExportArtifact,
    SimulationLeaderboardEntry,
    SimulationRequest,
    SimulationRunResult,
    SimulationSeriesPoint,
    SimulationStrategyPreset,
    SimulationStrategyResult,
    SimulationTradeView,
    BacktestRunView,
    StrategyBacktestRequest,
    StrategyCreateRequest,
    StrategyUpdateRequest,
    StrategyView,
    Summary,
    SystemPulseSnapshot,
    TradingOrderRequest,
    TradingOrderView,
    UserIdentity,
    UserProfile,
    VenuePulseItem,
    WalletIntelligenceSnapshot,
    WalletProfileView,
    WatchlistItem,
)
from .notifications import NotificationDispatcher
from .orchestration import PredictionOrchestrator
from .providers import (
    AutoMarketProvider,
    CoinGeckoMarketProvider,
    DemoMarketProvider,
    DemoMacroProvider,
    DemoPredictionMarketIntelProvider,
    DemoSignalProvider,
    DemoWalletProvider,
    FredMacroProvider,
    HyperliquidMarketProvider,
    KalshiSignalProvider,
    PolymarketPredictionMarketIntelProvider,
    PolymarketSignalProvider,
    PolymarketWalletProvider,
    RedditSignalProvider,
    RSSNewsSignalProvider,
)
from .repository import BotSocietyRepository
from .scoring import ScoringEngine, clamp
from .seed import ensure_demo_user_state, seed_demo_dataset
from .social_intelligence import (
    DemoSocialDiscoveryProvider,
    DiscoveredSocialTrader,
    SocialEvidenceRecord,
    YouTubeSocialDiscoveryProvider,
)
from .utils import parse_timestamp, to_timestamp

SLUG_RE = re.compile(r"[^a-z0-9]+")


class BotSocietyService:
    SIMULATION_PRESETS = [
        SimulationStrategyPreset(
            strategy_id="buy_hold",
            label="Buy and hold",
            description="Stay long the entire test window and use it as the benchmark.",
        ),
        SimulationStrategyPreset(
            strategy_id="trend_follow",
            label="Trend follow",
            description="Go long when price is above both fast and slow moving averages.",
        ),
        SimulationStrategyPreset(
            strategy_id="mean_reversion",
            label="Mean reversion",
            description="Buy sharp pullbacks below the rolling mean and exit when the move normalizes.",
        ),
        SimulationStrategyPreset(
            strategy_id="breakout",
            label="Breakout",
            description="Enter when price breaks the recent high and step aside when momentum fails.",
        ),
        SimulationStrategyPreset(
            strategy_id="custom_creator",
            label="Creator Blend",
            description="Blend trend, pullback, and breakout signals with editable thresholds and risk exits.",
        ),
    ]

    def __init__(self, database: Database, settings: Settings) -> None:
        self.database = database
        self.settings = settings
        self.auth = AuthManager()
        self.dispatcher = NotificationDispatcher(settings)
        self.demo_market_provider = DemoMarketProvider()
        self.demo_signal_provider = DemoSignalProvider()
        self.demo_macro_provider = DemoMacroProvider(series_ids=self.settings.fred_series_ids)
        self.demo_wallet_provider = DemoWalletProvider()
        self.demo_market_intel_provider = DemoPredictionMarketIntelProvider()
        self.history_provider = CoinGeckoMarketProvider(
            plan=self.settings.coingecko_plan,
            api_key=self.settings.coingecko_api_key,
            tracked_coin_ids=self.settings.tracked_coin_ids,
        )
        self.market_provider = self._build_market_provider()
        self.signal_provider = self._build_signal_provider()
        self.social_discovery_provider = self._build_social_discovery_provider()
        self.macro_provider = self._build_macro_provider()
        self.wallet_provider = self._build_wallet_provider()
        self.market_intel_provider = PolymarketPredictionMarketIntelProvider(
            tag_id=self.settings.polymarket_tag_id,
            event_limit=self.settings.polymarket_event_limit,
        )
        self.venue_signal_providers = self._build_venue_signal_providers()
        self.orchestrator = PredictionOrchestrator()
        self.market_provider_fallback = False
        self.signal_provider_fallback = False
        self.macro_provider_fallback = False
        self.wallet_provider_fallback = False
        self.market_provider_source = self.market_provider.source_name
        self.signal_provider_source = self._compose_signal_provider_source()
        self.macro_provider_source = self.macro_provider.source_name
        self.wallet_provider_source = self.wallet_provider.source_name
        self.wallet_snapshot_cache: tuple[datetime, WalletIntelligenceSnapshot] | None = None
        self.edge_snapshot_cache: tuple[datetime, EdgeSnapshot] | None = None
        self.macro_snapshot_cache: tuple[datetime, MacroSnapshot] | None = None
        self.provider_status_cache: tuple[datetime, ProviderStatus] | None = None
        self.system_pulse_cache: tuple[datetime, SystemPulseSnapshot] | None = None
        self.assets_cache: tuple[datetime, list[AssetSnapshot]] | None = None
        self.leaderboard_cache: dict[str, tuple[datetime, list[BotSummary]]] = {}
        self.landing_snapshot_cache: dict[str, tuple[datetime, LandingSnapshot]] = {}
        self.dashboard_snapshot_cache: dict[str, tuple[datetime, DashboardSnapshot]] = {}

    def bootstrap(self) -> None:
        self.database.initialize()
        repository = BotSocietyRepository(self.database)
        seeded = seed_demo_dataset(repository) if self.settings.seed_demo_data else False
        ensure_demo_user_state(repository)
        social_refresh = self._bootstrap_social_trader_discovery(repository)
        macro_refreshed = self._refresh_macro_data(repository)
        refreshed_signals = repository.refresh_signal_quality_scores()
        repository.delete_expired_sessions(self._now())
        scorer = ScoringEngine(repository, self.settings.scoring_version)
        scored = scorer.score_available_predictions()
        demo_paper_positions = self._seed_demo_paper_trading(repository)
        alert_deliveries = self._deliver_alerts_for_predictions(repository, repository.list_predictions(limit=12))
        if seeded:
            repository.insert_pipeline_run(
                {
                    "cycle_type": "bootstrap",
                    "status": "completed",
                    "started_at": "2026-04-08T00:01:00Z",
                    "completed_at": "2026-04-08T00:01:00Z",
                    "ingested_signals": 0,
                    "generated_predictions": 0,
                    "scored_predictions": scored,
                    "message": (
                        "Seeded demo market data, user state, historical signals, and scored the initial prediction archive. "
                        f"Initialized {alert_deliveries} alert deliveries, refreshed {refreshed_signals} signal quality records, "
                        f"hydrated {macro_refreshed} macro observations, seeded {demo_paper_positions} demo paper positions, "
                        f"and indexed {social_refresh.updated} social trader profile(s)."
                    ),
                }
            )
        self._warm_public_snapshot_caches()

    def resolve_user_slug(self, session_token: str | None, *, fallback_to_demo: bool = True) -> str | None:
        if not session_token:
            return self.settings.default_user_slug if fallback_to_demo else None
        repository = BotSocietyRepository(self.database)
        token_hash = self.auth.hash_session_token(session_token)
        session = repository.get_session(token_hash)
        if not session:
            return self.settings.default_user_slug if fallback_to_demo else None
        if not bool(session["is_active"]):
            repository.delete_session(token_hash)
            return self.settings.default_user_slug if fallback_to_demo else None
        if parse_timestamp(session["expires_at"]) <= datetime.now(timezone.utc):
            repository.delete_session(token_hash)
            return self.settings.default_user_slug if fallback_to_demo else None
        repository.touch_session(token_hash, last_seen_at=self._now(), expires_at=self._session_expires_at())
        return str(session["user_slug"])

    def get_session_snapshot(self, session_token: str | None) -> AuthSessionSnapshot:
        user_slug = self.resolve_user_slug(session_token, fallback_to_demo=False)
        if not user_slug:
            return AuthSessionSnapshot(authenticated=False, user=None)
        repository = BotSocietyRepository(self.database)
        user = repository.get_user(user_slug)
        if not user:
            return AuthSessionSnapshot(authenticated=False, user=None)
        return AuthSessionSnapshot(authenticated=True, user=self._to_user_identity(user))

    def register_user(self, payload: AuthRegisterRequest) -> tuple[AuthSessionSnapshot, str]:
        repository = BotSocietyRepository(self.database)
        email = payload.email.strip().lower()
        if repository.get_user_by_email(email):
            raise ValueError("An account with that email already exists")
        slug = self._generate_user_slug(repository, payload.display_name, email)
        try:
            repository.create_user(
                {
                    "slug": slug,
                    "display_name": payload.display_name.strip(),
                    "email": email,
                    "tier": "starter",
                    "created_at": self._now(),
                    "password_hash": self.auth.hash_password(payload.password),
                    "is_active": True,
                    "is_demo_user": False,
                }
            )
        except IntegrityError as exc:
            raise ValueError("Unable to create account with that email") from exc
        return self._create_session_for_user(slug)

    def login_user(self, payload: AuthLoginRequest) -> tuple[AuthSessionSnapshot, str]:
        repository = BotSocietyRepository(self.database)
        email = payload.email.strip().lower()
        user = repository.get_user_by_email(email)
        if not user or not self.auth.verify_password(payload.password, user.get("password_hash")):
            raise ValueError("Invalid email or password")
        if not bool(user.get("is_active", True)):
            raise ValueError("This account is inactive")
        return self._create_session_for_user(str(user["slug"]))

    def logout_session(self, session_token: str | None) -> None:
        if not session_token:
            return
        repository = BotSocietyRepository(self.database)
        repository.delete_session(self.auth.hash_session_token(session_token))

    def record_audit_event(
        self,
        *,
        actor_user_slug: str | None,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        before_state: dict[str, object] | None = None,
        after_state: dict[str, object] | None = None,
    ) -> int:
        repository = BotSocietyRepository(self.database)
        return repository.create_audit_log(
            {
                "actor_user_slug": actor_user_slug,
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "before_state_json": self._encode_audit_state(before_state),
                "after_state_json": self._encode_audit_state(after_state),
                "created_at": self._now(),
            }
        )

    def get_audit_logs(
        self,
        *,
        actor_user_slug: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        limit: int = 50,
    ) -> list[AuditLogEntry]:
        repository = BotSocietyRepository(self.database)
        return [
            AuditLogEntry(
                id=int(row["id"]),
                actor_user_slug=row.get("actor_user_slug"),
                action=str(row["action"]),
                resource_type=str(row["resource_type"]),
                resource_id=row.get("resource_id"),
                ip_address=row.get("ip_address"),
                user_agent=row.get("user_agent"),
                before_state=self._decode_audit_state(row.get("before_state_json")),
                after_state=self._decode_audit_state(row.get("after_state_json")),
                created_at=str(row["created_at"]),
            )
            for row in repository.list_audit_logs(
                actor_user_slug=actor_user_slug,
                action=action,
                resource_type=resource_type,
                limit=limit,
            )
        ]

    def refresh_social_trader_discovery(
        self,
        *,
        repository: BotSocietyRepository | None = None,
    ) -> SocialDiscoveryRunResult:
        active_repository = repository or BotSocietyRepository(self.database)
        started_at = self._now()
        provider_name = getattr(self.social_discovery_provider, "source_name", self.settings.social_discovery_provider)
        try:
            before_slugs = {str(row["slug"]) for row in active_repository.list_social_traders(limit=500)}
            result = self.social_discovery_provider.discover()
            return self._persist_social_discovery_result(
                active_repository=active_repository,
                result=result,
                started_at=started_at,
                before_slugs=before_slugs,
                ingest_batch_prefix="social-discovery",
            )
        except Exception as exc:
            completed_at = self._now()
            try:
                active_repository.insert_social_discovery_run(
                    {
                        "provider": provider_name,
                        "status": "failed",
                        "youtube_configured": bool(self.settings.youtube_api_key),
                        "discovered_count": 0,
                        "updated_count": 0,
                        "evidence_count": 0,
                        "warnings_json": self._encode_json_payload([f"{exc.__class__.__name__}: {exc}"]) or "[]",
                        "started_at": started_at,
                        "completed_at": completed_at,
                    }
                )
            except Exception:
                pass
            self._clear_live_caches()
            raise

    def _bootstrap_social_trader_discovery(self, repository: BotSocietyRepository) -> SocialDiscoveryRunResult:
        """Keep web startup independent from external social APIs."""
        existing_rows = repository.list_social_traders(limit=12)
        if existing_rows:
            return SocialDiscoveryRunResult(
                discovered=0,
                updated=0,
                provider=getattr(self.social_discovery_provider, "source_name", self.settings.social_discovery_provider),
                youtube_configured=bool(self.settings.youtube_api_key),
                traders=[
                    self._to_social_trader_scorecard(row, repository.list_social_trader_events(int(row["id"]), limit=6))
                    for row in existing_rows
                ],
                warnings=[
                    "Startup skipped live YouTube discovery so the web service can become ready without waiting on outbound APIs."
                ],
            )

        started_at = self._now()
        result = DemoSocialDiscoveryProvider().discover(include_key_warning=False)
        result.youtube_configured = bool(self.settings.youtube_api_key)
        result.warnings = [
            "Startup seeded the social trader watchlist from deterministic creator profiles; run discovery or analyze a target for live YouTube data.",
            *result.warnings,
        ]
        return self._persist_social_discovery_result(
            active_repository=repository,
            result=result,
            started_at=started_at,
            before_slugs=set(),
            ingest_batch_prefix="social-bootstrap",
        )

    def analyze_social_trader_target(
        self,
        payload: SocialTraderAnalyzeRequest,
        *,
        repository: BotSocietyRepository | None = None,
    ) -> SocialDiscoveryRunResult:
        active_repository = repository or BotSocietyRepository(self.database)
        started_at = self._now()
        provider_name = getattr(self.social_discovery_provider, "source_name", self.settings.social_discovery_provider)
        try:
            before_slugs = {str(row["slug"]) for row in active_repository.list_social_traders(limit=500)}
            provider = self.social_discovery_provider
            if hasattr(provider, "discover_target"):
                result = provider.discover_target(payload.query, video_limit=payload.video_limit)
            else:
                result = DemoSocialDiscoveryProvider().discover_target(payload.query, video_limit=payload.video_limit)
                result.provider = provider_name
                result.warnings.insert(0, "Active social provider cannot analyze an ad-hoc target, so demo analysis was used.")
            return self._persist_social_discovery_result(
                active_repository=active_repository,
                result=result,
                started_at=started_at,
                before_slugs=before_slugs,
                ingest_batch_prefix="social-target",
                focus_slugs=[trader.slug for trader in result.traders],
            )
        except Exception as exc:
            completed_at = self._now()
            try:
                active_repository.insert_social_discovery_run(
                    {
                        "provider": provider_name,
                        "status": "failed",
                        "youtube_configured": bool(self.settings.youtube_api_key),
                        "discovered_count": 0,
                        "updated_count": 0,
                        "evidence_count": 0,
                        "warnings_json": self._encode_json_payload([f"{exc.__class__.__name__}: {exc}"]) or "[]",
                        "started_at": started_at,
                        "completed_at": completed_at,
                    }
                )
            except Exception:
                pass
            self._clear_live_caches()
            raise

    def _persist_social_discovery_result(
        self,
        *,
        active_repository: BotSocietyRepository,
        result,
        started_at: str,
        before_slugs: set[str],
        ingest_batch_prefix: str,
        focus_slugs: list[str] | None = None,
    ) -> SocialDiscoveryRunResult:
        now = self._now()
        trader_payloads = [self._social_trader_payload(trader, now=now) for trader in result.traders]
        active_repository.upsert_social_traders(trader_payloads)

        refreshed_rows = active_repository.list_social_traders(limit=500)
        trader_ids = {str(row["slug"]): int(row["id"]) for row in refreshed_rows}
        event_payloads: list[dict[str, object]] = []
        for trader in result.traders:
            trader_id = trader_ids.get(trader.slug)
            if not trader_id:
                continue
            event_payloads.extend(self._social_event_payloads(trader_id, trader.evidence, now=now))
        active_repository.upsert_social_trader_events(event_payloads)
        signal_payloads = self._social_signal_payloads(
            result.traders,
            provider=result.provider,
            ingest_batch_id=f"{ingest_batch_prefix}:{started_at}",
        )
        social_signals_created = active_repository.upsert_signals(signal_payloads)

        discovered_count = len([payload for payload in trader_payloads if str(payload["slug"]) not in before_slugs])
        updated_count = len(trader_payloads)
        evidence_count = len(event_payloads)
        active_repository.insert_social_discovery_run(
            {
                "provider": result.provider,
                "status": "completed_with_warnings" if result.warnings else "completed",
                "youtube_configured": bool(result.youtube_configured),
                "discovered_count": discovered_count,
                "updated_count": updated_count,
                "evidence_count": evidence_count,
                "warnings_json": self._encode_json_payload(result.warnings) or "[]",
                "started_at": started_at,
                "completed_at": self._now(),
            }
        )
        self._clear_live_caches()

        visible_rows = self._social_discovery_visible_rows(
            active_repository,
            focus_slugs=focus_slugs,
            limit=12,
        )
        visible_scorecards = [
            self._to_social_trader_scorecard(row, active_repository.list_social_trader_events(int(row["id"]), limit=6))
            for row in visible_rows
        ]
        return SocialDiscoveryRunResult(
            discovered=discovered_count,
            updated=updated_count,
            provider=result.provider,
            youtube_configured=result.youtube_configured,
            traders=visible_scorecards,
            warnings=[
                *result.warnings,
                f"Created {social_signals_created} normalized social signal(s) for bot scoring.",
            ],
        )

    def _social_discovery_visible_rows(
        self,
        active_repository: BotSocietyRepository,
        *,
        focus_slugs: list[str] | None,
        limit: int,
    ) -> list[dict[str, object]]:
        if not focus_slugs:
            return active_repository.list_social_traders(limit=limit)

        all_rows = active_repository.list_social_traders(limit=500)
        rows_by_slug = {str(row["slug"]): row for row in all_rows}
        focused_rows = [rows_by_slug[slug] for slug in focus_slugs if slug in rows_by_slug]
        focused_ids = {int(row["id"]) for row in focused_rows}
        remaining_rows = [row for row in active_repository.list_social_traders(limit=limit) if int(row["id"]) not in focused_ids]
        return [*focused_rows, *remaining_rows][:limit]

    def get_social_trading_snapshot(
        self,
        user_slug: str,
        repository: BotSocietyRepository | None = None,
    ) -> SocialTradingSnapshot:
        active_repository = repository or BotSocietyRepository(self.database)
        trader_rows = active_repository.list_social_traders(limit=16)
        top_traders = [
            self._to_social_trader_scorecard(row, active_repository.list_social_trader_events(int(row["id"]), limit=5))
            for row in trader_rows
        ]
        allocations = [
            self._to_social_trader_allocation(row)
            for row in active_repository.list_social_trader_allocations(user_slug)
        ]
        allocation_by_trader = {allocation.trader_id: allocation for allocation in allocations}
        for trader in top_traders:
            allocation = allocation_by_trader.get(trader.id)
            if allocation and allocation.is_active:
                trader.is_deployed = True
                trader.deployment_mode = allocation.mode
                trader.delegated_usd = allocation.allocation_limit_usd
                trader.deployed_max_position_pct = allocation.max_position_pct
        discovery_runs = [
            self._to_social_discovery_run(row)
            for row in active_repository.list_social_discovery_runs(limit=6)
        ]
        allocated_usd = round(sum(item.allocation_limit_usd for item in allocations if item.is_active), 2)
        portfolio_limit = round(max(self.settings.paper_starting_balance, allocated_usd), 2)
        unallocated = round(max(0.0, portfolio_limit - allocated_usd), 2)
        leader_count = len(top_traders)
        youtube_configured = bool(self.settings.youtube_api_key)
        if leader_count:
            summary = (
                f"{leader_count} creator-trader profile(s) indexed. "
                f"{len(allocations)} followed allocation(s), {allocated_usd:,.0f} USD paper risk assigned."
            )
        else:
            summary = "No social trader profiles are indexed yet. Run discovery to seed the YouTube-first watchlist."
        return SocialTradingSnapshot(
            generated_at=self._now(),
            provider_mode=getattr(self.social_discovery_provider, "source_name", self.settings.social_discovery_provider),
            youtube_required=True,
            youtube_configured=youtube_configured,
            summary=summary,
            top_traders=top_traders,
            allocations=allocations,
            portfolio_limit_usd=portfolio_limit,
            allocated_usd=allocated_usd,
            unallocated_usd=unallocated,
            latest_discovery_run=discovery_runs[0] if discovery_runs else None,
            discovery_runs=discovery_runs,
            diversification_plan=self._social_diversification_plan(top_traders, allocations),
            portfolio_risk_notes=self._social_portfolio_risk_notes(
                top_traders,
                allocations,
                allocated_usd=allocated_usd,
                portfolio_limit=portfolio_limit,
                youtube_configured=youtube_configured,
            ),
            safety_notes=[
                "Signal mode sends alerts and watchlist updates only.",
                "Managed mode is paper-only here: no live user funds are moved by this MVP.",
                "Live copy trading requires KYC/suitability review, exchange authorization, risk controls, audit logging, and legal sign-off.",
                "YouTube ingestion uses the official YouTube Data API when BSM_YOUTUBE_API_KEY is configured.",
            ],
            monitoring=self._social_monitoring_status(discovery_runs),
            decision_feed=[
                decision
                for trader in top_traders[:6]
                for decision in trader.decision_feed[:2]
            ][:10],
        )

    def follow_social_trader(
        self,
        user_slug: str,
        payload: SocialTraderFollowRequest,
    ) -> SocialTradingSnapshot:
        repository = BotSocietyRepository(self.database)
        if not repository.get_user(user_slug):
            raise ValueError(f"User {user_slug} is not available")
        trader = (
            repository.get_social_trader_by_id(payload.trader_id)
            if payload.trader_id
            else repository.get_social_trader_by_slug(str(payload.trader_slug))
        )
        if not trader:
            raise ValueError("Social trader profile was not found. Run discovery first.")
        if payload.mode == "managed_paper" and payload.allocation_limit_usd <= 0:
            raise ValueError("Managed paper mode needs an allocation limit above zero")
        if payload.allocation_limit_usd > self.settings.paper_starting_balance * 10:
            raise ValueError("Allocation is above the configured safety ceiling for this workspace")
        now = self._now()
        repository.upsert_social_trader_allocation(
            {
                "user_slug": user_slug,
                "trader_id": int(trader["id"]),
                "mode": payload.mode,
                "allocation_limit_usd": round(payload.allocation_limit_usd, 2),
                "max_position_pct": round(payload.max_position_pct, 4),
                "auto_rebalance": bool(payload.auto_rebalance),
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            }
        )
        self._clear_live_caches()
        return self.get_social_trading_snapshot(user_slug, repository)

    def diversify_social_portfolio(
        self,
        user_slug: str,
        payload: SocialPortfolioDiversifyRequest,
    ) -> SocialTradingSnapshot:
        repository = BotSocietyRepository(self.database)
        if not repository.get_user(user_slug):
            raise ValueError(f"User {user_slug} is not available")
        top_traders = repository.list_social_traders(limit=payload.trader_count)
        if not top_traders:
            discovery = self.refresh_social_trader_discovery(repository=repository)
            top_traders = repository.list_social_traders(limit=payload.trader_count)
            if not top_traders:
                raise ValueError(f"Social discovery returned no profiles ({'; '.join(discovery.warnings)})")
        total_weight = sum(max(1.0, float(row.get("composite_score") or 1.0)) for row in top_traders)
        now = self._now()
        for row in top_traders:
            weight = max(1.0, float(row.get("composite_score") or 1.0)) / total_weight
            repository.upsert_social_trader_allocation(
                {
                    "user_slug": user_slug,
                    "trader_id": int(row["id"]),
                    "mode": payload.mode,
                    "allocation_limit_usd": round(payload.budget_usd * weight, 2),
                    "max_position_pct": round(payload.max_position_pct, 4),
                    "auto_rebalance": True,
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                }
            )
        self._clear_live_caches()
        return self.get_social_trading_snapshot(user_slug, repository)

    def execute_social_managed_paper(
        self,
        user_slug: str,
        payload: SocialManagedPaperExecutionRequest,
    ) -> SocialManagedPaperExecutionResult:
        repository = BotSocietyRepository(self.database)
        if not repository.get_user(user_slug):
            raise ValueError(f"User {user_slug} is not available")

        latest_assets = {row["asset"]: row for row in repository.list_latest_market_snapshots()}
        closed_positions = self._sync_paper_positions(repository, user_slug)
        snapshot = self.get_paper_trading_snapshot(user_slug, repository=repository, latest_assets=latest_assets)
        allocations = [
            row
            for row in repository.list_social_trader_allocations(user_slug)
            if bool(row.get("is_active")) and str(row.get("mode")) == "managed_paper"
        ]
        if payload.trader_id:
            allocations = [row for row in allocations if int(row["trader_id"]) == payload.trader_id]

        messages: list[str] = []
        if not allocations:
            return SocialManagedPaperExecutionResult(
                evaluated_allocations=0,
                created_predictions=0,
                created_positions=0,
                closed_positions=closed_positions,
                skipped_signals=0,
                messages=["No active managed-paper social trader allocations were found."],
                snapshot=snapshot,
            )

        open_prediction_ids = {
            int(position["prediction_id"])
            for position in repository.list_paper_positions(user_slug)
        }
        existing_predictions = repository.list_predictions(bot_slug="social-momentum", limit=1000)
        prediction_by_signal_id: dict[int, dict] = {}
        for prediction in existing_predictions:
            for signal_id in self._extract_source_signal_ids(prediction):
                prediction_by_signal_id.setdefault(signal_id, prediction)

        candidates: list[tuple[float, dict, dict, dict]] = []
        skipped_signals = 0
        for allocation in allocations:
            trader_id = int(allocation["trader_id"])
            events = repository.list_social_trader_events(trader_id, limit=24)
            signal_external_ids = [f"social-signal-{event['external_id']}" for event in events]
            signals_by_external_id = {
                str(signal["external_id"]): signal
                for signal in repository.list_signals_by_external_ids(signal_external_ids)
            }
            for event in events:
                signal = signals_by_external_id.get(f"social-signal-{event['external_id']}")
                if not signal:
                    skipped_signals += 1
                    continue
                asset = str(signal["asset"])
                direction = "bullish" if float(signal.get("sentiment") or 0) > 0 else "bearish" if float(signal.get("sentiment") or 0) < 0 else "neutral"
                if direction == "neutral" or asset not in latest_assets:
                    skipped_signals += 1
                    continue
                confidence = max(float(event.get("confidence") or 0), min(0.95, abs(float(signal.get("sentiment") or 0))))
                if confidence < payload.min_confidence:
                    skipped_signals += 1
                    continue
                if int(signal["id"]) in prediction_by_signal_id and int(prediction_by_signal_id[int(signal["id"])]["id"]) in open_prediction_ids:
                    skipped_signals += 1
                    continue
                candidate_score = (
                    confidence * 0.55
                    + float(signal.get("source_quality_score") or 0.0) * 0.25
                    + float(signal.get("freshness_score") or 0.0) * 0.15
                    + float(event.get("engagement_score") or 0.0) * 0.05
                )
                candidates.append((candidate_score, allocation, event, signal))

        candidates.sort(key=lambda item: item[0], reverse=True)
        available_cash = snapshot.summary.cash_balance
        open_exposure = snapshot.summary.open_exposure
        max_open_exposure = self.settings.paper_starting_balance * 0.65
        created_predictions = 0
        created_positions = 0
        now = self._now()

        for _, allocation, event, signal in candidates[: payload.max_positions]:
            if available_cash <= 25 or open_exposure >= max_open_exposure:
                messages.append("Paper risk ceiling reached; remaining social signals were not executed.")
                break
            signal_id = int(signal["id"])
            prediction = prediction_by_signal_id.get(signal_id)
            asset = str(signal["asset"])
            direction = "bullish" if float(signal.get("sentiment") or 0) > 0 else "bearish"
            mark_price = float(latest_assets[asset]["price"])
            confidence = round(
                min(
                    0.88,
                    max(
                        payload.min_confidence,
                        abs(float(signal.get("sentiment") or 0)) * 0.72
                        + float(signal.get("source_quality_score") or 0.0) * 0.2
                        + float(signal.get("freshness_score") or 0.0) * 0.08,
                    ),
                ),
                2,
            )
            trader_name = str(allocation.get("trader_name") or allocation.get("trader_slug") or "Social trader")
            if not prediction:
                prediction_id = repository.create_prediction(
                    {
                        "bot_slug": "social-momentum",
                        "asset": asset,
                        "direction": direction,
                        "confidence": confidence,
                        "horizon_days": 3,
                        "horizon_label": "3 days",
                        "thesis": (
                            f"Managed paper copy of {trader_name}: {signal['title']}. "
                            f"{str(signal.get('summary') or '')[:260]}"
                        ),
                        "trigger_conditions": (
                            f"Execute only while {trader_name}'s latest public creator signal remains fresh, "
                            f"confidence stays above {payload.min_confidence:.0%}, and paper allocation caps are respected."
                        ),
                        "invalidation": (
                            f"Pause if the creator reverses the thesis, {asset} loses live mark-price support, "
                            "or the social-manager allocation cap is reached."
                        ),
                        "source_signal_ids": json.dumps([signal_id]),
                        "published_at": now,
                        "status": "pending",
                        "start_price": mark_price,
                    }
                )
                prediction = repository.get_prediction(prediction_id)
                if not prediction:
                    skipped_signals += 1
                    continue
                prediction_by_signal_id[signal_id] = prediction
                created_predictions += 1

            prediction_id = int(prediction["id"])
            if prediction_id in open_prediction_ids or repository.get_paper_position_for_prediction(user_slug, prediction_id):
                skipped_signals += 1
                continue

            allocation_limit = float(allocation.get("allocation_limit_usd") or 0)
            max_position_pct = float(allocation.get("max_position_pct") or 0.12)
            max_position_notional = max(0.0, allocation_limit * max_position_pct)
            target_allocation = min(
                max_position_notional,
                self._paper_trade_allocation(available_cash, confidence),
                available_cash,
                max(0.0, max_open_exposure - open_exposure),
            )
            fee_rate = (self.settings.paper_trade_fee_bps + self.settings.paper_trade_slippage_bps) / 10000
            fee_cost = target_allocation * fee_rate
            if target_allocation + fee_cost > available_cash:
                target_allocation = max(0.0, available_cash / (1 + fee_rate))
                fee_cost = target_allocation * fee_rate
            if target_allocation < 25:
                skipped_signals += 1
                continue

            quantity = target_allocation / mark_price if mark_price else 0.0
            inserted = repository.create_paper_position(
                {
                    "user_slug": user_slug,
                    "prediction_id": prediction_id,
                    "bot_slug": "social-momentum",
                    "asset": asset,
                    "direction": direction,
                    "confidence": confidence,
                    "allocation_usd": round(target_allocation, 2),
                    "quantity": round(quantity, 8),
                    "entry_price": mark_price,
                    "fees_paid": round(fee_cost, 2),
                    "slippage_bps": self.settings.paper_trade_slippage_bps,
                    "status": "open",
                    "opened_at": now,
                    "closed_at": None,
                    "exit_price": None,
                    "realized_pnl": None,
                }
            )
            if inserted:
                created_positions += 1
                open_prediction_ids.add(prediction_id)
                available_cash -= target_allocation + fee_cost
                open_exposure += target_allocation
                messages.append(
                    f"Opened managed-paper {direction} {asset} from {trader_name} with {target_allocation:,.2f} USD notional."
                )

        self._clear_live_caches()
        return SocialManagedPaperExecutionResult(
            evaluated_allocations=len(allocations),
            created_predictions=created_predictions,
            created_positions=created_positions,
            closed_positions=closed_positions,
            skipped_signals=skipped_signals,
            messages=messages or ["No eligible fresh social signals passed risk and duplicate checks."],
            snapshot=self.get_paper_trading_snapshot(user_slug, repository=repository, latest_assets=latest_assets),
        )

    def create_strategy(self, user_slug: str, payload: StrategyCreateRequest) -> StrategyView:
        repository = BotSocietyRepository(self.database)
        if not repository.get_user(user_slug):
            raise ValueError(f"User {user_slug} is not available")

        now = self._now()
        strategy_id = repository.create_strategy(
            {
                "user_slug": user_slug,
                "name": payload.name,
                "description": payload.description,
                "config_json": self._encode_json_payload(payload.config.model_dump(mode="json")),
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            }
        )
        row = repository.get_strategy(user_slug, strategy_id)
        if not row:
            raise ValueError("Unable to create strategy")
        return self._strategy_view_from_row(row)

    def list_strategies(self, user_slug: str) -> list[StrategyView]:
        repository = BotSocietyRepository(self.database)
        if not repository.get_user(user_slug):
            raise ValueError(f"User {user_slug} is not available")
        return [self._strategy_view_from_row(row) for row in repository.list_strategies(user_slug)]

    def get_strategy(self, user_slug: str, strategy_id: int) -> StrategyView:
        repository = BotSocietyRepository(self.database)
        row = repository.get_strategy(user_slug, strategy_id)
        if not row:
            raise ValueError("Strategy not found")
        return self._strategy_view_from_row(row)

    def update_strategy(self, user_slug: str, strategy_id: int, payload: StrategyUpdateRequest) -> StrategyView:
        repository = BotSocietyRepository(self.database)
        existing = repository.get_strategy(user_slug, strategy_id, include_inactive=True)
        if not existing:
            raise ValueError("Strategy not found")

        updates: dict[str, object | None] = {}
        if "name" in payload.model_fields_set and payload.name is not None:
            updates["name"] = payload.name
        if "description" in payload.model_fields_set:
            updates["description"] = payload.description
        if payload.config is not None:
            updates["config_json"] = self._encode_json_payload(payload.config.model_dump(mode="json"))
        if payload.is_active is not None:
            updates["is_active"] = payload.is_active

        if updates:
            updates["updated_at"] = self._now()
            repository.update_strategy(user_slug, strategy_id, updates)

        row = repository.get_strategy(user_slug, strategy_id, include_inactive=True)
        if not row:
            raise ValueError("Strategy not found")
        return self._strategy_view_from_row(row)

    def delete_strategy(self, user_slug: str, strategy_id: int) -> StrategyView:
        repository = BotSocietyRepository(self.database)
        existing = repository.get_strategy(user_slug, strategy_id)
        if not existing:
            raise ValueError("Strategy not found")
        repository.update_strategy(user_slug, strategy_id, {"is_active": False, "updated_at": self._now()})
        row = repository.get_strategy(user_slug, strategy_id, include_inactive=True)
        if not row:
            raise ValueError("Strategy not found")
        return self._strategy_view_from_row(row)

    def run_strategy_backtest(
        self,
        user_slug: str,
        strategy_id: int,
        payload: StrategyBacktestRequest | None = None,
    ) -> BacktestRunView:
        repository = BotSocietyRepository(self.database)
        strategy = repository.get_strategy(user_slug, strategy_id)
        if not strategy:
            raise ValueError("Strategy not found")

        config_payload = self._decode_json_payload(strategy.get("config_json"))
        if not isinstance(config_payload, dict):
            raise ValueError("Saved strategy config is invalid")
        simulation_payload = payload.config_override if payload and payload.config_override else SimulationRequest(**config_payload)
        started_at = self._now()
        try:
            result = self.run_simulation(simulation_payload)
            completed_at = self._now()
            selected = result.selected_result
            rank = next(
                (index + 1 for index, item in enumerate(result.leaderboard) if item.strategy_id == selected.strategy_id),
                None,
            )
            summary: dict[str, object] = {
                "strategy_name": strategy["name"],
                "asset": result.asset,
                "strategy_id": selected.strategy_id,
                "selected_label": selected.label,
                "lookback_years": result.requested_lookback_years,
                "actual_years_covered": result.actual_years_covered,
                "data_source": result.data_source,
                "history_points": result.history_points,
                "rank": rank,
                "total_return": selected.total_return,
                "benchmark_total_return": result.benchmark_total_return,
                "cagr": selected.cagr,
                "max_drawdown": selected.max_drawdown,
                "sharpe_ratio": selected.sharpe_ratio,
                "win_rate": selected.win_rate,
                "trade_count": selected.trade_count,
                "final_equity": selected.final_equity,
                "beat_benchmark": selected.total_return > result.benchmark_total_return,
            }
            run_id = repository.create_backtest_run(
                {
                    "strategy_id": strategy_id,
                    "user_slug": user_slug,
                    "asset": result.asset,
                    "strategy_key": selected.strategy_id,
                    "lookback_years": result.requested_lookback_years,
                    "status": "complete",
                    "started_at": started_at,
                    "completed_at": completed_at,
                    "summary_json": self._encode_json_payload(summary),
                    "result_json": self._encode_json_payload(result.model_dump(mode="json")),
                    "error_message": None,
                }
            )
        except Exception as exc:
            completed_at = self._now()
            run_id = repository.create_backtest_run(
                {
                    "strategy_id": strategy_id,
                    "user_slug": user_slug,
                    "asset": simulation_payload.asset,
                    "strategy_key": simulation_payload.strategy_id,
                    "lookback_years": simulation_payload.lookback_years,
                    "status": "failed",
                    "started_at": started_at,
                    "completed_at": completed_at,
                    "summary_json": self._encode_json_payload(
                        {
                            "strategy_name": strategy["name"],
                            "asset": simulation_payload.asset,
                            "strategy_id": simulation_payload.strategy_id,
                            "lookback_years": simulation_payload.lookback_years,
                        }
                    ),
                    "result_json": None,
                    "error_message": str(exc),
                }
            )
            raise ValueError(f"Backtest failed and was recorded as run {run_id}: {exc}") from exc

        row = repository.get_backtest_run(user_slug, run_id)
        if not row:
            raise ValueError("Unable to record backtest run")
        return self._backtest_run_view_from_row(row)

    def list_backtest_runs(
        self,
        user_slug: str,
        *,
        strategy_id: int | None = None,
        limit: int = 20,
    ) -> list[BacktestRunView]:
        repository = BotSocietyRepository(self.database)
        if not repository.get_user(user_slug):
            raise ValueError(f"User {user_slug} is not available")
        return [
            self._backtest_run_view_from_row(row)
            for row in repository.list_backtest_runs(user_slug, strategy_id=strategy_id, limit=limit)
        ]

    def get_backtest_run(self, user_slug: str, run_id: int) -> BacktestRunView:
        repository = BotSocietyRepository(self.database)
        row = repository.get_backtest_run(user_slug, run_id)
        if not row:
            raise ValueError("Backtest run not found")
        return self._backtest_run_view_from_row(row)

    def get_billing_snapshot(self, user_slug: str, *, can_manage: bool | None = None) -> BillingSnapshot:
        repository = BotSocietyRepository(self.database)
        user = repository.get_user(user_slug)
        if not user:
            raise ValueError(f"User {user_slug} is not available")

        plans = self._billing_plan_catalog()
        configured_plan_count = sum(plan.configured for plan in plans)
        customer = repository.get_billing_customer(user_slug)
        subscription = repository.get_billing_subscription(user_slug)
        provider = self.settings.fiat_billing_provider
        can_manage_workspace = (not bool(user.get("is_demo_user"))) if can_manage is None else can_manage

        warnings: list[str] = []
        if provider != "stripe":
            warnings.append("Fiat billing provider is not configured yet.")
        else:
            if not self.settings.stripe_publishable_key:
                warnings.append("Stripe publishable key is missing.")
            if not self.settings.stripe_secret_key:
                warnings.append("Stripe secret key is missing.")
            if not configured_plan_count:
                warnings.append("No Stripe price IDs are configured yet.")
            if self.settings.stripe_customer_portal_enabled and not customer:
                warnings.append("Customer portal will activate after the first paid checkout creates a Stripe customer.")

        subscription_status = str(subscription["status"]) if subscription else None
        active_subscription = subscription_status in {"trialing", "active", "past_due", "unpaid"}
        plan_key = subscription.get("plan_key") if subscription else None
        if not plan_key and subscription and subscription.get("price_id"):
            plan_key = self._plan_key_for_price_id(str(subscription["price_id"]))

        summary = (
            "Sign in with a personal workspace to launch Stripe Checkout and manage a paid plan."
            if not can_manage_workspace
            else self._billing_summary_text(
                configured=provider == "stripe" and bool(self.settings.stripe_secret_key) and bool(self.settings.stripe_publishable_key),
                configured_plan_count=configured_plan_count,
                active_subscription=active_subscription,
                plan_key=plan_key,
                subscription_status=subscription_status,
            )
        )

        return BillingSnapshot(
            provider=provider,
            configured=provider == "stripe" and bool(self.settings.stripe_secret_key) and bool(self.settings.stripe_publishable_key),
            checkout_ready=can_manage_workspace and provider == "stripe" and bool(self.settings.stripe_secret_key) and configured_plan_count > 0,
            portal_ready=can_manage_workspace and provider == "stripe" and bool(self.settings.stripe_secret_key) and bool(customer) and self.settings.stripe_customer_portal_enabled,
            can_manage=can_manage_workspace,
            tier=str(user["tier"]),
            summary=summary,
            warnings=warnings,
            available_plans=plans,
            publishable_key=self.settings.stripe_publishable_key,
            contact_email=str(user["email"]),
            customer_state="linked" if customer else "new",
            subscription_status=subscription_status,
            plan_key=plan_key,
            plan_label=self._plan_label(plan_key),
            current_period_end=str(subscription["current_period_end"]) if subscription and subscription.get("current_period_end") else None,
            cancel_at_period_end=bool(subscription["cancel_at_period_end"]) if subscription else False,
            has_active_subscription=active_subscription,
            last_event_type=str(subscription["last_event_type"]) if subscription and subscription.get("last_event_type") else None,
            provider_customer_id=self._mask_identifier(str(customer["provider_customer_id"])) if customer and customer.get("provider_customer_id") else None,
            provider_subscription_id=self._mask_identifier(str(subscription["provider_subscription_id"])) if subscription and subscription.get("provider_subscription_id") else None,
        )

    def create_billing_checkout_session(
        self,
        user_slug: str,
        payload: BillingCheckoutSessionRequest,
        *,
        base_url: str,
    ) -> BillingSessionLaunch:
        repository = BotSocietyRepository(self.database)
        user = repository.get_user(user_slug)
        if not user:
            raise ValueError(f"User {user_slug} is not available")
        if bool(user.get("is_demo_user")):
            raise ValueError("Sign in with a personal workspace before starting checkout")
        if self.settings.fiat_billing_provider != "stripe":
            raise ValueError("Stripe billing is not configured for this deployment")

        plan = next((item for item in self._billing_plan_catalog() if item.key == payload.plan_key), None)
        if not plan or not plan.configured or not plan.price_id:
            raise ValueError(f"The {payload.plan_key} plan is not configured yet")

        customer = repository.get_billing_customer(user_slug)
        client = self._stripe_client()
        try:
            session = client.create_checkout_session(
                price_id=plan.price_id,
                success_url=f"{base_url}{payload.success_path}",
                cancel_url=f"{base_url}{payload.cancel_path}",
                customer_id=str(customer["provider_customer_id"]) if customer and customer.get("provider_customer_id") else None,
                customer_email=str(user["email"]),
                user_slug=user_slug,
                plan_key=payload.plan_key,
            )
        except StripeClientError as exc:
            raise ValueError(str(exc)) from exc
        now = self._now()
        customer_id = str(session.get("customer") or "") or None
        if customer_id:
            repository.upsert_billing_customer(
                {
                    "user_slug": user_slug,
                    "provider": "stripe",
                    "provider_customer_id": customer_id,
                    "email": user["email"],
                    "created_at": customer["created_at"] if customer else now,
                    "updated_at": now,
                }
            )

        existing = repository.get_billing_subscription(user_slug)
        repository.upsert_billing_subscription(
            {
                "user_slug": user_slug,
                "provider": "stripe",
                "provider_customer_id": customer_id or (existing.get("provider_customer_id") if existing else None),
                "provider_subscription_id": str(session.get("subscription") or "") or (existing.get("provider_subscription_id") if existing else None),
                "provider_checkout_session_id": str(session.get("id") or ""),
                "status": "checkout_created",
                "plan_key": payload.plan_key,
                "price_id": plan.price_id,
                "current_period_end": existing.get("current_period_end") if existing else None,
                "cancel_at_period_end": bool(existing.get("cancel_at_period_end")) if existing else False,
                "last_event_id": existing.get("last_event_id") if existing else None,
                "last_event_type": "checkout.session.created",
                "created_at": existing.get("created_at") if existing else now,
                "updated_at": now,
            }
        )

        return BillingSessionLaunch(
            provider="stripe",
            url=str(session["url"]),
            session_id=str(session["id"]),
            plan_key=payload.plan_key,
        )

    def create_billing_portal_session(
        self,
        user_slug: str,
        payload: BillingPortalSessionRequest,
        *,
        base_url: str,
    ) -> BillingSessionLaunch:
        if self.settings.fiat_billing_provider != "stripe":
            raise ValueError("Stripe billing is not configured for this deployment")
        if not self.settings.stripe_customer_portal_enabled:
            raise ValueError("Stripe customer portal is not enabled yet")

        repository = BotSocietyRepository(self.database)
        customer = repository.get_billing_customer(user_slug)
        if not customer or not customer.get("provider_customer_id"):
            raise ValueError("No Stripe customer is linked to this workspace yet")

        try:
            session = self._stripe_client().create_customer_portal_session(
                customer_id=str(customer["provider_customer_id"]),
                return_url=f"{base_url}{payload.return_path}",
            )
        except StripeClientError as exc:
            raise ValueError(str(exc)) from exc
        return BillingSessionLaunch(
            provider="stripe",
            url=str(session["url"]),
            session_id=str(session.get("id") or ""),
            plan_key=None,
        )

    def handle_stripe_webhook(self, payload: bytes, signature_header: str | None) -> BillingWebhookAck:
        if self.settings.fiat_billing_provider != "stripe":
            raise ValueError("Stripe billing is not configured for this deployment")

        try:
            event = self._stripe_client().verify_webhook(payload, signature_header or "")
        except StripeSignatureError as exc:
            raise ValueError(str(exc)) from exc
        event_id = str(event.get("id") or "").strip()
        event_type = str(event.get("type") or "").strip()
        if not event_id or not event_type:
            raise ValueError("Stripe webhook payload is missing event metadata")

        repository = BotSocietyRepository(self.database)
        now = self._now()
        inserted = repository.create_billing_event(
            {
                "provider": "stripe",
                "provider_event_id": event_id,
                "event_type": event_type,
                "user_slug": None,
                "provider_customer_id": None,
                "provider_subscription_id": None,
                "status": "received",
                "payload_json": json.dumps(event, separators=(",", ":"), sort_keys=True),
                "received_at": now,
                "processed_at": None,
            }
        )
        if not inserted:
            return BillingWebhookAck(duplicate=True, event_type=event_type, status="duplicate")

        try:
            event_context = self._apply_stripe_event(repository, event, event_id=event_id, event_type=event_type)
        except Exception:
            repository.update_billing_event(
                event_id,
                {
                    "status": "failed",
                    "processed_at": self._now(),
                },
            )
            raise

        repository.update_billing_event(
            event_id,
            {
                "status": "processed",
                "processed_at": self._now(),
                **event_context,
            },
        )
        return BillingWebhookAck(event_type=event_type, status="processed")

    def get_summary(
        self,
        user_slug: str | None = None,
        *,
        repository: BotSocietyRepository | None = None,
        bot_summaries: list[BotSummary] | None = None,
        predictions: list[dict] | None = None,
        assets: list[str] | None = None,
        signals: list[dict] | None = None,
        latest_run: dict | None = None,
    ) -> Summary:
        active_repository = repository or BotSocietyRepository(self.database)
        bots = bot_summaries or self._build_bot_summaries(active_repository, user_slug)
        predictions = predictions if predictions is not None else active_repository.list_predictions(limit=500)
        assets = assets if assets is not None else active_repository.list_assets()
        signals = signals if signals is not None else active_repository.list_recent_signals(limit=100)
        latest_run = latest_run if latest_run is not None else active_repository.get_latest_pipeline_run()
        latest_signal_time = parse_timestamp(signals[0]["observed_at"]) if signals else None
        signals_last_24h = len(signals) if signals is not None else (
            active_repository.count_signals_since(to_timestamp(latest_signal_time.replace(hour=0, minute=0, second=0)))
            if latest_signal_time
            else 0
        )
        calibrations = [bot.calibration for bot in bots] or [0.0]
        scores = [bot.score for bot in bots] or [0.0]
        return Summary(
            active_bots=len(bots),
            tracked_assets=len(assets),
            total_predictions=len(predictions),
            scored_predictions=sum(1 for prediction in predictions if prediction["status"] == "scored"),
            pending_predictions=sum(1 for prediction in predictions if prediction["status"] == "pending"),
            average_bot_score=round(mean(scores), 2),
            median_calibration=round(median(calibrations), 3),
            signals_last_24h=signals_last_24h,
            last_cycle_status=latest_run["status"] if latest_run else None,
            last_cycle_at=latest_run["completed_at"] if latest_run else None,
        )

    def get_assets(self) -> list[AssetSnapshot]:
        if self._cache_is_fresh(self.assets_cache, ttl_seconds=300):
            return self.assets_cache[1]
        repository = BotSocietyRepository(self.database)
        assets = [self._to_asset_model(row) for row in repository.list_latest_market_snapshots()]
        self.assets_cache = (datetime.now(timezone.utc), assets)
        return assets

    def get_asset_history(self, asset: str) -> AssetHistoryEnvelope:
        repository = BotSocietyRepository(self.database)
        rows = repository.list_market_history(asset.upper())
        if not rows:
            raise ValueError(f"Unknown asset: {asset.upper()}")
        return AssetHistoryEnvelope(
            asset=asset.upper(),
            points=[AssetHistoryPoint(time=row["as_of"], value=float(row["price"])) for row in rows],
        )

    def get_macro_snapshot(self, repository: BotSocietyRepository | None = None) -> MacroSnapshot:
        if self._cache_is_fresh(self.macro_snapshot_cache, ttl_seconds=300):
            return self.macro_snapshot_cache[1]

        active_repository = repository or BotSocietyRepository(self.database)
        latest_rows = active_repository.list_latest_macro_snapshots()
        series = []
        for row in latest_rows:
            history_rows = active_repository.list_macro_history(str(row["series_id"]), limit=180)
            series.append(
                MacroSeriesSnapshot(
                    series_id=row["series_id"],
                    label=row["label"],
                    unit=row["unit"],
                    latest_value=float(row["value"]),
                    change_percent=float(row["change_percent"]),
                    signal_bias=float(row["signal_bias"]),
                    regime_label=row["regime_label"],
                    source=row["source"],
                    observed_at=row["observation_date"],
                    history=[
                        MacroObservationPoint(time=history_row["observation_date"], value=float(history_row["value"]))
                        for history_row in history_rows
                    ],
                )
            )

        posture_score = mean(item.signal_bias for item in series) if series else 0.0
        posture = "Macro supportive" if posture_score >= 0.18 else ("Macro restrictive" if posture_score <= -0.18 else "Macro balanced")
        strongest = sorted(series, key=lambda item: abs(item.signal_bias), reverse=True)[:2]
        summary = (
            "Watching "
            + ", ".join(
                f"{item.label} ({'supportive' if item.signal_bias >= 0 else 'restrictive'})" for item in strongest
            )
            if strongest
            else "Macro provider is online but no series have been hydrated yet."
        )
        snapshot = MacroSnapshot(
            generated_at=self._now(),
            posture=posture,
            summary=summary,
            series=series,
        )
        self.macro_snapshot_cache = (datetime.now(timezone.utc), snapshot)
        return snapshot

    def get_signals(self, limit: int = 12) -> list[SignalView]:
        repository = BotSocietyRepository(self.database)
        return [self._to_signal_model(row) for row in repository.list_recent_signals(limit=limit)]

    def get_predictions(self, limit: int = 20, status: str | None = None) -> list[PredictionView]:
        repository = BotSocietyRepository(self.database)
        return self._build_prediction_views(repository, repository.list_predictions(limit=limit, status=status))

    def get_leaderboard(self, user_slug: str | None = None) -> list[BotSummary]:
        cache_key = user_slug or self.settings.default_user_slug
        cached = self.leaderboard_cache.get(cache_key)
        if self._cache_is_fresh(cached, ttl_seconds=300):
            return cached[1]
        repository = BotSocietyRepository(self.database)
        leaderboard = self._build_bot_summaries(repository, user_slug)
        self.leaderboard_cache[cache_key] = (datetime.now(timezone.utc), leaderboard)
        return leaderboard

    def get_bot_detail(self, slug: str, user_slug: str | None = None) -> BotDetail | None:
        repository = BotSocietyRepository(self.database)
        summaries = self._build_bot_summaries(repository, user_slug)
        summary = next((bot for bot in summaries if bot.slug == slug), None)
        if not summary:
            return None
        recent_predictions = self._build_prediction_views(repository, repository.list_predictions(bot_slug=slug, limit=8))
        return BotDetail(**summary.model_dump(), recent_predictions=recent_predictions)

    def get_paper_trading_snapshot(
        self,
        user_slug: str,
        *,
        repository: BotSocietyRepository | None = None,
        latest_assets: dict[str, dict] | None = None,
    ) -> PaperTradingSnapshot:
        active_repository = repository or BotSocietyRepository(self.database)
        closed_positions = self._sync_paper_positions(active_repository, user_slug)
        positions = active_repository.list_paper_positions(user_slug)
        latest_assets = latest_assets or {
            row["asset"]: row for row in active_repository.list_latest_market_snapshots()
        }
        views: list[PaperPositionView] = []

        for row in positions:
            current_price = float(latest_assets.get(row["asset"], {}).get("price") or row.get("exit_price") or row["entry_price"])
            unrealized_pnl = 0.0
            if row["status"] == "open":
                unrealized_pnl = self._position_pnl(
                    direction=str(row["direction"]),
                    quantity=float(row["quantity"]),
                    entry_price=float(row["entry_price"]),
                    mark_price=current_price,
                )
            views.append(
                PaperPositionView(
                    id=int(row["id"]),
                    prediction_id=int(row["prediction_id"]),
                    bot_slug=row["bot_slug"],
                    bot_name=row.get("bot_name") or row["bot_slug"],
                    asset=row["asset"],
                    direction=row["direction"],
                    confidence=float(row["confidence"]),
                    status=row["status"],
                    opened_at=row["opened_at"],
                    closed_at=row.get("closed_at"),
                    allocation_usd=float(row["allocation_usd"]),
                    quantity=float(row["quantity"]),
                    entry_price=float(row["entry_price"]),
                    current_price=current_price,
                    exit_price=float(row["exit_price"]) if row.get("exit_price") is not None else None,
                    fees_paid=float(row.get("fees_paid") or 0.0),
                    unrealized_pnl=round(unrealized_pnl, 2),
                    realized_pnl=round(float(row["realized_pnl"]), 2) if row.get("realized_pnl") is not None else None,
                )
            )

        open_views = [view for view in views if view.status == "open"]
        closed_views = [view for view in views if view.status == "closed"]
        realized_pnl = sum(view.realized_pnl or 0.0 for view in closed_views)
        unrealized_pnl = sum(view.unrealized_pnl for view in open_views)
        open_exposure = sum(view.allocation_usd for view in open_views)
        cash_balance = self.settings.paper_starting_balance
        cash_balance -= sum(view.allocation_usd + view.fees_paid for view in open_views)
        cash_balance -= sum(view.fees_paid for view in closed_views)
        cash_balance += sum(view.allocation_usd + (view.realized_pnl or 0.0) for view in closed_views)
        equity = cash_balance + open_exposure + unrealized_pnl
        win_rate = (
            sum(1 for view in closed_views if (view.realized_pnl or 0.0) > 0) / len(closed_views)
            if closed_views
            else 0.0
        )
        summary = PaperPortfolioSummary(
            starting_balance=round(self.settings.paper_starting_balance, 2),
            cash_balance=round(cash_balance, 2),
            open_exposure=round(open_exposure, 2),
            equity=round(equity, 2),
            realized_pnl=round(realized_pnl, 2),
            unrealized_pnl=round(unrealized_pnl, 2),
            total_return=round(((equity - self.settings.paper_starting_balance) / self.settings.paper_starting_balance), 6),
            win_rate=round(win_rate, 3),
            open_positions=len(open_views),
            closed_positions=len(closed_views),
        )
        return PaperTradingSnapshot(generated_at=self._now(), summary=summary, positions=views[:12])

    def simulate_paper_trading(self, user_slug: str, limit: int = 3) -> PaperSimulationResult:
        repository = BotSocietyRepository(self.database)
        closed_positions = self._sync_paper_positions(repository, user_slug)
        snapshot_before = self.get_paper_trading_snapshot(user_slug)
        existing_prediction_ids = {position.prediction_id for position in snapshot_before.positions}
        latest_assets = {row["asset"]: row for row in repository.list_latest_market_snapshots()}
        pending_predictions = [
            row
            for row in repository.list_predictions(status="pending", limit=50)
            if int(row["id"]) not in existing_prediction_ids and row["asset"] in latest_assets
        ]
        available_cash = snapshot_before.summary.cash_balance
        created_positions = 0

        for prediction in sorted(pending_predictions, key=lambda row: float(row["confidence"]), reverse=True)[:limit]:
            entry_price = float(latest_assets[prediction["asset"]]["price"])
            allocation = self._paper_trade_allocation(available_cash, float(prediction["confidence"]))
            if allocation <= 0:
                break
            fee_cost = allocation * ((self.settings.paper_trade_fee_bps + self.settings.paper_trade_slippage_bps) / 10000)
            if allocation + fee_cost > available_cash:
                allocation = max(0.0, available_cash - fee_cost)
            if allocation <= 0:
                break
            quantity = allocation / entry_price if entry_price else 0.0
            inserted = repository.create_paper_position(
                {
                    "user_slug": user_slug,
                    "prediction_id": int(prediction["id"]),
                    "bot_slug": prediction["bot_slug"],
                    "asset": prediction["asset"],
                    "direction": prediction["direction"],
                    "confidence": float(prediction["confidence"]),
                    "allocation_usd": round(allocation, 2),
                    "quantity": round(quantity, 8),
                    "entry_price": entry_price,
                    "fees_paid": round(fee_cost, 2),
                    "slippage_bps": self.settings.paper_trade_slippage_bps,
                    "status": "open",
                    "opened_at": self._now(),
                    "closed_at": None,
                    "exit_price": None,
                    "realized_pnl": None,
                }
            )
            if inserted:
                created_positions += 1
                available_cash -= allocation + fee_cost

        self._clear_live_caches()
        return PaperSimulationResult(
            created_positions=created_positions,
            closed_positions=closed_positions,
            snapshot=self.get_paper_trading_snapshot(user_slug),
        )

    def place_trading_order(self, user_slug: str, payload: TradingOrderRequest) -> TradingOrderView:
        repository = BotSocietyRepository(self.database)
        user = repository.get_user(user_slug)
        if not user:
            raise ValueError(f"User {user_slug} is not available")
        if not payload.is_paper or payload.venue not in {"paper", "internal"}:
            raise ValueError("Live execution is disabled. Use venue=paper and is_paper=true.")
        if payload.order_type != "market":
            raise ValueError("The current paper engine only accepts market orders")
        if payload.side not in {"buy", "long"}:
            raise ValueError("The current paper engine only supports buy/long orders")

        latest_assets = {row["asset"]: row for row in repository.list_latest_market_snapshots()}
        if payload.asset not in latest_assets:
            raise ValueError(f"Unknown or unsupported paper-trading asset: {payload.asset}")
        mark_price = float(latest_assets[payload.asset]["price"])
        if mark_price <= 0:
            raise ValueError(f"Invalid market price for {payload.asset}")

        slippage_multiplier = 1 + (self.settings.paper_trade_slippage_bps / 10000)
        fill_price = round(mark_price * slippage_multiplier, 8)
        quantity = float(payload.quantity) if payload.quantity is not None else float(payload.notional_usd or 0.0) / fill_price
        requested_notional = quantity * fill_price
        if requested_notional <= 0:
            raise ValueError("Order notional must be greater than zero")

        snapshot = self.get_paper_trading_snapshot(user_slug)
        fee = requested_notional * (self.settings.paper_trade_fee_bps / 10000)
        total_cash_required = requested_notional + fee
        max_single_order = self.settings.paper_starting_balance * 0.25
        max_open_exposure = self.settings.paper_starting_balance * 0.65
        daily_loss_limit = self.settings.paper_starting_balance * -0.1

        if requested_notional > max_single_order:
            raise ValueError(f"Paper order exceeds max single-order notional of {max_single_order:.2f} USD")
        if total_cash_required > snapshot.summary.cash_balance:
            raise ValueError("Insufficient paper cash for order notional plus fees")
        if snapshot.summary.open_exposure + requested_notional > max_open_exposure:
            raise ValueError(f"Paper order would exceed max open exposure of {max_open_exposure:.2f} USD")
        if snapshot.summary.realized_pnl <= daily_loss_limit:
            raise ValueError("Daily paper loss limit reached; new orders are suspended")

        notional = quantity * fill_price
        fee = notional * (self.settings.paper_trade_fee_bps / 10000)
        now = self._now()
        metadata = {
            "execution_mode": "internal-paper",
            "reference_price": mark_price,
            "slippage_bps": self.settings.paper_trade_slippage_bps,
            "fee_bps": self.settings.paper_trade_fee_bps,
            "risk_limits": {
                "max_single_order_usd": round(max_single_order, 2),
                "max_open_exposure_usd": round(max_open_exposure, 2),
                "daily_loss_limit_usd": round(daily_loss_limit, 2),
            },
            "client_order_id": payload.client_order_id,
        }
        order_id = repository.create_order(
            {
                "user_slug": user_slug,
                "prediction_id": payload.prediction_id,
                "venue": "paper",
                "asset": payload.asset,
                "side": payload.side,
                "order_type": payload.order_type,
                "is_paper": True,
                "quantity": round(quantity, 8),
                "notional_usd": round(notional, 2),
                "price": None,
                "status": "filled",
                "filled_quantity": round(quantity, 8),
                "avg_fill_price": fill_price,
                "fee": round(fee, 2),
                "fee_currency": "USD",
                "exchange_order_id": f"paper-{now.replace(':', '').replace('-', '').replace('Z', '')}-{payload.asset.lower()}",
                "rejection_reason": None,
                "submitted_at": now,
                "filled_at": now,
                "cancelled_at": None,
                "metadata_json": self._encode_json_payload(metadata),
            }
        )
        row = repository.get_order(user_slug, order_id)
        if not row:
            raise ValueError("Unable to record paper order")
        self._clear_live_caches()
        return self._trading_order_view_from_row(row)

    def list_trading_orders(
        self,
        user_slug: str,
        *,
        status: str | None = None,
        limit: int = 50,
    ) -> list[TradingOrderView]:
        repository = BotSocietyRepository(self.database)
        if not repository.get_user(user_slug):
            raise ValueError(f"User {user_slug} is not available")
        return [self._trading_order_view_from_row(row) for row in repository.list_orders(user_slug, status=status, limit=limit)]

    def get_trading_order(self, user_slug: str, order_id: int) -> TradingOrderView:
        repository = BotSocietyRepository(self.database)
        row = repository.get_order(user_slug, order_id)
        if not row:
            raise ValueError("Order not found")
        return self._trading_order_view_from_row(row)

    def cancel_trading_order(self, user_slug: str, order_id: int) -> TradingOrderView:
        repository = BotSocietyRepository(self.database)
        row = repository.get_order(user_slug, order_id)
        if not row:
            raise ValueError("Order not found")
        if row["status"] != "open":
            raise ValueError("Only open paper orders can be cancelled")
        repository.update_order(user_slug, order_id, {"status": "cancelled", "cancelled_at": self._now()})
        updated = repository.get_order(user_slug, order_id)
        if not updated:
            raise ValueError("Order not found")
        return self._trading_order_view_from_row(updated)

    def get_paper_venues(self) -> PaperVenuesSnapshot:
        polysandbox_configured = bool(self.settings.polysandbox_api_key and self.settings.polysandbox_sandbox_id)
        kalshi_demo_configured = bool(self.settings.kalshi_demo_key_id and self.settings.kalshi_demo_private_key_path)
        hyperliquid_testnet_configured = bool(
            self.settings.hyperliquid_testnet_wallet_address and self.settings.hyperliquid_testnet_private_key
        )
        lorem_ipsum_enabled = bool(self.settings.lorem_ipsum_trade_enabled)
        ibkr_gateway_configured = self.settings.ibkr_connection_mode != "disabled" and (
            bool(self.settings.ibkr_tws_host and self.settings.ibkr_tws_port)
            if self.settings.ibkr_connection_mode == "tws_gateway"
            else bool(self.settings.ibkr_client_portal_base_url)
        )
        ibkr_account_configured = bool(self.settings.ibkr_account_id)
        ibkr_order_gate_open = bool(ibkr_gateway_configured and ibkr_account_configured and not self.settings.ibkr_read_only)
        ibkr_status = "ready" if ibkr_order_gate_open else ("watchlist" if ibkr_gateway_configured and ibkr_account_configured else "needs_credentials")
        ibkr_endpoint = (
            f"{self.settings.ibkr_tws_host}:{self.settings.ibkr_tws_port}"
            if self.settings.ibkr_connection_mode == "tws_gateway"
            else self.settings.ibkr_client_portal_base_url
            if self.settings.ibkr_connection_mode == "client_portal"
            else None
        )

        venues = [
            PaperVenueView(
                id="internal",
                name="Bot Society Internal Paper Ledger",
                category="Internal simulator",
                priority=1,
                status="ready",
                configured=True,
                live_capable=False,
                api_capable=True,
                manual_capable=False,
                historical_replay_capable=True,
                supported_markets=["BTC", "ETH", "SOL"],
                api_base_url="/api/paper-trading",
                app_url="/dashboard#paper-section",
                docs_url=None,
                capability_summary="Local paper positions tied directly to Bot Society prediction objects.",
                capabilities=[
                    PaperVenueCapability(label="Portfolio accounting", detail="Tracks cash, exposure, PnL, win rate, and open/closed positions."),
                    PaperVenueCapability(label="Bot attribution", detail="Every simulated position keeps the source bot and prediction id."),
                    PaperVenueCapability(label="Safe by default", detail="No external order endpoint or wallet is used."),
                ],
                setup_steps=[
                    "Open the dashboard paper trading card.",
                    "Run a pipeline cycle to create pending predictions.",
                    "Press Simulate Positions to allocate demo capital to the highest-confidence calls.",
                ],
                limitations=[
                    "Uses asset-level market prices, not full venue order-book microstructure.",
                    "No external fills, cancellations, or websocket execution loop yet.",
                ],
                env_keys=["BSM_PAPER_STARTING_BALANCE", "BSM_PAPER_TRADE_FEE_BPS", "BSM_PAPER_TRADE_SLIPPAGE_BPS"],
                next_action="Keep this as the baseline ledger while external paper venues are activated.",
                safety_note="This ledger cannot send real orders.",
                readiness_score=1.0,
            ),
            PaperVenueView(
                id="polysandbox",
                name="Polysandbox",
                category="Polymarket paper venue",
                priority=2,
                status="ready" if polysandbox_configured else "needs_credentials",
                configured=polysandbox_configured,
                live_capable=True,
                api_capable=True,
                manual_capable=True,
                historical_replay_capable=True,
                supported_markets=["Polymarket CLOB", "prediction markets", "crypto directionals", "weather markets"],
                api_base_url=self.settings.polysandbox_api_url,
                app_url=self.settings.polysandbox_app_url,
                docs_url=self.settings.polysandbox_docs_url,
                capability_summary="Best first external adapter for automated Polymarket-style paper orders.",
                capabilities=[
                    PaperVenueCapability(label="Live CLOB quotes", detail="Designed to price paper fills from live Polymarket order books."),
                    PaperVenueCapability(label="API parity", detail="REST API flow can be kept close to a later live CLOB integration."),
                    PaperVenueCapability(label="Agent-friendly", detail="Includes API and MCP-oriented workflows for bot testing."),
                ],
                setup_steps=[
                    "Create a Polysandbox account and sandbox.",
                    "Create a paper API key in the Polysandbox app.",
                    "Set BSM_PAPER_EXECUTION_PROVIDER=polysandbox, BSM_POLYSANDBOX_API_KEY, and BSM_POLYSANDBOX_SANDBOX_ID.",
                    "Run the adapter in paper-only mode before any live Polymarket work.",
                ],
                limitations=[
                    "Independent product, not affiliated with Polymarket.",
                    "Pricing, replay depth, and rate limits depend on the selected Polysandbox plan.",
                ],
                env_keys=[
                    "BSM_PAPER_EXECUTION_PROVIDER",
                    "BSM_POLYSANDBOX_API_URL",
                    "BSM_POLYSANDBOX_API_KEY",
                    "BSM_POLYSANDBOX_SANDBOX_ID",
                ],
                next_action=(
                    "Credentials are present. Build the order adapter next."
                    if polysandbox_configured
                    else "Create a free trial sandbox, then add API key and sandbox id to .env.local."
                ),
                safety_note="Use only paper API keys here. Never paste a funded wallet seed phrase into the platform.",
                readiness_score=0.92 if polysandbox_configured else 0.68,
            ),
            PaperVenueView(
                id="lorem_ipsum_trade",
                name="Lorem Ipsum Trade",
                category="Polymarket-compatible sandbox",
                priority=3,
                status="ready" if lorem_ipsum_enabled else "watchlist",
                configured=lorem_ipsum_enabled,
                live_capable=True,
                api_capable=True,
                manual_capable=True,
                historical_replay_capable=False,
                supported_markets=["Polymarket-style CLOB", "15-minute crypto up/down markets"],
                api_base_url=self.settings.lorem_ipsum_trade_clob_url,
                app_url=self.settings.lorem_ipsum_trade_app_url,
                docs_url="https://www.loremipsumtrade.com/",
                capability_summary="Drop-in CLOB-style sandbox for fast bot loops on short-horizon prediction markets.",
                capabilities=[
                    PaperVenueCapability(label="SDK-compatible endpoint", detail="Can be pointed at by Polymarket CLOB clients after changing the base URL."),
                    PaperVenueCapability(label="Order-book realism", detail="Focuses on spreads, partial fills, slippage, and thin liquidity."),
                    PaperVenueCapability(label="Agent testing", detail="Useful for rapid AI-agent policy comparison."),
                ],
                setup_steps=[
                    "Open the sandbox and connect a separate development wallet if required.",
                    "Set BSM_LOREM_IPSUM_TRADE_ENABLED=true after manual account verification.",
                    "Route only paper-sized synthetic orders through the CLOB URL.",
                ],
                limitations=[
                    "Focused on fast crypto binary markets, not broad prediction-market coverage.",
                    "Treat as a sandbox until API stability, auth, and limits are verified.",
                ],
                env_keys=[
                    "BSM_LOREM_IPSUM_TRADE_ENABLED",
                    "BSM_LOREM_IPSUM_TRADE_CLOB_URL",
                    "BSM_LOREM_IPSUM_TRADE_APP_URL",
                ],
                next_action=(
                    "Enabled for adapter experiments."
                    if lorem_ipsum_enabled
                    else "Keep on watchlist until account/API behavior is verified in a throwaway sandbox."
                ),
                safety_note="Connect only an empty development wallet if the sandbox requires wallet login.",
                readiness_score=0.82 if lorem_ipsum_enabled else 0.55,
            ),
            PaperVenueView(
                id="kalshi_demo",
                name="Kalshi Demo",
                category="Regulated prediction market demo",
                priority=4,
                status="ready" if kalshi_demo_configured else "needs_credentials",
                configured=kalshi_demo_configured,
                live_capable=True,
                api_capable=True,
                manual_capable=True,
                historical_replay_capable=False,
                supported_markets=["Kalshi demo markets", "events", "crypto category"],
                api_base_url=self.settings.kalshi_demo_api_url,
                app_url=self.settings.kalshi_demo_app_url,
                docs_url="https://docs.kalshi.com/getting_started/demo_env",
                capability_summary="Best non-Polymarket demo venue for event-contract order flow and enterprise credibility.",
                capabilities=[
                    PaperVenueCapability(label="Official demo environment", detail="Separate demo credentials and mock funds for API testing."),
                    PaperVenueCapability(label="API root available", detail="Uses the documented demo trading API root."),
                    PaperVenueCapability(label="Enterprise fit", detail="Useful for compliance-aware demo execution workflows."),
                ],
                setup_steps=[
                    "Create a Kalshi Demo account.",
                    "Create demo API credentials inside the demo environment.",
                    "Set BSM_PAPER_EXECUTION_PROVIDER=kalshi_demo plus demo key id and private key path.",
                    "Map Bot Society signals to Kalshi event tickers before enabling orders.",
                ],
                limitations=[
                    "Demo and production credentials are separate.",
                    "Market mapping is event-specific and cannot be inferred from BTC/ETH/SOL alone.",
                ],
                env_keys=[
                    "BSM_PAPER_EXECUTION_PROVIDER",
                    "BSM_KALSHI_DEMO_API_URL",
                    "BSM_KALSHI_DEMO_KEY_ID",
                    "BSM_KALSHI_DEMO_PRIVATE_KEY_PATH",
                ],
                next_action=(
                    "Credentials are present. Build Kalshi demo ticket mapping next."
                    if kalshi_demo_configured
                    else "Create demo credentials and store only the private key file path in .env.local."
                ),
                safety_note="Do not mix demo credentials with production Kalshi credentials.",
                readiness_score=0.88 if kalshi_demo_configured else 0.62,
            ),
            PaperVenueView(
                id="hyperliquid_testnet",
                name="Hyperliquid Testnet",
                category="Crypto execution testnet",
                priority=5,
                status="ready" if hyperliquid_testnet_configured else "needs_credentials",
                configured=hyperliquid_testnet_configured,
                live_capable=True,
                api_capable=True,
                manual_capable=True,
                historical_replay_capable=False,
                supported_markets=["perpetuals", "spot", "crypto hedging", "execution plumbing"],
                api_base_url=self.settings.hyperliquid_testnet_api_url,
                app_url=self.settings.hyperliquid_testnet_app_url,
                docs_url="https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api",
                capability_summary="Useful for order-management, hedging, latency, and websocket execution tests.",
                capabilities=[
                    PaperVenueCapability(label="Official testnet endpoint", detail="Uses the public testnet API and websocket URLs."),
                    PaperVenueCapability(label="Execution infrastructure", detail="Good venue for validating order routers and risk checks."),
                    PaperVenueCapability(label="Hedge research", detail="Can help test hedges around prediction-market crypto exposures."),
                ],
                setup_steps=[
                    "Open Hyperliquid testnet and fund the testnet wallet from the faucet.",
                    "Set BSM_PAPER_EXECUTION_PROVIDER=hyperliquid_testnet.",
                    "Set a testnet-only wallet address and private key in local secrets if automated orders are needed.",
                    "Keep this isolated from any real mainnet wallet.",
                ],
                limitations=[
                    "Not a prediction-market venue.",
                    "Testnet fills validate mechanics, not real trading edge.",
                ],
                env_keys=[
                    "BSM_PAPER_EXECUTION_PROVIDER",
                    "BSM_HYPERLIQUID_TESTNET_API_URL",
                    "BSM_HYPERLIQUID_TESTNET_WS_URL",
                    "BSM_HYPERLIQUID_TESTNET_WALLET_ADDRESS",
                    "BSM_HYPERLIQUID_TESTNET_PRIVATE_KEY",
                ],
                next_action=(
                    "Credentials are present. Build testnet order-router smoke tests next."
                    if hyperliquid_testnet_configured
                    else "Create a testnet-only wallet and never reuse a mainnet private key."
                ),
                safety_note="Use a dedicated testnet wallet only. Never reuse a wallet with real funds.",
                readiness_score=0.84 if hyperliquid_testnet_configured else 0.58,
            ),
            PaperVenueView(
                id="ibkr_gateway",
                name="Interactive Brokers Paper Gateway",
                category="Brokerage API connector",
                priority=6,
                status=ibkr_status,
                configured=ibkr_gateway_configured and ibkr_account_configured,
                live_capable=True,
                api_capable=True,
                manual_capable=True,
                historical_replay_capable=True,
                supported_markets=["stocks", "ETFs", "options", "futures", "forex", "bonds", "funds"],
                api_base_url=ibkr_endpoint,
                app_url="https://www.interactivebrokers.com/en/trading/ibgateway-stable.php",
                docs_url="https://ibkrcampus.com/campus/ibkr-api-page/twsapi-doc/",
                capability_summary="Paper-first bridge to an Interactive Brokers account through TWS/IB Gateway or Client Portal Gateway.",
                capabilities=[
                    PaperVenueCapability(label="Brokerage account visibility", detail="Designed for account, position, order, and portfolio checks before execution is enabled."),
                    PaperVenueCapability(label="Paper account first", detail="Defaults to TWS paper port 7497 and read-only mode so setup can be verified safely."),
                    PaperVenueCapability(label="Future live rail", detail="Can become a live brokerage execution rail only after legal, risk, and explicit user approval gates."),
                ],
                setup_steps=[
                    "Log in to your IBKR paper account in Trader Workstation or IB Gateway.",
                    "Enable API socket access in TWS or use Client Portal Gateway after browser login and 2FA.",
                    "Set BSM_IBKR_CONNECTION_MODE=tws_gateway, BSM_IBKR_TWS_HOST, BSM_IBKR_TWS_PORT, and BSM_IBKR_ACCOUNT_ID.",
                    "Keep BSM_IBKR_READ_ONLY=true until account and market-data diagnostics pass.",
                    "Only set BSM_IBKR_READ_ONLY=false for paper execution tests; keep BSM_IBKR_LIVE_TRADING_ENABLED=false until legal and risk gates are approved.",
                ],
                limitations=[
                    "TWS and IB Gateway require an authenticated user session; credentials are never stored in BITprivat.",
                    "Market data may require IBKR subscriptions and some snapshot requests can create account charges.",
                    "No live order submission is enabled by this connector without explicit platform configuration.",
                ],
                env_keys=[
                    "BSM_IBKR_CONNECTION_MODE",
                    "BSM_IBKR_ACCOUNT_ID",
                    "BSM_IBKR_TWS_HOST",
                    "BSM_IBKR_TWS_PORT",
                    "BSM_IBKR_CLIENT_ID",
                    "BSM_IBKR_CLIENT_PORTAL_BASE_URL",
                    "BSM_IBKR_READ_ONLY",
                    "BSM_IBKR_LIVE_TRADING_ENABLED",
                ],
                next_action=(
                    "Connector is configured for paper execution tests. Add the IBKR adapter smoke test before routing orders."
                    if ibkr_order_gate_open
                    else "Configure TWS/IB Gateway in paper mode and keep the connector read-only until diagnostics pass."
                ),
                safety_note="Never send or store your IBKR password in the platform. Authenticate directly inside TWS, IB Gateway, or Client Portal Gateway.",
                readiness_score=0.86 if ibkr_order_gate_open else (0.67 if ibkr_gateway_configured and ibkr_account_configured else 0.46),
            ),
            PaperVenueView(
                id="papermarket",
                name="PaperMarket",
                category="Manual Polymarket paper terminal",
                priority=7,
                status="manual_only",
                configured=True,
                live_capable=True,
                api_capable=False,
                manual_capable=True,
                historical_replay_capable=False,
                supported_markets=["Polymarket markets", "YES/NO order books", "manual virtual positions"],
                api_base_url=None,
                app_url="https://papermarket.gitbook.io/papermarket/get-start/overview",
                docs_url="https://papermarket.gitbook.io/papermarket/get-start/overview",
                capability_summary="Good manual validation cockpit before automating a strategy.",
                capabilities=[
                    PaperVenueCapability(label="Live Polymarket book view", detail="Lets a trader load a supported Polymarket market and inspect the live book."),
                    PaperVenueCapability(label="Virtual orders", detail="Stores virtual cash, orders, positions, and trades off-chain."),
                    PaperVenueCapability(label="Visual debugging", detail="Helpful for comparing Bot Society signals with a human paper trade."),
                ],
                setup_steps=[
                    "Use it manually to replay the exact market a bot wants to trade.",
                    "Compare fill assumptions with Bot Society edge and wallet context.",
                    "Promote the strategy to an API venue after the manual loop looks sane.",
                ],
                limitations=[
                    "Manual-first workflow, not the first choice for automated SaaS execution.",
                    "Order availability depends on the supported market loaded by the user.",
                ],
                env_keys=[],
                next_action="Use as the human validation cockpit while API adapters are built.",
                safety_note="Virtual trades remain separate from real Polymarket funds.",
                readiness_score=0.74,
            ),
        ]

        ready_venues = [venue for venue in venues if venue.status in {"ready", "manual_only"}]
        api_ready_venues = [venue for venue in venues if venue.status == "ready" and venue.api_capable]
        selected_mode = self.settings.paper_execution_provider
        recommended_venue_id = selected_mode if selected_mode != "internal" else "polysandbox"
        if recommended_venue_id not in {venue.id for venue in venues}:
            recommended_venue_id = "polysandbox"
        summary = (
            f"{len(ready_venues)} paper venues are immediately usable. "
            f"{len(api_ready_venues)} have API-ready execution paths. "
            f"Recommended next activation: {recommended_venue_id.replace('_', ' ')}."
        )
        return PaperVenuesSnapshot(
            generated_at=self._now(),
            execution_provider_mode=selected_mode,
            recommended_venue_id=recommended_venue_id,
            summary=summary,
            ready_venues=len(ready_venues),
            api_ready_venues=len(api_ready_venues),
            venues=sorted(venues, key=lambda venue: venue.priority),
            activation_sequence=[
                "Keep Bot Society Internal Paper Ledger as the source-of-truth baseline.",
                "Activate Polysandbox first for Polymarket-style API paper orders.",
                "Add Kalshi Demo once event ticker mapping is explicit.",
                "Use Hyperliquid Testnet for execution plumbing and crypto hedge tests, not for prediction-market PnL claims.",
                "Add Interactive Brokers in read-only paper mode for equities, options, futures, and FX account visibility.",
                "Promote any adapter to live trading only after kill switches, position limits, and audit logs exist.",
            ],
            safety_rules=[
                "Paper mode only until an explicit human approval gate is implemented.",
                "Never store seed phrases. Use API keys or testnet-only private keys in .env.local.",
                "Never store IBKR username, password, or 2FA secrets; the authenticated broker session must live in IBKR software.",
                "Use separate wallets and credentials for demo, testnet, sandbox, and production.",
                "Treat paper PnL as research telemetry, not proof of live profitability.",
            ],
        )

    def get_simulation_config(self) -> SimulationConfig:
        repository = BotSocietyRepository(self.database)
        assets = repository.list_assets()
        live_history_capable = self.settings.simulation_live_history
        note = (
            "Strategy Lab can fetch long-range daily history and compare multiple algorithm presets quickly."
            if live_history_capable
            else "Strategy Lab is using the local archive only. Enable live history to test deeper lookback windows."
        )
        return SimulationConfig(
            available_assets=assets,
            lookback_year_options=[1, 3, 5, 10],
            strategy_presets=self.SIMULATION_PRESETS,
            data_source_options=[
                SimulationDataSourceOption(
                    mode="auto",
                    label="Auto real data",
                    description="Use cached/live CoinGecko daily history when available, then fall back to the local archive.",
                ),
                SimulationDataSourceOption(
                    mode="real",
                    label="Require real provider",
                    description="Prefer live or cached provider history and clearly flag any fallback.",
                ),
                SimulationDataSourceOption(
                    mode="local",
                    label="Local archive",
                    description="Use the seeded local archive for deterministic fast runs.",
                ),
            ],
            default_strategy_id="custom_creator",
            default_history_source_mode="auto",
            default_lookback_years=5,
            default_starting_capital=10000,
            default_fee_bps=10,
            live_history_capable=live_history_capable,
            note=note,
        )

    def run_simulation(self, payload: SimulationRequest) -> SimulationRunResult:
        if payload.asset not in BotSocietyRepository(self.database).list_assets():
            raise ValueError(f"Unknown asset: {payload.asset}")

        history_points, data_source, history_note = self._load_simulation_history(
            payload.asset,
            payload.lookback_years,
            payload.history_source_mode,
        )
        if len(history_points) < 3:
            raise ValueError(f"Not enough historical data to simulate {payload.asset}")

        results = {
            preset.strategy_id: self._run_strategy_backtest(history_points, payload, preset.strategy_id)
            for preset in self.SIMULATION_PRESETS
        }
        benchmark = results["buy_hold"]
        leaderboard = [
            SimulationLeaderboardEntry(
                strategy_id=result.strategy_id,
                label=result.label,
                total_return=result.total_return,
                cagr=result.cagr,
                max_drawdown=result.max_drawdown,
                sharpe_ratio=result.sharpe_ratio,
                win_rate=result.win_rate,
                trade_count=result.trade_count,
                exposure_ratio=result.exposure_ratio,
                final_equity=result.final_equity,
                beat_buy_hold=result.total_return > benchmark.total_return,
            )
            for result in sorted(results.values(), key=lambda item: (item.total_return, item.sharpe_ratio), reverse=True)
        ]
        period_start = history_points[0].time
        period_end = history_points[-1].time
        actual_days = max(1, (parse_timestamp(period_end) - parse_timestamp(period_start)).days)
        return SimulationRunResult(
            asset=payload.asset,
            requested_lookback_years=payload.lookback_years,
            actual_years_covered=round(actual_days / 365.25, 2),
            period_start=period_start,
            period_end=period_end,
            history_points=len(history_points),
            data_source=data_source,
            history_note=history_note,
            benchmark_label=benchmark.label,
            benchmark_total_return=benchmark.total_return,
            benchmark_curve=benchmark.equity_curve,
            selected_result=results[payload.strategy_id],
            leaderboard=leaderboard,
        )

    def get_wallet_intelligence(self, force_refresh: bool = False) -> WalletIntelligenceSnapshot:
        if not force_refresh and self._cache_is_fresh(self.wallet_snapshot_cache):
            return self.wallet_snapshot_cache[1]

        tracked_assets = self._current_tracked_assets()
        generated_rows: list[dict]
        summary_prefix = "Demo wallet intelligence is active."

        if self.settings.wallet_provider_mode == "demo":
            generated_rows = self.demo_wallet_provider.generate(tracked_assets)
            self.wallet_provider_fallback = False
            self.wallet_provider_source = self.demo_wallet_provider.source_name
        else:
            try:
                generated_rows = self.wallet_provider.generate(tracked_assets)
                self.wallet_provider_fallback = False
                self.wallet_provider_source = self.wallet_provider.source_name
                summary_prefix = "Live public wallet intelligence is active."
            except Exception as exc:
                generated_rows = self.demo_wallet_provider.generate(tracked_assets)
                self.wallet_provider_fallback = True
                self.wallet_provider_source = f"{self.wallet_provider.source_name}-fallback"
                summary_prefix = f"Wallet fallback active after {exc.__class__.__name__}."

        wallets = [
            WalletProfileView(**row)
            for row in sorted(generated_rows, key=lambda item: (float(item.get("smart_money_score") or 0.0), float(item.get("portfolio_value") or 0.0)), reverse=True)
        ]
        weighted_bias_sum = 0.0
        weighted_bias_denominator = 0.0
        for wallet in wallets:
            weight = max(0.2, wallet.smart_money_score)
            weighted_bias_sum += wallet.net_bias * weight
            weighted_bias_denominator += weight
        aggregate_bias = clamp(weighted_bias_sum / weighted_bias_denominator if weighted_bias_denominator else 0.0, -1.0, 1.0)
        lead_wallet = wallets[0] if wallets else None
        wallet_focus = lead_wallet.primary_asset if lead_wallet and lead_wallet.primary_asset else "tracked assets"
        bias_label = (
            "bullish"
            if aggregate_bias >= 0.18
            else ("bearish" if aggregate_bias <= -0.18 else "balanced")
        )
        summary = (
            f"{summary_prefix} Tracking {len(wallets)} wallets with a {bias_label} aggregate lean across {wallet_focus}. "
            f"Lead wallet {lead_wallet.display_name} is scoring {lead_wallet.smart_money_score:.0%} on smart-money quality."
            if lead_wallet
            else f"{summary_prefix} No public wallet profiles are available yet."
        )
        snapshot = WalletIntelligenceSnapshot(
            generated_at=self._now(),
            summary=summary,
            wallets=wallets,
            aggregate_bias=round(aggregate_bias, 3),
        )
        self.wallet_snapshot_cache = (datetime.now(timezone.utc), snapshot)
        return snapshot

    def get_edge_snapshot(
        self,
        repository: BotSocietyRepository | None = None,
        *,
        force_refresh: bool = False,
        wallet_snapshot: WalletIntelligenceSnapshot | None = None,
        macro_snapshot: MacroSnapshot | None = None,
        latest_assets: list[dict] | None = None,
        recent_signals: list[dict] | None = None,
    ) -> EdgeSnapshot:
        if not force_refresh and self._cache_is_fresh(self.edge_snapshot_cache):
            return self.edge_snapshot_cache[1]

        active_repository = repository or BotSocietyRepository(self.database)
        tracked_assets = self._current_tracked_assets(active_repository)
        latest_assets = {row["asset"]: row for row in (latest_assets or active_repository.list_latest_market_snapshots())}
        recent_signals = recent_signals or active_repository.list_recent_signals(limit=120)
        macro_snapshot = macro_snapshot or self.get_macro_snapshot(active_repository)
        wallet_snapshot = wallet_snapshot or self.get_wallet_intelligence()
        market_intel_source = self.demo_market_intel_provider.source_name

        try:
            intel_rows = self.market_intel_provider.generate_intel(tracked_assets)
            market_intel_source = self.market_intel_provider.source_name
        except Exception:
            intel_rows = self.demo_market_intel_provider.generate_intel(tracked_assets)

        macro_bias = clamp(mean(series.signal_bias for series in macro_snapshot.series), -1.0, 1.0) if macro_snapshot.series else 0.0
        opportunities: list[EdgeOpportunityView] = []

        for row in intel_rows:
            asset = str(row["asset"]).upper()
            asset_row = latest_assets.get(asset, {})
            asset_signals = [signal for signal in recent_signals if str(signal.get("asset")).upper() == asset]
            signal_bias = self._signal_sentiment_for_asset(asset_signals)
            wallet_bias = self._wallet_bias_for_asset(wallet_snapshot, asset)
            wallet_confidence = self._wallet_confidence_for_asset(wallet_snapshot, asset)
            trend_bias = clamp(float(asset_row.get("trend_score") or 0.0), -1.0, 1.0)
            internal_signal_bias = clamp((signal_bias * 0.45) + (wallet_bias * 0.35) + (trend_bias * 0.2), -1.0, 1.0)
            fair_probability = self._fair_probability(
                implied_probability=float(row["implied_probability"]),
                macro_bias=macro_bias,
                wallet_bias=wallet_bias,
                signal_bias=internal_signal_bias,
                trend_bias=trend_bias,
            )
            edge_bps = round((fair_probability - float(row["implied_probability"])) * 10000, 1)
            liquidity_score = min(1.0, float(row.get("liquidity") or 0.0) / 250000)
            quality_score = mean(float(signal.get("source_quality_score") or 0.0) for signal in asset_signals) if asset_signals else 0.45
            confidence = clamp(
                0.2
                + (min(1.0, abs(edge_bps) / 500) * 0.24)
                + (liquidity_score * 0.18)
                + (quality_score * 0.18)
                + (wallet_confidence * 0.12)
                + (min(1.0, len(asset_signals) / 6) * 0.08)
                + (min(1.0, abs(macro_bias)) * 0.05),
                0.12,
                0.99,
            )
            if edge_bps >= 80:
                stance = "bullish"
            elif edge_bps <= -80:
                stance = "bearish"
            else:
                stance = "neutral"
            supporting_signals: list[str] = []
            if asset_signals:
                top_signal = max(
                    asset_signals,
                    key=lambda signal: (
                        float(signal.get("source_quality_score") or 0.0),
                        float(signal.get("relevance") or 0.0),
                    ),
                )
                supporting_signals.append(f"Signal pulse: {top_signal.get('title')}")
                supporting_signals.append(
                    f"Signal sentiment {signal_bias:+.2f} from {len(asset_signals)} recent items"
                )
            if abs(wallet_bias) >= 0.08:
                supporting_signals.append(f"Smart-wallet bias {wallet_bias:+.2f}")
            supporting_signals.append(f"Macro bias {macro_bias:+.2f}")
            opportunities.append(
                EdgeOpportunityView(
                    asset=asset,
                    market_source=str(row.get("market_source") or market_intel_source),
                    market_label=str(row["market_label"]),
                    market_slug=row.get("market_slug"),
                    implied_probability=round(float(row["implied_probability"]), 4),
                    fair_probability=round(fair_probability, 4),
                    edge_bps=edge_bps,
                    confidence=round(confidence, 3),
                    stance=stance,
                    liquidity=round(float(row.get("liquidity") or 0.0), 2),
                    volume_24h=round(float(row.get("volume_24h") or 0.0), 2),
                    supporting_signals=supporting_signals[:3],
                    updated_at=str(row["updated_at"]),
                )
            )

        opportunities.sort(key=lambda item: (abs(item.edge_bps), item.confidence, item.liquidity), reverse=True)
        best_edge = opportunities[0] if opportunities else None
        summary = (
            f"{len(opportunities)} prediction-market surfaces ranked. Strongest dislocation is {best_edge.asset} at {best_edge.edge_bps:+.0f} bps versus implied pricing."
            if best_edge
            else "No prediction-market edge surfaces are available right now."
        )
        snapshot = EdgeSnapshot(
            generated_at=self._now(),
            summary=summary,
            opportunities=opportunities,
        )
        self.edge_snapshot_cache = (datetime.now(timezone.utc), snapshot)
        return snapshot

    def export_advanced_backtest(self, payload: SimulationRequest) -> AdvancedBacktestExport:
        result = self.run_simulation(payload)
        repository = BotSocietyRepository(self.database)
        macro_snapshot = self.get_macro_snapshot(repository)
        wallet_snapshot = self.get_wallet_intelligence()
        edge_snapshot = self.get_edge_snapshot(repository, wallet_snapshot=wallet_snapshot, macro_snapshot=macro_snapshot)
        asset_edge = next((item for item in edge_snapshot.opportunities if item.asset == payload.asset), None)
        related_wallets = [wallet for wallet in wallet_snapshot.wallets if wallet.primary_asset == payload.asset][:3]
        filename = self._build_export_filename(payload)
        package_filename = self._build_adapter_package_filename(filename)
        adapter_manifest = self._build_prediction_market_adapter_manifest(
            filename=filename,
            package_filename=package_filename,
            payload=payload,
            result=result,
            asset_edge=asset_edge,
            related_wallets=related_wallets,
        )
        export_payload = {
            "metadata": {
                "generated_at": self._now(),
                "engine_target": "prediction-market-backtesting",
                "asset": payload.asset,
                "strategy_id": payload.strategy_id,
                "lookback_years": payload.lookback_years,
                "data_source": result.data_source,
            },
            "simulation_request": payload.model_dump(),
            "simulation_result": result.model_dump(),
            "macro_context": macro_snapshot.model_dump(),
            "edge_context": asset_edge.model_dump() if asset_edge else None,
            "wallet_context": [wallet.model_dump() for wallet in related_wallets],
            "prediction_market_adapter": adapter_manifest,
            "notes": [
                "Generated for import into an external prediction-market backtesting workflow.",
                "Use the edge context as the prior and the strategy result as the execution benchmark.",
                "Wallet context ranks public trader behavior by smart-money score and directional bias.",
            ],
        }
        artifact_path = self._write_export_artifact(filename, export_payload)
        package_path = self._write_prediction_market_adapter_package(
            package_filename=package_filename,
            export_filename=filename,
            export_payload=export_payload,
            payload=payload,
            result=result,
            asset_edge=asset_edge,
            related_wallets=related_wallets,
        )
        summary = (
            f"Prepared {payload.asset} advanced export for {payload.strategy_id} across {result.actual_years_covered:.2f} years "
            f"with {len(related_wallets)} relevant wallet profiles, "
            f"a prediction-market adapter pack, and "
            f"{'a matched edge surface' if asset_edge else 'no direct edge surface match'}."
        )
        return AdvancedBacktestExport(
            generated_at=self._now(),
            engine_target="prediction-market-backtesting",
            asset=payload.asset,
            summary=summary,
            filename=filename,
            download_url=f"/api/simulation/exports/{filename}",
            filesystem_path=str(artifact_path),
            saved_to_disk=True,
            package_filename=package_filename,
            package_download_url=f"/api/simulation/packages/{package_filename}",
            package_filesystem_path=str(package_path),
            payload=export_payload,
        )

    def list_simulation_exports(self, limit: int = 12) -> list[SimulationExportArtifact]:
        artifacts_dir = self._export_artifacts_dir()
        artifacts: list[SimulationExportArtifact] = []
        for path in sorted(artifacts_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)[:limit]:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            metadata = payload.get("metadata") if isinstance(payload, dict) else {}
            if not isinstance(metadata, dict):
                metadata = {}
            adapter = payload.get("prediction_market_adapter") if isinstance(payload, dict) else {}
            if not isinstance(adapter, dict):
                adapter = {}
            artifacts.append(
                SimulationExportArtifact(
                    filename=path.name,
                    asset=str(metadata.get("asset") or "n/a"),
                    strategy_id=str(metadata.get("strategy_id") or "n/a"),
                    lookback_years=max(1, min(10, int(metadata.get("lookback_years") or 1))),
                    engine_target=str(metadata.get("engine_target") or "prediction-market-backtesting"),
                    generated_at=str(metadata.get("generated_at") or self._now()),
                    size_bytes=max(0, path.stat().st_size),
                    download_url=f"/api/simulation/exports/{path.name}",
                    package_filename=str(adapter.get("package_filename")) if adapter.get("package_filename") else None,
                    package_download_url=(
                        f"/api/simulation/packages/{adapter.get('package_filename')}"
                        if adapter.get("package_filename")
                        else None
                    ),
                )
            )
        return artifacts

    def get_simulation_export_path(self, filename: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9._-]+\.json", filename):
            raise ValueError("Invalid export filename")
        candidate = (self._export_artifacts_dir() / filename).resolve()
        artifacts_dir = self._export_artifacts_dir().resolve()
        if artifacts_dir not in candidate.parents:
            raise ValueError("Invalid export filename")
        if not candidate.exists() or not candidate.is_file():
            raise ValueError("Export artifact not found")
        return candidate

    def get_simulation_package_path(self, filename: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9._-]+\.zip", filename):
            raise ValueError("Invalid package filename")
        candidate = (self._export_artifacts_dir() / filename).resolve()
        artifacts_dir = self._export_artifacts_dir().resolve()
        if artifacts_dir not in candidate.parents:
            raise ValueError("Invalid package filename")
        if not candidate.exists() or not candidate.is_file():
            raise ValueError("Export package not found")
        return candidate

    def get_alert_inbox(self, user_slug: str, unread_only: bool = False) -> AlertInbox:
        repository = BotSocietyRepository(self.database)
        alerts = [
            self._to_alert_model(row)
            for row in repository.list_alert_deliveries(
                user_slug,
                limit=self.settings.alert_inbox_limit,
                unread_only=unread_only,
            )
        ]
        return AlertInbox(
            unread_count=repository.count_unread_alert_deliveries(user_slug),
            alerts=alerts,
        )

    def _lightweight_alert_inbox(self) -> AlertInbox:
        return AlertInbox(unread_count=0, alerts=[])

    def _lightweight_notification_health(self) -> NotificationHealthSnapshot:
        return NotificationHealthSnapshot(
            active_channels=0,
            delivered_last_24h=0,
            retry_queue_depth=0,
            exhausted_deliveries=0,
            last_delivery_at=None,
            channels=[],
        )

    def mark_alert_read(self, user_slug: str, alert_id: int) -> AlertInbox:
        repository = BotSocietyRepository(self.database)
        repository.mark_alert_delivery_read(user_slug, alert_id, self._now())
        return self.get_alert_inbox(user_slug)

    def mark_all_alerts_read(self, user_slug: str) -> AlertInbox:
        repository = BotSocietyRepository(self.database)
        repository.mark_all_alert_deliveries_read(user_slug, self._now())
        return self.get_alert_inbox(user_slug)

    def get_user_profile(
        self,
        user_slug: str,
        *,
        repository: BotSocietyRepository | None = None,
        leaderboard_map: dict[str, BotSummary] | None = None,
        alert_inbox: AlertInbox | None = None,
    ) -> UserProfile:
        active_repository = repository or BotSocietyRepository(self.database)
        user = active_repository.get_user(user_slug)
        if not user:
            raise ValueError(f"User {user_slug} is not available")

        leaderboard_map = leaderboard_map or {
            bot.slug: bot for bot in self._build_bot_summaries(active_repository, user_slug)
        }
        follows = [
            FollowedBot(
                bot_slug=row["bot_slug"],
                name=row["name"],
                score=leaderboard_map[row["bot_slug"]].score if row["bot_slug"] in leaderboard_map else 0.0,
                created_at=row["created_at"],
            )
            for row in active_repository.list_user_follows(user_slug)
        ]
        watchlist = [WatchlistItem(**row) for row in active_repository.list_watchlist_items(user_slug)]
        alert_rules = [
            AlertRule(**{**row, "is_active": bool(row["is_active"])})
            for row in active_repository.list_alert_rules(user_slug)
        ]
        notification_channels = [
            NotificationChannel(**{**row, "is_active": bool(row["is_active"])})
            for row in active_repository.list_notification_channels(user_slug)
        ]
        alert_inbox = alert_inbox or self.get_alert_inbox(user_slug)
        return UserProfile(
            slug=user["slug"],
            display_name=user["display_name"],
            email=user["email"],
            tier=user["tier"],
            is_demo_user=bool(user.get("is_demo_user")),
            billing=self.get_billing_snapshot(user_slug, can_manage=not bool(user.get("is_demo_user"))),
            follows=follows,
            watchlist=watchlist,
            alert_rules=alert_rules,
            recent_alerts=alert_inbox.alerts,
            notification_channels=notification_channels,
            unread_alert_count=alert_inbox.unread_count,
        )

    def get_notification_health(self, user_slug: str) -> NotificationHealthSnapshot:
        repository = BotSocietyRepository(self.database)
        channels = repository.list_notification_channels(user_slug)
        now = datetime.now(timezone.utc)
        since = now - timedelta(hours=24)
        delivery_metrics = repository.get_alert_delivery_metrics(user_slug, to_timestamp(since))
        channel_metrics = {
            int(row["notification_channel_id"]): row
            for row in repository.list_alert_delivery_channel_metrics(user_slug)
            if row.get("notification_channel_id") is not None
        }

        channel_health_map: dict[int, dict[str, object]] = {}

        for channel in channels:
            channel_id = int(channel["id"])
            metrics = channel_metrics.get(channel_id, {})
            channel_health_map[int(channel["id"])] = {
                "channel_id": channel_id,
                "channel_type": channel["channel_type"],
                "target": channel["target"],
                "is_active": bool(channel["is_active"]),
                "delivered_count": int(metrics.get("delivered_count") or 0),
                "retry_scheduled_count": int(metrics.get("retry_scheduled_count") or 0),
                "exhausted_count": int(metrics.get("exhausted_count") or 0),
                "last_delivered_at": metrics.get("last_delivered_at") or channel.get("last_delivered_at"),
                "last_error": channel.get("last_error"),
            }

        channel_health = [
            NotificationChannelHealth(**payload)
            for payload in sorted(channel_health_map.values(), key=lambda item: str(item["target"]).lower())
        ]
        return NotificationHealthSnapshot(
            active_channels=sum(1 for channel in channels if bool(channel["is_active"])),
            delivered_last_24h=int(delivery_metrics["delivered_last_24h"]),
            retry_queue_depth=int(delivery_metrics["retry_queue_depth"]),
            exhausted_deliveries=int(delivery_metrics["exhausted_deliveries"]),
            last_delivery_at=delivery_metrics.get("last_delivery_at"),
            channels=channel_health,
        )

    def retry_failed_notifications(self, limit: int | None = None) -> NotificationRetryResult:
        repository = BotSocietyRepository(self.database)
        scan_limit = min(limit or self.settings.notification_retry_limit, self.settings.notification_retry_limit)
        retryable = repository.list_retryable_alert_deliveries(self._now(), limit=scan_limit)
        delivered = 0
        rescheduled = 0
        exhausted = 0

        for event in retryable:
            channel = {
                "id": event["notification_channel_id"],
                "channel_type": event["notification_channel_type"],
                "target": event["notification_channel_target"],
                "secret": event.get("notification_channel_secret"),
            }
            payload = {
                "title": event["title"],
                "message": event["message"],
                "prediction_id": event["prediction_id"],
                "bot_slug": event["bot_slug"],
                "asset": event["asset"],
                "direction": event["direction"],
                "confidence": event["confidence"],
                "rule_id": event["rule_id"],
            }
            attempt_count = int(event.get("attempt_count") or 0) + 1
            attempted_at = self._now()
            success, error = self.dispatcher.dispatch(channel, payload)

            if success:
                delivered += 1
                repository.update_notification_channel_delivery(
                    str(event["user_slug"]),
                    int(event["notification_channel_id"]),
                    delivered_at=attempted_at,
                    error=None,
                )
                repository.update_alert_delivery_event(
                    int(event["id"]),
                    {
                        "delivery_status": "delivered",
                        "attempt_count": attempt_count,
                        "last_attempt_at": attempted_at,
                        "next_attempt_at": None,
                        "error_detail": None,
                    },
                )
                continue

            final_status, next_attempt_at = self._next_delivery_state(attempt_count)
            if final_status == "retry_scheduled":
                rescheduled += 1
            else:
                exhausted += 1

            repository.update_notification_channel_delivery(
                str(event["user_slug"]),
                int(event["notification_channel_id"]),
                delivered_at=None,
                error=error,
            )
            repository.update_alert_delivery_event(
                int(event["id"]),
                {
                    "delivery_status": final_status,
                    "attempt_count": attempt_count,
                    "last_attempt_at": attempted_at,
                    "next_attempt_at": next_attempt_at,
                    "error_detail": error,
                    "message": event["message"],
                },
            )

        return NotificationRetryResult(
            scanned_events=len(retryable),
            delivered=delivered,
            rescheduled=rescheduled,
            exhausted=exhausted,
        )

    def follow_bot(self, user_slug: str, bot_slug: str) -> UserProfile:
        repository = BotSocietyRepository(self.database)
        if not repository.get_bot(bot_slug):
            raise ValueError(f"Unknown bot slug: {bot_slug}")
        repository.create_follow(user_slug, bot_slug, self._now())
        self._clear_live_caches()
        return self.get_user_profile(user_slug)

    def unfollow_bot(self, user_slug: str, bot_slug: str) -> UserProfile:
        repository = BotSocietyRepository(self.database)
        repository.delete_follow(user_slug, bot_slug)
        self._clear_live_caches()
        return self.get_user_profile(user_slug)

    def add_watchlist_asset(self, user_slug: str, asset: str) -> UserProfile:
        repository = BotSocietyRepository(self.database)
        normalized_asset = asset.upper()
        if normalized_asset not in repository.list_assets():
            raise ValueError(f"Unknown asset: {normalized_asset}")
        repository.create_watchlist_item(user_slug, normalized_asset, self._now())
        self._clear_live_caches()
        return self.get_user_profile(user_slug)

    def remove_watchlist_asset(self, user_slug: str, asset: str) -> UserProfile:
        repository = BotSocietyRepository(self.database)
        repository.delete_watchlist_item(user_slug, asset.upper())
        self._clear_live_caches()
        return self.get_user_profile(user_slug)

    def add_alert_rule(self, user_slug: str, payload: AlertRuleCreate) -> UserProfile:
        repository = BotSocietyRepository(self.database)
        asset = payload.asset.upper() if payload.asset else None
        if asset and asset not in repository.list_assets():
            raise ValueError(f"Unknown asset: {asset}")
        if payload.bot_slug and not repository.get_bot(payload.bot_slug):
            raise ValueError(f"Unknown bot slug: {payload.bot_slug}")
        repository.create_alert_rule(
            {
                "user_slug": user_slug,
                "bot_slug": payload.bot_slug,
                "asset": asset,
                "min_confidence": payload.min_confidence,
                "is_active": True,
                "created_at": self._now(),
            }
        )
        self._clear_live_caches()
        return self.get_user_profile(user_slug)

    def delete_alert_rule(self, user_slug: str, rule_id: int) -> UserProfile:
        repository = BotSocietyRepository(self.database)
        repository.delete_alert_rule(user_slug, rule_id)
        self._clear_live_caches()
        return self.get_user_profile(user_slug)

    def add_notification_channel(self, user_slug: str, payload: NotificationChannelCreate) -> UserProfile:
        repository = BotSocietyRepository(self.database)
        existing_channels = repository.list_notification_channels(user_slug)
        if any(channel["channel_type"] == payload.channel_type for channel in existing_channels):
            raise ValueError(f"{payload.channel_type.title()} notifications are already configured for this workspace")
        try:
            repository.create_notification_channel(
                {
                    "user_slug": user_slug,
                    "channel_type": payload.channel_type,
                    "target": payload.target,
                    "secret": payload.secret,
                    "is_active": True,
                    "created_at": self._now(),
                    "last_delivered_at": None,
                    "last_error": None,
                }
            )
        except IntegrityError as exc:
            raise ValueError("That notification channel already exists") from exc
        self._clear_live_caches()
        return self.get_user_profile(user_slug)

    def delete_notification_channel(self, user_slug: str, channel_id: int) -> UserProfile:
        repository = BotSocietyRepository(self.database)
        repository.delete_notification_channel(user_slug, channel_id)
        self._clear_live_caches()
        return self.get_user_profile(user_slug)

    def get_provider_status(self, *, force_refresh: bool = False) -> ProviderStatus:
        if not force_refresh and self._cache_is_fresh(self.provider_status_cache, ttl_seconds=30):
            return self.provider_status_cache[1]

        market_readiness = self.market_provider.readiness()
        signal_ready, signal_warning, venue_statuses = self._signal_provider_health()
        macro_readiness = self.macro_provider.readiness()
        wallet_readiness = self.wallet_provider.readiness()
        social_readiness = self._social_discovery_provider_component()
        market_configured, market_live_capable = self._provider_configuration("market")
        signal_configured, signal_live_capable = self._provider_configuration("signal")
        macro_configured, macro_live_capable = self._provider_configuration("macro")
        wallet_configured, wallet_live_capable = self._provider_configuration("wallet")
        status = ProviderStatus(
            environment_name=self.settings.environment_name,
            deployment_target=self.settings.deployment_target,
            database_backend=self.database.dialect_name,
            database_target=self._database_target(),
            market_provider_mode=self.settings.market_provider_mode,
            market_provider_source=self.market_provider_source,
            market_provider_configured=market_configured,
            market_provider_live_capable=market_live_capable,
            market_provider_ready=market_readiness.ready,
            market_provider_warning=market_readiness.warning,
            signal_provider_mode=self._signal_provider_mode_label(),
            signal_provider_source=self.signal_provider_source,
            signal_provider_configured=signal_configured,
            signal_provider_live_capable=signal_live_capable,
            signal_provider_ready=signal_ready,
            signal_provider_warning=signal_warning,
            macro_provider_mode=self.settings.macro_provider_mode,
            macro_provider_source=self.macro_provider_source,
            macro_provider_configured=macro_configured,
            macro_provider_live_capable=macro_live_capable,
            macro_provider_ready=macro_readiness.ready,
            macro_provider_warning=macro_readiness.warning,
            wallet_provider_mode=self.settings.wallet_provider_mode,
            wallet_provider_source=self.wallet_provider_source,
            wallet_provider_configured=wallet_configured,
            wallet_provider_live_capable=wallet_live_capable,
            wallet_provider_ready=wallet_readiness.ready,
            wallet_provider_warning=wallet_readiness.warning,
            social_discovery_provider_mode=social_readiness.mode,
            social_discovery_provider_source=social_readiness.source,
            social_discovery_configured=social_readiness.configured,
            social_discovery_live_capable=social_readiness.live_capable,
            social_discovery_ready=social_readiness.ready,
            social_discovery_warning=social_readiness.warning,
            youtube_discovery_queries=list(self.settings.youtube_discovery_queries),
            youtube_channel_ids=list(self.settings.youtube_channel_ids),
            tracked_coin_ids=list(self.settings.tracked_coin_ids),
            fred_series_ids=list(self.settings.fred_series_ids),
            tracked_wallets=list(self.settings.tracked_wallets),
            rss_feed_urls=list(self.settings.rss_feed_urls),
            reddit_subreddits=list(self.settings.reddit_subreddits),
            venue_signal_providers=venue_statuses,
            market_fallback_active=self.market_provider_fallback,
            signal_fallback_active=self.signal_provider_fallback,
            macro_fallback_active=self.macro_provider_fallback,
            wallet_fallback_active=self.wallet_provider_fallback,
            social_discovery_fallback_active=(
                self.settings.social_discovery_provider == "youtube"
                and social_readiness.live_capable
                and not social_readiness.ready
            ),
        )
        self.provider_status_cache = (datetime.now(timezone.utc), status)
        return status

    def get_connector_control(
        self,
        provider_status: ProviderStatus | None = None,
        paper_venues: PaperVenuesSnapshot | None = None,
    ) -> ConnectorControlSnapshot:
        provider_status = provider_status or self.get_provider_status()
        paper_venues = paper_venues or self.get_paper_venues()
        venue_lookup = {venue.id: venue for venue in paper_venues.venues}

        signal_source = provider_status.signal_provider_source
        if provider_status.venue_signal_providers:
            signal_source = f"{signal_source} + venue adapters"

        stripe_configured = self.settings.fiat_billing_provider == "stripe"
        stripe_ready = stripe_configured and all(
            (
                self.settings.stripe_publishable_key,
                self.settings.stripe_secret_key,
                self.settings.stripe_webhook_secret,
                self.settings.stripe_basic_price_id,
            )
        )
        coinbase_onramp_configured = bool(self.settings.coinbase_onramp_api_key or self.settings.coinbase_onramp_app_id)
        coinbase_onramp_ready = bool(self.settings.coinbase_onramp_api_key and self.settings.coinbase_onramp_app_id)
        edge_router_ready = bool(self.settings.canonical_host and self.settings.force_https)
        desktop_configured = self.settings.desktop_app_framework != "none" or bool(self.settings.desktop_bundle_id)
        desktop_ready = self.settings.desktop_app_framework != "none" and bool(self.settings.desktop_bundle_id)
        social_fallback_active = provider_status.social_discovery_fallback_active
        hyperliquid_enabled = self.settings.market_provider_mode in {"auto", "hyperliquid"}
        ibkr_endpoint_configured = self.settings.ibkr_connection_mode != "disabled" and (
            bool(self.settings.ibkr_tws_host and self.settings.ibkr_tws_port)
            if self.settings.ibkr_connection_mode == "tws_gateway"
            else bool(self.settings.ibkr_client_portal_base_url)
        )
        ibkr_configured = bool(ibkr_endpoint_configured and self.settings.ibkr_account_id)
        ibkr_live_ready = bool(
            ibkr_configured
            and not self.settings.ibkr_read_only
            and self.settings.ibkr_live_trading_enabled
        )

        connectors = [
            self._connector_item(
                connector_id="coingecko-market-data",
                label="CoinGecko Market Data",
                category="Market Data",
                mode=provider_status.market_provider_mode,
                source=provider_status.market_provider_source,
                configured=provider_status.market_provider_configured,
                live_capable=provider_status.market_provider_live_capable,
                ready=provider_status.market_provider_ready,
                fallback_active=provider_status.market_fallback_active,
                activation_phase="Market data cutover",
                owner="Data Integrations",
                risk_level="low",
                target_surface="Spot market tracking and historical archive hydration",
                env_keys=["BSM_COINGECKO_API_KEY"],
                next_actions=[
                    "Keep market mode on auto so CoinGecko acts as the resilient spot-data fallback.",
                    "Attach a live API key before increasing tracked assets.",
                ],
            ),
            self._connector_item(
                connector_id="hyperliquid-market-feed",
                label="Hyperliquid Market Feed",
                category="Derivatives",
                mode="auto" if self.settings.market_provider_mode == "auto" else ("hyperliquid" if hyperliquid_enabled else "planned"),
                source="Hyperliquid perpetual futures surfaces",
                configured=hyperliquid_enabled,
                live_capable=True,
                ready=hyperliquid_enabled and provider_status.market_provider_ready,
                fallback_active=(not hyperliquid_enabled) or provider_status.market_fallback_active,
                activation_phase="Perps data activation",
                owner="Trading Integrations",
                risk_level="high",
                target_surface="Perpetuals monitoring, momentum context, and future execution adapters",
                env_keys=["BSM_HYPERLIQUID_DEX"],
                next_actions=[
                    "Keep BSM_MARKET_PROVIDER=auto so Hyperliquid can lead while CoinGecko remains a fallback.",
                    "Pair the live feed with testnet credentials before any execution-adjacent work.",
                ],
                app_url=self.settings.hyperliquid_testnet_app_url,
            ),
            self._connector_item(
                connector_id="ibkr-brokerage-gateway",
                label="Interactive Brokers Gateway",
                category="Brokerage",
                mode=self.settings.ibkr_connection_mode,
                source="IBKR TWS API, IB Gateway, or Client Portal Gateway",
                configured=ibkr_configured,
                live_capable=True,
                ready=ibkr_live_ready,
                fallback_active=ibkr_endpoint_configured and not ibkr_live_ready,
                activation_phase="Brokerage account connection",
                owner="Trading Integrations",
                risk_level="high",
                target_surface="paper account verification, equities/options/futures/FX research, and future broker execution",
                env_keys=[
                    "BSM_IBKR_CONNECTION_MODE",
                    "BSM_IBKR_ACCOUNT_ID",
                    "BSM_IBKR_TWS_HOST",
                    "BSM_IBKR_TWS_PORT",
                    "BSM_IBKR_CLIENT_ID",
                    "BSM_IBKR_CLIENT_PORTAL_BASE_URL",
                    "BSM_IBKR_READ_ONLY",
                    "BSM_IBKR_LIVE_TRADING_ENABLED",
                    "BSM_IBKR_MARKET_DATA_SUBSCRIBED",
                ],
                next_actions=[
                    "Start with the IBKR paper account and keep BSM_IBKR_READ_ONLY=true while confirming account visibility.",
                    "Do not store an IBKR password in BITprivat; log in through TWS, IB Gateway, or Client Portal Gateway.",
                    "Only enable order submission after paper smoke tests, per-account limits, audit logs, and legal review are complete.",
                ],
                app_url="https://www.interactivebrokers.com/en/trading/ibgateway-stable.php",
            ),
            self._connector_item(
                connector_id="signal-ingestion",
                label="Signal Ingestion",
                category="Signals",
                mode=provider_status.signal_provider_mode,
                source=signal_source,
                configured=provider_status.signal_provider_configured,
                live_capable=provider_status.signal_provider_live_capable,
                ready=provider_status.signal_provider_ready,
                fallback_active=provider_status.signal_fallback_active,
                activation_phase="Signal intake expansion",
                owner="Signal Intelligence",
                risk_level="medium",
                target_surface="News, social, and venue context feeding the bot network",
                env_keys=["BSM_RSS_FEED_URLS", "BSM_REDDIT_CLIENT_ID", "BSM_REDDIT_CLIENT_SECRET"],
                next_actions=[
                    "Keep RSS active for broad intake and enable Reddit only with production credentials.",
                    "Tune source-quality weighting before relying on venue-linked signals at scale.",
                ],
            ),
            self._connector_item(
                connector_id="fred-macro",
                label="FRED Macro Series",
                category="Macro",
                mode=provider_status.macro_provider_mode,
                source=provider_status.macro_provider_source,
                configured=provider_status.macro_provider_configured,
                live_capable=provider_status.macro_provider_live_capable,
                ready=provider_status.macro_provider_ready,
                fallback_active=provider_status.macro_fallback_active,
                activation_phase="Macro regime feed",
                owner="Research Data",
                risk_level="low",
                target_surface="Regime detection and macro overlays inside the dashboard and Strategy Lab",
                env_keys=["BSM_FRED_API_KEY", "BSM_FRED_SERIES_IDS"],
                next_actions=[
                    "Move macro mode to fred on the production deployment.",
                    "Lock the final series list before publishing enterprise-ready reporting.",
                ],
            ),
            self._connector_item(
                connector_id="polymarket-intel",
                label="Polymarket Intelligence",
                category="Prediction Markets",
                mode="live" if any(component.source == "polymarket" and component.ready for component in provider_status.venue_signal_providers) else "planned",
                source="Polymarket venue signals, wallet footprints, and edge surfaces",
                configured="polymarket" in {component.source for component in provider_status.venue_signal_providers} or self.settings.wallet_provider_mode == "polymarket",
                live_capable=True,
                ready=any(component.source == "polymarket" and component.ready for component in provider_status.venue_signal_providers) or self.settings.wallet_provider_mode == "polymarket",
                fallback_active=False,
                activation_phase="Prediction-market intelligence",
                owner="Venue Integrations",
                risk_level="medium",
                target_surface="Venue pulse, smart-money tracking, and probability edge analysis",
                env_keys=["BSM_VENUE_SIGNAL_PROVIDERS", "BSM_WALLET_PROVIDER", "BSM_TRACKED_WALLETS"],
                next_actions=[
                    "Keep paper trading separate from live research ingestion.",
                    "Curate tracked public wallets before ranking smart-money profiles in production.",
                ],
                app_url=venue_lookup["polysandbox"].app_url if "polysandbox" in venue_lookup else None,
            ),
            self._connector_item(
                connector_id="kalshi-surfaces",
                label="Kalshi Surfaces",
                category="Prediction Markets",
                mode="live" if any(component.source == "kalshi" and component.ready for component in provider_status.venue_signal_providers) else (venue_lookup["kalshi_demo"].status if "kalshi_demo" in venue_lookup else "planned"),
                source="Kalshi public markets plus demo trading venue",
                configured=any(component.source == "kalshi" for component in provider_status.venue_signal_providers) or ("kalshi_demo" in venue_lookup and venue_lookup["kalshi_demo"].configured),
                live_capable=("kalshi_demo" in venue_lookup and venue_lookup["kalshi_demo"].live_capable),
                ready=("kalshi_demo" in venue_lookup and venue_lookup["kalshi_demo"].status == "ready"),
                fallback_active=False,
                activation_phase="Regulated venue review",
                owner="Venue Integrations",
                risk_level="high",
                target_surface="Event market monitoring and future paper-execution routing",
                env_keys=["BSM_VENUE_SIGNAL_PROVIDERS", "BSM_KALSHI_DEMO_KEY_ID", "BSM_KALSHI_DEMO_PRIVATE_KEY_PATH"],
                next_actions=[
                    "Keep Kalshi on demo or research-only surfaces until legal review clears anything broader.",
                    "Use the venue to validate monitoring and paper workflows, not live execution.",
                ],
                app_url=venue_lookup["kalshi_demo"].app_url if "kalshi_demo" in venue_lookup else None,
            ),
            self._connector_item(
                connector_id="wallet-intel",
                label="Wallet Intelligence",
                category="Smart Money",
                mode=provider_status.wallet_provider_mode,
                source=provider_status.wallet_provider_source,
                configured=provider_status.wallet_provider_configured,
                live_capable=provider_status.wallet_provider_live_capable,
                ready=provider_status.wallet_provider_ready,
                fallback_active=provider_status.wallet_fallback_active,
                activation_phase="Smart-money provenance",
                owner="Signal Intelligence",
                risk_level="medium",
                target_surface="Tracked public trader personas and conviction ranking",
                env_keys=["BSM_WALLET_PROVIDER", "BSM_TRACKED_WALLETS"],
                next_actions=[
                    "Curate a first production wallet list instead of relying on generic demo traffic.",
                    "Keep provenance weighting visible as smart-money surfaces expand.",
                ],
            ),
            self._connector_item(
                connector_id="youtube-social-discovery",
                label="YouTube Social Discovery",
                category="Social Intelligence",
                mode=provider_status.social_discovery_provider_mode,
                source=provider_status.social_discovery_provider_source,
                configured=provider_status.social_discovery_configured,
                live_capable=provider_status.social_discovery_live_capable,
                ready=provider_status.social_discovery_ready,
                fallback_active=social_fallback_active,
                activation_phase="Creator-trader discovery",
                owner="Signal Intelligence",
                risk_level="medium",
                target_surface="creator scorecards, evidence timelines, and managed-paper follow allocation",
                env_keys=[
                    "BSM_SOCIAL_DISCOVERY_PROVIDER",
                    "BSM_YOUTUBE_API_KEY",
                    "BSM_YOUTUBE_DISCOVERY_QUERIES",
                    "BSM_YOUTUBE_CHANNEL_IDS",
                    "BSM_YOUTUBE_VIDEO_LIMIT",
                ],
                next_actions=[
                    "Run python -m api.app.jobs social-discovery after adding the YouTube key.",
                    "Curate channel IDs for known trader-influencers before relying on query discovery alone.",
                ],
                app_url="https://console.cloud.google.com/apis/library/youtube.googleapis.com",
            ),
            self._connector_item(
                connector_id="stripe-billing-rail",
                label="Stripe Billing Rail",
                category="Revenue",
                mode=self.settings.fiat_billing_provider,
                source="Stripe Checkout, Billing, Portal, and webhooks",
                configured=stripe_configured,
                live_capable=stripe_configured,
                ready=stripe_ready,
                fallback_active=stripe_configured and not stripe_ready,
                activation_phase="Fiat card onboarding",
                owner="Commercial Ops",
                risk_level="medium",
                target_surface="Paid SaaS onboarding, subscription state, and entitlement gates",
                env_keys=[
                    "BSM_FIAT_BILLING_PROVIDER",
                    "BSM_STRIPE_PUBLISHABLE_KEY",
                    "BSM_STRIPE_SECRET_KEY",
                    "BSM_STRIPE_WEBHOOK_SECRET",
                    "BSM_STRIPE_BASIC_PRICE_ID",
                ],
                next_actions=[
                    "Keep card entry inside hosted Stripe Checkout and Customer Portal.",
                    "Set Stripe webhook secrets before enabling paid plan transitions.",
                ],
                app_url="https://dashboard.stripe.com/",
            ),
            self._connector_item(
                connector_id="coinbase-onramp-rail",
                label="Coinbase Onramp Rail",
                category="Crypto Payments",
                mode="coinbase_onramp" if coinbase_onramp_configured else "planned",
                source="Coinbase Onramp with Coinbase Commerce or MoonPay as optional backup rails",
                configured=coinbase_onramp_configured,
                live_capable=True,
                ready=coinbase_onramp_ready,
                fallback_active=coinbase_onramp_configured and not coinbase_onramp_ready,
                activation_phase="Crypto funding onboarding",
                owner="Commercial Ops",
                risk_level="high",
                target_surface="Hosted wallet funding and optional crypto-denominated account credits",
                env_keys=[
                    "BSM_COINBASE_ONRAMP_API_KEY",
                    "BSM_COINBASE_ONRAMP_APP_ID",
                    "BSM_COINBASE_COMMERCE_API_KEY",
                    "BSM_MOONPAY_API_KEY",
                ],
                next_actions=[
                    "Keep KYC and payment collection inside the hosted onramp provider.",
                    "Ledger completions as credits only after webhook verification is in place.",
                ],
                app_url="https://www.coinbase.com/onramp",
            ),
            self._connector_item(
                connector_id="cloudflare-edge-router",
                label="Cloudflare Edge Router",
                category="Infrastructure",
                mode="cloudflare-worker",
                source="Cloudflare Worker routes for root, app, API, and status surfaces",
                configured=bool(self.settings.canonical_host),
                live_capable=True,
                ready=edge_router_ready,
                fallback_active=False,
                activation_phase="Public routing hardening",
                owner="Platform Ops",
                risk_level="low",
                target_surface="bitprivat.com, app.bitprivat.com, api.bitprivat.com, and status.bitprivat.com",
                env_keys=["CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN", "BSM_CANONICAL_HOST", "BSM_FORCE_HTTPS"],
                next_actions=[
                    "Add Cloudflare GitHub secrets so edge deploys are automatic.",
                    "Run production verification after each Akash redeploy.",
                ],
            ),
            self._connector_item(
                connector_id="desktop-shell",
                label="Windows and macOS Shell",
                category="Distribution",
                mode=self.settings.desktop_app_framework,
                source="Tauri-style signed shell around the hosted dashboard",
                configured=desktop_configured,
                live_capable=False,
                ready=desktop_ready,
                fallback_active=False,
                activation_phase="Installable app packaging",
                owner="Product Platform",
                risk_level="medium",
                target_surface="Installable Windows and macOS application wrapper",
                env_keys=[
                    "BSM_DESKTOP_APP_FRAMEWORK",
                    "BSM_DESKTOP_BUNDLE_ID",
                    "BSM_APPLE_DEVELOPER_TEAM_ID",
                    "BSM_WINDOWS_DISTRIBUTION_CHANNEL",
                ],
                next_actions=[
                    "Wrap the hosted dashboard first; keep payments in the system browser.",
                    "Add signing and notarization only after the web app routing is stable.",
                ],
            ),
        ]

        live_or_ready_count = sum(item.state in {"live", "ready"} for item in connectors)
        return ConnectorControlSnapshot(
            generated_at=self._now(),
            summary=(
                "The connector command layer shows which market, macro, venue, and wallet integrations are production-ready, "
                "which ones are still demo-safe, and which ones still need credentials or cutover work."
            ),
            live_or_ready_count=live_or_ready_count,
            connectors=connectors,
        )

    def get_connector_diagnostics(self) -> list[ConnectorDiagnosticResult]:
        return [
            self.get_connector_diagnostic(connector.id)
            for connector in self.get_connector_control().connectors
        ]

    def get_connector_diagnostic(self, connector_id: str) -> ConnectorDiagnosticResult:
        normalized_id = connector_id.strip().lower()
        connector = next(
            (item for item in self.get_connector_control().connectors if item.id == normalized_id),
            None,
        )
        if connector is None:
            raise ValueError("Connector not found")

        checks: list[ConnectorDiagnosticCheck] = [
            self._connector_check(
                key="configuration",
                label="Configuration",
                status="pass" if connector.configured else ("warn" if connector.state == "planned" else "fail"),
                detail=(
                    f"{connector.label} has runtime configuration attached."
                    if connector.configured
                    else f"{connector.label} still needs its activation environment values."
                ),
            ),
            self._connector_check(
                key="readiness_score",
                label="Readiness score",
                status="pass" if connector.readiness_score >= 0.75 else ("warn" if connector.readiness_score >= 0.35 else "fail"),
                detail=f"Current readiness is {round(connector.readiness_score * 100)}%. Target for promotion is 75% or higher.",
            ),
            self._connector_check(
                key="runtime_state",
                label="Runtime state",
                status=(
                    "pass"
                    if connector.state in {"live", "ready"}
                    else ("warn" if connector.state in {"demo", "planned"} else "fail")
                ),
                detail=f"Runtime state is {connector.state}. Mode is {connector.mode}; source is {connector.source}.",
            ),
            self._connector_check(
                key="env_inventory",
                label="Environment inventory",
                status="pass" if connector.configured else ("warn" if connector.state == "planned" else "fail"),
                detail=(
                    f"Expected keys: {', '.join(connector.env_keys)}."
                    if connector.env_keys
                    else "No external environment keys are required for this connector."
                ),
            ),
        ]

        checks.extend(self._specific_connector_checks(connector))

        if connector.risk_level == "high":
            checks.append(
                self._connector_check(
                    key="high_risk_gate",
                    label="High-risk promotion gate",
                    status="pass" if connector.configured and connector.state in {"live", "ready"} else "blocked",
                    detail=(
                        "High-risk connectors require credentials, sandbox proof, and explicit operating limits before promotion."
                    ),
                )
            )
        elif connector.live_capable:
            checks.append(
                self._connector_check(
                    key="live_guardrail",
                    label="Live guardrail",
                    status="pass" if connector.state in {"live", "ready"} else "warn",
                    detail="Live-capable connector remains gated until readiness and fallback checks pass.",
                    required=False,
                )
            )

        blockers = [
            f"{check.label}: {check.detail}"
            for check in checks
            if check.required and check.status in {"fail", "blocked"}
        ]
        overall_status = self._connector_diagnostic_status(checks)
        ready_to_activate = not blockers and connector.configured and connector.readiness_score >= 0.75
        safe_to_promote = ready_to_activate and overall_status == "pass" and connector.state in {"live", "ready"}
        next_actions = blockers[:3] + list(connector.next_actions)

        return ConnectorDiagnosticResult(
            connector_id=connector.id,
            label=connector.label,
            generated_at=self._now(),
            overall_status=overall_status,
            ready_to_activate=ready_to_activate,
            safe_to_promote=safe_to_promote,
            checks=checks,
            blockers=blockers,
            next_actions=next_actions,
        )

    def _specific_connector_checks(self, connector: ConnectorStatusItem) -> list[ConnectorDiagnosticCheck]:
        checks: list[ConnectorDiagnosticCheck] = []
        connector_id = connector.id

        if connector_id == "stripe-billing-rail":
            required_values = {
                "BSM_FIAT_BILLING_PROVIDER=stripe": self.settings.fiat_billing_provider == "stripe",
                "BSM_STRIPE_PUBLISHABLE_KEY": bool(self.settings.stripe_publishable_key),
                "BSM_STRIPE_SECRET_KEY": bool(self.settings.stripe_secret_key),
                "BSM_STRIPE_WEBHOOK_SECRET": bool(self.settings.stripe_webhook_secret),
                "BSM_STRIPE_BASIC_PRICE_ID": bool(self.settings.stripe_basic_price_id),
            }
            missing = [key for key, present in required_values.items() if not present]
            checks.append(
                self._connector_check(
                    key="stripe_required_values",
                    label="Stripe required values",
                    status="pass" if not missing else "fail",
                    detail="All hosted Stripe billing values are present." if not missing else f"Missing: {', '.join(missing)}.",
                )
            )
            checks.append(
                self._connector_check(
                    key="hosted_payment_boundary",
                    label="Hosted payment boundary",
                    status="pass",
                    detail="Card entry stays inside Stripe Checkout and Portal; BITprivat does not collect card data directly.",
                    required=False,
                )
            )

        elif connector_id == "coinbase-onramp-rail":
            required_values = {
                "BSM_COINBASE_ONRAMP_API_KEY": bool(self.settings.coinbase_onramp_api_key),
                "BSM_COINBASE_ONRAMP_APP_ID": bool(self.settings.coinbase_onramp_app_id),
            }
            missing = [key for key, present in required_values.items() if not present]
            checks.append(
                self._connector_check(
                    key="coinbase_required_values",
                    label="Coinbase onramp values",
                    status="pass" if not missing else "fail",
                    detail="Coinbase hosted onramp credentials are present." if not missing else f"Missing: {', '.join(missing)}.",
                )
            )
            checks.append(
                self._connector_check(
                    key="crypto_kyc_boundary",
                    label="Hosted KYC boundary",
                    status="pass",
                    detail="Crypto funding must stay inside Coinbase or MoonPay hosted KYC/payment flows; internal custody remains disabled.",
                    required=False,
                )
            )
            backup_ready = bool(self.settings.coinbase_commerce_api_key or self.settings.moonpay_api_key)
            checks.append(
                self._connector_check(
                    key="backup_crypto_rail",
                    label="Backup crypto rail",
                    status="pass" if backup_ready else "warn",
                    detail=(
                        "A backup Coinbase Commerce or MoonPay key is configured."
                        if backup_ready
                        else "No backup crypto checkout rail is configured yet."
                    ),
                    required=False,
                )
            )

        elif connector_id == "cloudflare-edge-router":
            checks.append(
                self._connector_check(
                    key="canonical_https",
                    label="Canonical HTTPS",
                    status="pass" if self.settings.canonical_host and self.settings.force_https else "fail",
                    detail=(
                        f"Canonical host is {self.settings.canonical_host} with HTTPS enforced."
                        if self.settings.canonical_host and self.settings.force_https
                        else "Set BSM_CANONICAL_HOST and BSM_FORCE_HTTPS=true on the hosted deployment."
                    ),
                )
            )
            checks.append(
                self._connector_check(
                    key="edge_deploy_automation",
                    label="Edge deploy automation",
                    status="warn",
                    detail="Runtime cannot inspect GitHub repository secrets; keep CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN in GitHub Actions.",
                    required=False,
                )
            )

        elif connector_id == "desktop-shell":
            checks.append(
                self._connector_check(
                    key="desktop_shell_identity",
                    label="Desktop shell identity",
                    status="pass" if self.settings.desktop_app_framework != "none" and self.settings.desktop_bundle_id else "fail",
                    detail=(
                        f"{self.settings.desktop_app_framework} shell uses bundle ID {self.settings.desktop_bundle_id}."
                        if self.settings.desktop_app_framework != "none" and self.settings.desktop_bundle_id
                        else "Set BSM_DESKTOP_APP_FRAMEWORK and BSM_DESKTOP_BUNDLE_ID before packaging installers."
                    ),
                )
            )
            checks.append(
                self._connector_check(
                    key="desktop_signing",
                    label="Signing and distribution",
                    status="pass" if self.settings.apple_developer_team_id else "warn",
                    detail=(
                        "Apple developer team is configured for notarization planning."
                        if self.settings.apple_developer_team_id
                        else "Desktop installers still need signing/notarization setup before public distribution."
                    ),
                    required=False,
                )
            )

        elif connector_id == "hyperliquid-market-feed":
            hyperliquid_mode_active = self.settings.market_provider_mode in {"auto", "hyperliquid"}
            checks.append(
                self._connector_check(
                    key="hyperliquid_feed_mode",
                    label="Hyperliquid feed mode",
                    status="pass" if hyperliquid_mode_active else "fail",
                    detail=(
                        "Hyperliquid public feed is active through the auto market router."
                        if self.settings.market_provider_mode == "auto"
                        else f"Hyperliquid feed is active for {self.settings.hyperliquid_dex or 'the default universe'}."
                        if hyperliquid_mode_active
                        else "Keep this in research mode until BSM_MARKET_PROVIDER=auto or hyperliquid is set."
                    ),
                )
            )

        elif connector_id == "ibkr-brokerage-gateway":
            endpoint_configured = self.settings.ibkr_connection_mode != "disabled" and (
                bool(self.settings.ibkr_tws_host and self.settings.ibkr_tws_port)
                if self.settings.ibkr_connection_mode == "tws_gateway"
                else bool(self.settings.ibkr_client_portal_base_url)
            )
            account_configured = bool(self.settings.ibkr_account_id)
            endpoint_label = (
                f"{self.settings.ibkr_tws_host}:{self.settings.ibkr_tws_port}"
                if self.settings.ibkr_connection_mode == "tws_gateway"
                else self.settings.ibkr_client_portal_base_url
            )
            checks.append(
                self._connector_check(
                    key="ibkr_connection_mode",
                    label="IBKR connection mode",
                    status="pass" if endpoint_configured else "fail",
                    detail=(
                        f"IBKR is configured for {self.settings.ibkr_connection_mode} at {endpoint_label}."
                        if endpoint_configured
                        else "Set BSM_IBKR_CONNECTION_MODE to tws_gateway or client_portal and configure the matching endpoint."
                    ),
                )
            )
            checks.append(
                self._connector_check(
                    key="ibkr_account_id",
                    label="IBKR account ID",
                    status="pass" if account_configured else "fail",
                    detail=(
                        "An IBKR account ID is configured for routing account and position checks."
                        if account_configured
                        else "Set BSM_IBKR_ACCOUNT_ID after confirming the paper account shown by TWS, IB Gateway, or Client Portal Gateway."
                    ),
                )
            )
            checks.append(
                self._connector_check(
                    key="ibkr_read_only_default",
                    label="Read-only default",
                    status="pass" if self.settings.ibkr_read_only else "warn",
                    detail=(
                        "Read-only mode is active; account diagnostics can be built without order submission."
                        if self.settings.ibkr_read_only
                        else "Read-only mode is off. Use this only for paper-account order smoke tests until live controls are approved."
                    ),
                    required=False,
                )
            )
            checks.append(
                self._connector_check(
                    key="ibkr_live_trading_gate",
                    label="Live trading gate",
                    status="blocked" if not self.settings.ibkr_live_trading_enabled else "warn",
                    detail=(
                        "Live trading is disabled, which is the required default before legal, risk, and paper-trade verification."
                        if not self.settings.ibkr_live_trading_enabled
                        else "Live trading flag is enabled. Confirm this is intentional and backed by order limits, audit logs, and counsel-approved disclosures."
                    ),
                    required=False,
                )
            )
            checks.append(
                self._connector_check(
                    key="ibkr_market_data",
                    label="Market data entitlement",
                    status="pass" if self.settings.ibkr_market_data_subscribed else "warn",
                    detail=(
                        "Market data subscription flag is set; still verify entitlements inside the IBKR account."
                        if self.settings.ibkr_market_data_subscribed
                        else "Market data entitlements are not marked as verified. IBKR data access can depend on subscriptions and exchange fees."
                    ),
                    required=False,
                )
            )
            checks.append(
                self._connector_check(
                    key="ibkr_secret_boundary",
                    label="Credential boundary",
                    status="pass",
                    detail="BITprivat stores no IBKR password or 2FA secret; authentication must happen inside IBKR-operated software.",
                    required=False,
                )
            )

        elif connector_id == "kalshi-surfaces":
            kalshi_ready = bool(self.settings.kalshi_demo_key_id and self.settings.kalshi_demo_private_key_path)
            checks.append(
                self._connector_check(
                    key="kalshi_demo_credentials",
                    label="Kalshi demo credentials",
                    status="pass" if kalshi_ready else "fail",
                    detail=(
                        "Kalshi demo key ID and private key path are configured."
                        if kalshi_ready
                        else "Set BSM_KALSHI_DEMO_KEY_ID and BSM_KALSHI_DEMO_PRIVATE_KEY_PATH before enabling demo venue checks."
                    ),
                )
            )

        elif connector_id == "polymarket-intel":
            has_wallets = bool(self.settings.tracked_wallets)
            has_venue = "polymarket" in set(self.settings.venue_signal_providers)
            checks.append(
                self._connector_check(
                    key="polymarket_signal_surface",
                    label="Polymarket signal surface",
                    status="pass" if has_venue or self.settings.wallet_provider_mode == "polymarket" else "warn",
                    detail=(
                        "Polymarket signal or wallet mode is active."
                        if has_venue or self.settings.wallet_provider_mode == "polymarket"
                        else "Enable polymarket in BSM_VENUE_SIGNAL_PROVIDERS or BSM_WALLET_PROVIDER for live venue intelligence."
                    ),
                    required=False,
                )
            )
            checks.append(
                self._connector_check(
                    key="tracked_wallets",
                    label="Tracked public wallets",
                    status="pass" if has_wallets else "warn",
                    detail=(
                        f"{len(self.settings.tracked_wallets)} public wallets are configured for provenance weighting."
                        if has_wallets
                        else "Curate tracked public wallets before ranking smart-money profiles."
                    ),
                    required=False,
                )
            )

        elif connector_id == "signal-ingestion":
            has_live_source = self.settings.signal_provider_mode in {"rss", "reddit"} and bool(
                self.settings.rss_feed_urls or self.settings.reddit_client_id
            )
            checks.append(
                self._connector_check(
                    key="live_signal_source",
                    label="Live signal source",
                    status="pass" if has_live_source else "warn",
                    detail=(
                        "Live RSS or Reddit intake is configured."
                        if has_live_source
                        else "Signal intake is still demo-first; add RSS feeds or Reddit credentials for live collection."
                    ),
                    required=False,
                )
            )

        return checks

    @staticmethod
    def _connector_diagnostic_status(checks: list[ConnectorDiagnosticCheck]) -> str:
        required_checks = [check for check in checks if check.required]
        if any(check.status == "blocked" for check in required_checks):
            return "blocked"
        if any(check.status == "fail" for check in required_checks):
            return "fail"
        if any(check.status == "warn" for check in checks):
            return "warn"
        return "pass"

    @staticmethod
    def _connector_check(
        *,
        key: str,
        label: str,
        status: str,
        detail: str,
        required: bool = True,
    ) -> ConnectorDiagnosticCheck:
        return ConnectorDiagnosticCheck(
            key=key,
            label=label,
            status=status,
            detail=detail,
            required=required,
        )

    def get_infrastructure_readiness(self, provider_status: ProviderStatus | None = None) -> InfrastructureReadinessSnapshot:
        provider_status = provider_status or self.get_provider_status()
        database_ready = provider_status.database_backend == "postgresql"
        hosted_target = self.settings.deployment_target in {"render", "akash"}
        https_ready = bool(self.settings.canonical_host and self.settings.force_https)

        tasks = [
            InfrastructureTask(
                key="managed_database",
                label="Managed Database",
                state="ready" if database_ready else "attention",
                detail=(
                    f"Current backend is {provider_status.database_backend} targeting {provider_status.database_target}. "
                    + ("Durable managed storage is active." if database_ready else "Preview SQLite should be promoted to managed Postgres before monetization or heavier live integrations.")
                ),
                next_step=(
                    "Keep schema evolution flowing through the managed production database."
                    if database_ready
                    else "Create a Neon database, set BSM_DATABASE_URL, and redeploy Akash with the generated production manifest."
                ),
            ),
            InfrastructureTask(
                key="canonical_host",
                label="Canonical HTTPS Host",
                state="ready" if https_ready else "attention",
                detail=(
                    "Canonical host redirects and HTTPS headers are active."
                    if https_ready
                    else "The hosted experience should keep a canonical HTTPS app domain before broader launch."
                ),
                next_step=(
                    "Maintain the Cloudflare proxy and update the Akash ingress target after each redeploy."
                    if https_ready
                    else "Set BSM_CANONICAL_HOST and BSM_FORCE_HTTPS on the hosted environment."
                ),
            ),
            InfrastructureTask(
                key="separate_worker",
                label="Background Worker Path",
                state="ready" if hosted_target else "planned",
                detail=(
                    "The deployment target supports a separate worker process for scheduled refreshes."
                    if hosted_target
                    else "The local environment is fine for development, but production refreshes should run on a dedicated worker."
                ),
                next_step=(
                    "Enable the worker deployment after the database cutover is complete."
                    if hosted_target
                    else "Move the production app to a hosted target with separate web and worker surfaces."
                ),
            ),
            InfrastructureTask(
                key="legal_surface",
                label="Published Legal Surface",
                state="ready",
                detail="Terms, Privacy, and Risk Disclosure pages are now published inside the product shell.",
                next_step="Replace any placeholder company details with counsel-reviewed language before paid launch.",
            ),
        ]

        ready_count = sum(task.state == "ready" for task in tasks)
        return InfrastructureReadinessSnapshot(
            generated_at=self._now(),
            production_posture="ready" if ready_count == len(tasks) else "attention",
            summary=(
                "Public hosting is live. The biggest remaining production gate is durable Postgres storage; "
                "everything else should now be managed as controlled hardening instead of basic setup."
            ),
            database_backend=provider_status.database_backend,
            database_target=provider_status.database_target,
            tasks=tasks,
        )

    def get_production_cutover(self, provider_status: ProviderStatus | None = None) -> ProductionCutoverSnapshot:
        provider_status = provider_status or self.get_provider_status()
        current_backend = provider_status.database_backend
        current_target = provider_status.database_target
        source_path = str(self.settings.database_path)
        canonical_host = self.settings.canonical_host or "app.bitprivat.com"
        root_domain = (
            self.settings.canonical_redirect_hosts[0]
            if self.settings.canonical_redirect_hosts
            else ".".join(canonical_host.split(".")[-2:])
        )
        database_placeholder = "postgresql+psycopg://USER:PASSWORD@HOST/DBNAME?sslmode=require"
        backup_command = f'python -m api.app.jobs db-backup --source-path "{source_path}"'
        copy_command = (
            f'python -m api.app.jobs db-copy --source-path "{source_path}" '
            f'--target-url "{database_placeholder}"'
        )
        manifest_command = (
            f'.\\deploy\\akash\\prepare-bitprivat-neon.ps1 -DatabaseUrl "{database_placeholder}" '
            f'-CanonicalHost "{canonical_host}" -RootDomain "{root_domain}"'
        )

        using_postgres = current_backend == "postgresql"
        hosted_sqlite_preview = (
            current_backend == "sqlite"
            and self.settings.deployment_target == "akash"
            and str(self.settings.database_path).startswith("/tmp/")
        )

        steps = [
            ProductionCutoverStep(
                key="backup",
                label="Back Up Current SQLite State",
                state="ready" if using_postgres else "attention",
                detail=(
                    "Managed Postgres is already active, so SQLite backup is not the primary concern."
                    if using_postgres
                    else (
                        "Create a safe SQLite backup before any copy or redeploy work if the source database is local and accessible."
                    )
                ),
                command=None if using_postgres or hosted_sqlite_preview else backup_command,
            ),
            ProductionCutoverStep(
                key="provision_neon",
                label="Provision Managed Postgres",
                state="ready" if using_postgres else "attention",
                detail=(
                    "A durable Postgres target is already configured for the production app."
                    if using_postgres
                    else "Create a Neon production database and capture the pooled psycopg connection string with sslmode=require."
                ),
                command=None,
            ),
            ProductionCutoverStep(
                key="copy_data",
                label="Copy Durable Data Into Postgres",
                state="ready" if using_postgres else "attention",
                detail=(
                    "Application data already lives on Postgres."
                    if using_postgres
                    else (
                        "Use the built-in db-copy job when the SQLite source is local. "
                        "If the current Akash preview data only exists inside the container, treat it as disposable unless you export it deliberately."
                    )
                ),
                command=None if using_postgres or hosted_sqlite_preview else copy_command,
            ),
            ProductionCutoverStep(
                key="generate_manifest",
                label="Generate the Akash Production Manifest",
                state="ready" if using_postgres else "attention",
                detail=(
                    "The hosted environment should point Akash at the managed database URL and preserve the canonical domain."
                ),
                command=manifest_command,
            ),
            ProductionCutoverStep(
                key="redeploy_and_dns",
                label="Redeploy and Confirm Cloudflare Target",
                state="planned" if using_postgres else "attention",
                detail=(
                    "Redeploy Akash with the generated manifest, then update the Cloudflare app CNAME if Akash issues a new ingress hostname."
                ),
                command=None,
            ),
            ProductionCutoverStep(
                key="verify",
                label="Verify Health, Dashboard, and Simulation",
                state="planned" if using_postgres else "attention",
                detail=(
                    "Confirm health, dashboard, simulation, and legal pages after the database-backed redeploy."
                ),
                command=None,
            ),
        ]

        posture = "ready" if using_postgres else "attention"
        source_data_note = (
            "Managed Postgres is already the system of record."
            if using_postgres
            else (
                "The current deployment is still SQLite-based. "
                + (
                    "Because the hosted Akash preview stores SQLite inside the running container, treat preview data as disposable unless you export it from the provider environment first."
                    if hosted_sqlite_preview
                    else "Because the SQLite file is locally addressable, you can back it up and copy it forward with the included jobs."
                )
            )
        )

        return ProductionCutoverSnapshot(
            generated_at=self._now(),
            posture=posture,
            current_backend=current_backend,
            current_target=current_target,
            target_backend="postgresql",
            summary=(
                "Move the live platform to managed Postgres before enabling heavier payments, live connectors, or long-lived worker automation."
                if not using_postgres
                else "The durable database cutover is complete; future changes should flow through managed Postgres migrations."
            ),
            source_data_note=source_data_note,
            verification_urls=[
                f"https://{canonical_host}/health",
                f"https://{canonical_host}/dashboard",
                f"https://{canonical_host}/simulation",
                f"https://{canonical_host}/terms",
            ],
            steps=steps,
        )

    def _connector_item(
        self,
        *,
        connector_id: str,
        label: str,
        category: str,
        mode: str,
        source: str,
        configured: bool,
        live_capable: bool,
        ready: bool,
        fallback_active: bool,
        activation_phase: str = "Selected",
        owner: str = "Platform",
        risk_level: str = "medium",
        target_surface: str,
        env_keys: list[str],
        next_actions: list[str],
        app_url: str | None = None,
    ) -> ConnectorStatusItem:
        normalized_mode = str(mode or "planned").lower()
        normalized_source = str(source or "internal")

        if ready and live_capable and not fallback_active:
            state: str = "live"
        elif ready:
            state = "ready"
        elif fallback_active or (configured and not ready):
            state = "attention"
        elif normalized_mode in {"demo", "planned", "internal"} or normalized_source.lower().startswith("demo"):
            state = "demo" if normalized_mode != "planned" else "planned"
        else:
            state = "attention"

        posture = "Fallback guardrails are active." if fallback_active else ("Credentials are configured." if configured else "Credentials are still missing.")
        readiness_note = "Live-capable connector." if live_capable else "Demo-safe or manually promoted connector."
        summary = f"{normalized_source} feeds {target_surface}. {posture} {readiness_note}"
        readiness_score = self._connector_readiness_score(
            configured=configured,
            live_capable=live_capable,
            ready=ready,
            fallback_active=fallback_active,
        )

        return ConnectorStatusItem(
            id=connector_id,
            label=label,
            category=category,
            state=state,
            mode=mode,
            source=source,
            configured=configured,
            live_capable=live_capable,
            readiness_score=readiness_score,
            activation_phase=activation_phase,
            owner=owner,
            risk_level=risk_level,
            summary=summary,
            target_surface=target_surface,
            env_keys=env_keys,
            next_actions=next_actions,
            app_url=app_url,
        )

    @staticmethod
    def _connector_readiness_score(
        *,
        configured: bool,
        live_capable: bool,
        ready: bool,
        fallback_active: bool,
    ) -> float:
        score = 0.18
        if configured:
            score += 0.28
        if live_capable:
            score += 0.18
        if ready:
            score += 0.28
        if fallback_active:
            score -= 0.18
        return round(max(0.0, min(1.0, score)), 2)

    @staticmethod
    def _readiness_level_from_counts(completed: int, total: int, *, live: bool = False) -> str:
        if live:
            return "live"
        if total > 0 and completed >= total:
            return "ready"
        if completed > 0:
            return "building"
        return "selected"

    def get_launch_readiness(self, provider_status: ProviderStatus | None = None) -> LaunchReadinessSnapshot:
        provider_status = provider_status or self.get_provider_status()
        terms_url = self.settings.terms_url or "/terms"
        privacy_url = self.settings.privacy_url or "/privacy"
        risk_disclosure_url = self.settings.risk_disclosure_url or "/risk"

        stripe_completed = sum(
            bool(value)
            for value in (
                self.settings.stripe_publishable_key,
                self.settings.stripe_secret_key,
                self.settings.stripe_webhook_secret,
                self.settings.stripe_basic_price_id,
            )
        )
        fiat_track = LaunchReadinessTrack(
            key="fiat_onboarding",
            label="Fiat Card Onboarding",
            level=self._readiness_level_from_counts(stripe_completed, 4),
            headline="Hosted card onboarding should run through Stripe Checkout and Billing.",
            summary=(
                "Use Stripe-hosted checkout, subscriptions, customer portal, and tax so the platform can sell plans "
                "without bringing raw card data onto your own servers."
            ),
            recommended_provider="Stripe Checkout + Billing + Customer Portal + Stripe Tax",
            target_release="Phase 1 - retail subscriptions and enterprise invoicing",
            next_actions=[
                "Create Starter, Pro, and Enterprise price IDs in Stripe.",
                "Add webhook handlers for checkout.session.completed, invoice.paid, and customer.subscription.updated.",
                "Map paid plans to entitlements inside the workspace and API layer.",
                "Turn on Stripe Tax and define VAT handling before EU launch.",
            ],
            blockers=[
                message
                for condition, message in (
                    (not self.settings.stripe_publishable_key, "Stripe publishable key is not configured."),
                    (not self.settings.stripe_secret_key, "Stripe secret key is not configured."),
                    (not self.settings.stripe_webhook_secret, "Stripe webhook signing secret is not configured."),
                    (not self.settings.stripe_basic_price_id, "Starter or Basic Stripe price ID is not configured."),
                )
                if condition
            ],
        )

        crypto_completed = int(bool(self.settings.coinbase_onramp_api_key)) + int(bool(self.settings.coinbase_onramp_app_id))
        crypto_completed += int(bool(self.settings.coinbase_commerce_api_key or self.settings.moonpay_api_key))
        crypto_track = LaunchReadinessTrack(
            key="crypto_onboarding",
            label="Crypto Payment Onboarding",
            level=self._readiness_level_from_counts(crypto_completed, 3),
            headline="Fund wallets and optional crypto checkout through hosted third-party rails first.",
            summary=(
                "Primary path should be Coinbase-hosted Onramp for funded wallets and optional Coinbase Commerce or MoonPay "
                "for controlled crypto-denominated settlement, while avoiding direct custody."
            ),
            recommended_provider="Coinbase Onramp primary, Coinbase Commerce or MoonPay secondary",
            target_release="Phase 2 - wallet funding and crypto-denominated credits",
            next_actions=[
                "Launch Coinbase-hosted Onramp first and keep KYC inside the provider flow.",
                "Use crypto checkout only for account credits or enterprise settlement, not primary SaaS subscriptions.",
                "Add webhook ledgering for onramp completions and credit assignment.",
                "Write explicit user disclosures covering volatility, fees, and third-party provider terms.",
            ],
            blockers=[
                message
                for condition, message in (
                    (not self.settings.coinbase_onramp_api_key, "Coinbase Onramp API key is not configured."),
                    (not self.settings.coinbase_onramp_app_id, "Coinbase Onramp app ID is not configured."),
                    (not (self.settings.coinbase_commerce_api_key or self.settings.moonpay_api_key), "No backup crypto rail is configured for checkout or regional coverage."),
                )
                if condition
            ],
        )

        live_connector_count = (
            int(provider_status.market_provider_live_capable)
            + int(provider_status.signal_provider_live_capable)
            + int(provider_status.macro_provider_live_capable)
            + int(provider_status.wallet_provider_live_capable)
            + int(provider_status.social_discovery_live_capable)
            + sum(1 for provider in provider_status.venue_signal_providers if provider.live_capable)
        )
        connector_track = LaunchReadinessTrack(
            key="api_connectors",
            label="API Connectors",
            level=self._readiness_level_from_counts(
                min(live_connector_count, 5),
                5,
                live=live_connector_count >= 5 and not (
                    provider_status.market_fallback_active
                    or provider_status.signal_fallback_active
                    or provider_status.macro_fallback_active
                    or provider_status.wallet_fallback_active
                    or provider_status.social_discovery_fallback_active
                ),
            ),
            headline="Market intelligence connectors are already online; revenue and operations connectors come next.",
            summary=(
                f"{live_connector_count} live-capable data connectors are already exposed across market, signal, macro, "
                "wallet, social discovery, and venue layers. Next connectors should add billing webhooks, onramp callbacks, CRM alerts, and exports."
            ),
            recommended_provider="Hyperliquid, Polymarket, Kalshi, FRED, Stripe webhooks, Coinbase webhooks",
            target_release="Continuous track - data, billing, and operations",
            next_actions=[
                "Keep public market connectors live and add Stripe and Coinbase webhook ingestion as first private connectors.",
                "Add connector health checks for billing, onramp, and outbound webhook destinations.",
                "Publish a connector inventory with owner, SLA, retry policy, and fallback path.",
            ],
            blockers=[
                message
                for condition, message in (
                    (not provider_status.market_provider_live_capable, "Primary market data connector is still demo-only."),
                    (not provider_status.signal_provider_live_capable, "Primary signal connector is still demo-only."),
                    (not provider_status.wallet_provider_live_capable, "Wallet intelligence is not yet live-configured."),
                )
                if condition
            ],
        )

        dashboard_track = LaunchReadinessTrack(
            key="dashboard_redesign",
            label="Dashboard Redesign",
            level="building",
            headline="The command-center visual system is live; commercial conversion surfaces are the next layer.",
            summary=(
                "The dashboard already functions as a live command center. The next redesign pass should add onboarding funnels, "
                "plan comparison states, connector health drilldowns, payment activation panels, and enterprise-ready reporting cards."
            ),
            recommended_provider="Design system refresh inside the existing FastAPI static frontend",
            target_release="Phase 1 - conversion-focused command center",
            next_actions=[
                "Add a monetization rail section with pricing, onboarding status, and entitlement state.",
                "Add operator drilldowns for connector health, billing events, and legal blockers.",
                "Introduce a cleaner onboarding path for retail, enterprise, and desktop install users.",
            ],
            blockers=[
                "The current dashboard does not yet surface subscription state or payment-provider events.",
                "Commercial onboarding and legal notices are not yet part of the in-product flow.",
            ],
        )

        desktop_completed = int(self.settings.desktop_app_framework != "none") + int(bool(self.settings.desktop_bundle_id))
        desktop_completed += int(bool(self.settings.apple_developer_team_id or self.settings.windows_distribution_channel == "store"))
        desktop_track = LaunchReadinessTrack(
            key="desktop_apps",
            label="Windows and macOS App",
            level=self._readiness_level_from_counts(desktop_completed, 3),
            headline="Wrap the hosted dashboard in a signed desktop shell before adding local-side features.",
            summary=(
                "Use a Tauri desktop shell around the hosted product, open payment flows in the system browser, and distribute "
                "through Microsoft Store or signed direct download on Windows plus Developer ID and notarized builds on macOS."
            ),
            recommended_provider="Tauri desktop shell, Microsoft Store MSIX, Apple Developer ID notarization",
            target_release="Phase 3 - installable desktop distribution",
            next_actions=[
                "Initialize a Tauri workspace that points to the hosted dashboard domain.",
                "Use system-browser payment redirects rather than embedding sensitive payment flows inside the webview.",
                "Prepare Windows MSIX packaging and Apple notarization CI once the shell is stable.",
            ],
            blockers=[
                message
                for condition, message in (
                    (self.settings.desktop_app_framework == "none", "Desktop shell framework is not set."),
                    (not self.settings.desktop_bundle_id, "Desktop bundle identifier is not configured."),
                    (not self.settings.apple_developer_team_id, "Apple Developer team ID is not configured for macOS signing and notarization."),
                )
                if condition
            ],
        )

        legal_completed = sum(
            bool(value)
            for value in (
                self.settings.legal_entity_name,
                self.settings.legal_primary_jurisdiction,
                self.settings.privacy_contact_email,
                terms_url,
                privacy_url,
                risk_disclosure_url,
                self.settings.aml_program_owner,
            )
        )
        legal_track = LaunchReadinessTrack(
            key="legal_compliance",
            label="Legal and Compliance",
            level=self._readiness_level_from_counts(legal_completed, 7),
            headline="Keep the product research-only until counsel approves the commercial perimeter.",
            summary=(
                "Stay on the analytics and alerting side until counsel signs off on terms, privacy, disclosures, payments posture, "
                "crypto rails, sanctions handling, and any copy-trading or investment-advice boundary questions."
            ),
            recommended_provider="External fintech, payments, privacy, and securities counsel",
            target_release="Must be complete before paid production launch",
            next_actions=[
                "Finalize Terms of Service, Privacy Policy, Cookie Notice, and risk disclosures.",
                "Document that the product does not custody funds and is not auto-executing customer trades.",
                "Run US and EU counsel review for MSB, MiCA, MiFID, and investment-advice perimeter analysis.",
                "Define AML, sanctions, complaints, and incident-response ownership.",
            ],
            blockers=[
                message
                for condition, message in (
                    (not self.settings.legal_entity_name, "Operating legal entity is not recorded in configuration."),
                    (not self.settings.legal_primary_jurisdiction, "Primary operating jurisdiction is not recorded."),
                    (not self.settings.privacy_contact_email, "Privacy contact email is not configured."),
                    (not terms_url, "Terms of Service URL is missing."),
                    (not privacy_url, "Privacy Policy URL is missing."),
                    (not risk_disclosure_url, "Risk disclosure URL is missing."),
                    (not self.settings.aml_program_owner, "AML or sanctions ownership is not assigned."),
                )
                if condition
            ],
        )

        tracks = [
            fiat_track,
            crypto_track,
            connector_track,
            dashboard_track,
            desktop_track,
            legal_track,
        ]
        ready_or_live = sum(track.level in {"ready", "live"} for track in tracks)
        any_building = any(track.level == "building" for track in tracks)
        any_live = any(track.level == "live" for track in tracks)
        overall_level = "selected"
        if any_live or ready_or_live >= 3:
            overall_level = "ready"
        elif any_building or ready_or_live:
            overall_level = "building"

        return LaunchReadinessSnapshot(
            generated_at=self._now(),
            level=overall_level,
            summary=(
                "Commercial expansion is in motion: live market connectors are already operating, the dashboard redesign is active, "
                "and the next controlled gates are fiat billing, crypto onboarding, signed desktop distribution, and legal readiness."
            ),
            tracks=tracks,
        )

    def get_business_model_strategy(self) -> BusinessModelSnapshot:
        return BusinessModelSnapshot(
            generated_at=self._now(),
            source_deck="BITprivat_Investor_SaaS_Clean_v2.pptx",
            thesis=(
                "BITprivat is an autonomous trading workflow SaaS for event markets and perpetuals: one shared intelligence engine, "
                "two commercial products, and a constrained self-improvement loop that makes trading automation easier to install, "
                "easier to trust, and more adaptive over time."
            ),
            wedge=(
                "The wedge is setup friction and decision fatigue. Users connect venues and choose a risk profile; the engine selects "
                "a pre-tested setup, monitors market and social inputs, and retunes only inside approved guardrails."
            ),
            engine_workflow=[
                "Ingest market, wallet, social, macro, and venue data across Polymarket, Hyperliquid, Kalshi, and future connectors.",
                "Score sources with AdvisorRank so creator, trader, and data-provider provenance affects signal confidence.",
                "Simulate strategy templates and parameter ranges before any production deployment.",
                "Deploy selected templates through retail or enterprise workflows with auto-pause and audit visibility.",
                "Retune approved parameters with DynaTune using live execution, slippage, and signal feedback.",
            ],
            products=[
                BusinessModelProduct(
                    key="retail_autopilot",
                    name="BITprivat Autopilot",
                    segment="Retail SaaS",
                    pricing_model="$79-299/month plus premium packs",
                    buyer="Power retail traders, prediction-market communities, creator audiences, and advanced crypto users.",
                    positioning=(
                        "A one-click trading automation cockpit for users who want pre-tested strategy packs, live dashboards, "
                        "paper/live separation, auto-pause controls, and clear model confidence."
                    ),
                    core_capabilities=[
                        "Wallet/API connection onboarding",
                        "Pre-tested strategy packs",
                        "Live portfolio and prediction dashboards",
                        "Auto-pause, risk profile, and paper-first controls",
                        "Premium signal and advisor packs",
                    ],
                    expansion_paths=[
                        "Community bundles",
                        "Team seats for trading groups",
                        "Creator-led distribution",
                        "Premium simulations and export packs",
                    ],
                    risk_controls=[
                        "No promised returns",
                        "Paper-trading default for unverified users",
                        "Risk disclosures and model confidence labels",
                    ],
                ),
                BusinessModelProduct(
                    key="enterprise_os",
                    name="BITprivat Enterprise OS",
                    segment="Enterprise SaaS",
                    pricing_model="$40k-250k ARR plus usage/API modules",
                    buyer="Funds, research teams, venues, brokers, market makers, and infrastructure partners.",
                    positioning=(
                        "A private automation and intelligence operating system with RBAC, approvals, audit logs, private deployment, "
                        "strategy registry, white-label surfaces, and API access."
                    ),
                    core_capabilities=[
                        "Role-based access control",
                        "Approval workflows and audit logs",
                        "Private cloud, VPC, or on-prem deployment path",
                        "Strategy registry and versioned scorecards",
                        "White-label dashboards and APIs",
                    ],
                    expansion_paths=[
                        "Private data connectors",
                        "Custom strategy review workflows",
                        "Execution API usage",
                        "Venue and broker distribution partnerships",
                    ],
                    risk_controls=[
                        "Enterprise compliance review",
                        "Approval gates before execution",
                        "Auditability and exportable evidence trails",
                    ],
                ),
            ],
            revenue_streams=[
                BusinessModelRevenueStream(
                    key="retail_subscription",
                    label="Retail subscriptions",
                    model="Monthly SaaS",
                    detail="Tiered access to Autopilot, dashboards, simulations, risk controls, and selected connectors.",
                    priority="Launch wedge",
                ),
                BusinessModelRevenueStream(
                    key="premium_signal_packs",
                    label="Premium signal and advisor packs",
                    model="Add-on subscription",
                    detail="Paid access to higher-grade AdvisorRank lists, social signal bundles, and specialized market packs.",
                    priority="Expansion",
                ),
                BusinessModelRevenueStream(
                    key="team_community",
                    label="Team seats and community bundles",
                    model="Seat-based SaaS",
                    detail="Multi-user workspaces for trading groups, creator communities, and research pods.",
                    priority="Expansion",
                ),
                BusinessModelRevenueStream(
                    key="enterprise_arr",
                    label="Enterprise ARR",
                    model="Annual contracts",
                    detail="Private deployment, RBAC, audit logs, strategy registry, custom support, and governance workflows.",
                    priority="Defensibility",
                ),
                BusinessModelRevenueStream(
                    key="api_usage",
                    label="White-label and API usage",
                    model="Usage-based",
                    detail="Usage fees for embedded intelligence, connector calls, scorecard APIs, and partner-branded dashboards.",
                    priority="Platform scale",
                ),
                BusinessModelRevenueStream(
                    key="performance_linked_modules",
                    label="Selective performance-linked modules",
                    model="Optional rev-share",
                    detail="Only after legal review, proper disclosures, and customer-specific approvals; never positioned as fixed returns.",
                    priority="Controlled upside",
                ),
            ],
            strategy_families=[
                BusinessModelStrategyFamily(
                    key="event_dislocation_scanner",
                    label="Event dislocation scanner",
                    description="Find probability gaps between news, market pricing, macro context, and prediction-market order books.",
                    monetization_role="Core retail/enterprise signal family",
                    required_data=["Prediction-market order books", "News/social context", "Macro calendar", "Venue liquidity"],
                    enabled_by=["Polymarket/Kalshi connectors", "Firecrawl/Tavily-style web ingestion", "Strategy Lab backtests"],
                ),
                BusinessModelStrategyFamily(
                    key="social_momentum_fade",
                    label="Social momentum and fade",
                    description="Track viral narratives, creator velocity, and sentiment exhaustion to decide follow or fade posture.",
                    monetization_role="Premium signal pack and creator distribution wedge",
                    required_data=["X/Telegram/Discord/YouTube/Substack/news", "Creator history", "Market reaction windows"],
                    enabled_by=["SocialPulse", "AdvisorRank", "Signal provenance scoring"],
                ),
                BusinessModelStrategyFamily(
                    key="cross_venue_hedge",
                    label="Cross-venue hedge sleeve",
                    description="Use event markets, perpetuals, and spot context to reduce directional risk or express relative-value views.",
                    monetization_role="Enterprise and advanced retail module",
                    required_data=["Hyperliquid perps", "Prediction markets", "Reference spot markets", "Funding/liquidity data"],
                    enabled_by=["Hyperliquid connector", "Paper execution venues", "Edge scoring"],
                ),
                BusinessModelStrategyFamily(
                    key="spread_capture_micro_mm",
                    label="Spread capture and micro market making",
                    description="Target small spreads and depth imbalances with tight risk limits, inventory caps, and auto-pause logic.",
                    monetization_role="Enterprise execution and API module",
                    required_data=["Order book depth", "Fees", "Slippage", "Latency snapshots"],
                    enabled_by=["Venue adapters", "Execution telemetry", "Approval gates"],
                ),
                BusinessModelStrategyFamily(
                    key="advisor_follow_meta",
                    label="Advisor-follow meta layer",
                    description="Follow or fade ranked traders, wallets, and creators based on hit rate, timeliness, impact, and decay.",
                    monetization_role="Moat data product and premium pack",
                    required_data=["Wallet history", "Creator posts", "Prediction outcomes", "Timeliness metadata"],
                    enabled_by=["AdvisorRank", "Wallet intelligence", "Leaderboard provenance"],
                ),
                BusinessModelStrategyFamily(
                    key="template_rotation",
                    label="Template rotation",
                    description="Rotate among approved strategy templates when market regime, signal quality, or venue liquidity changes.",
                    monetization_role="Retention driver and enterprise governance feature",
                    required_data=["Backtest results", "Live scorecards", "Regime labels", "Risk-profile constraints"],
                    enabled_by=["DynaTune", "Strategy Lab", "Strategy registry"],
                ),
            ],
            moat_loop=[
                BusinessModelMoatStep(
                    key="socialpulse_ingest",
                    label="SocialPulse ingestion",
                    description="Monitor social, creator, news, and venue signals across fragmented information sources.",
                    output="Fresh signal graph with provenance and timeliness metadata.",
                ),
                BusinessModelMoatStep(
                    key="advisor_rank",
                    label="AdvisorRank scoring",
                    description="Score traders, creators, wallets, and advisors by hit rate, timeliness, impact, and decay.",
                    output="Trusted source weights that affect leaderboard and strategy confidence.",
                ),
                BusinessModelMoatStep(
                    key="template_matching",
                    label="Template matching",
                    description="Match signals and market regimes to approved strategy templates instead of free-form execution.",
                    output="Safer strategy selection with explainable playbooks.",
                ),
                BusinessModelMoatStep(
                    key="execution_feedback",
                    label="Execution feedback",
                    description="Measure fills, slippage, volatility, and market response after paper or live deployment.",
                    output="Evidence trail for promotion, demotion, or pause decisions.",
                ),
                BusinessModelMoatStep(
                    key="dynatune_retune",
                    label="DynaTune retuning",
                    description="Adjust only approved parameters inside governance limits using live signal and execution outcomes.",
                    output="Constrained improvement loop that compounds data advantage without uncontrolled behavior.",
                ),
            ],
            go_to_market=[
                "Retail starts with power users, prediction-market communities, creators, referrals, and a paper-first trust funnel.",
                "Enterprise starts with data, alerting, and scorecards, then expands into execution, white-label, and API workflows.",
                "Distribution partnerships can come from funds, research shops, brokers, venues, and infrastructure providers.",
                "Retail creates velocity, usage data, and market feedback; enterprise creates higher ACV, lower churn, and defensibility.",
            ],
            investor_model=[
                "One engine supports two products, reducing duplicate engineering and increasing reuse of connectors, scoring, and simulations.",
                "Gross margin should improve as reusable data pipelines, scorecards, and templates scale across both segments.",
                "Capital is directed into engineering, signal stack, enterprise readiness, security, and compliance rather than return guarantees.",
                "The investor story is retention, expansion, trusted automation, and platform data advantage, not fixed monthly performance claims.",
            ],
            team_plan=[
                BusinessModelTeamRole(
                    key="ceo_product",
                    label="CEO/Product",
                    responsibility="Own narrative, product direction, customer discovery, fundraising, and roadmap tradeoffs.",
                    timing="Now",
                ),
                BusinessModelTeamRole(
                    key="quant_strategy",
                    label="Quant/Strategy Lead",
                    responsibility="Design templates, backtests, risk rules, and promotion/demotion scorecards.",
                    timing="Months 0-6",
                ),
                BusinessModelTeamRole(
                    key="ml_data",
                    label="ML/Data Lead",
                    responsibility="Build SocialPulse, AdvisorRank, feature pipelines, and signal quality evaluation.",
                    timing="Months 0-9",
                ),
                BusinessModelTeamRole(
                    key="backend_integrations",
                    label="Backend/Integrations",
                    responsibility="Own venue connectors, APIs, execution telemetry, auth, billing, and enterprise surfaces.",
                    timing="Months 0-12",
                ),
                BusinessModelTeamRole(
                    key="infra_security",
                    label="Infra/Security",
                    responsibility="Harden deployment, secrets, observability, data retention, backups, and customer isolation.",
                    timing="Months 3-12",
                ),
                BusinessModelTeamRole(
                    key="frontend_ux",
                    label="Frontend/UX",
                    responsibility="Make dashboard, Strategy Lab, onboarding, and enterprise review flows intuitive and credible.",
                    timing="Months 0-12",
                ),
                BusinessModelTeamRole(
                    key="growth_community",
                    label="Growth/Community",
                    responsibility="Run retail waitlist, creator partnerships, education, referrals, and feedback loops.",
                    timing="Months 6-18",
                ),
                BusinessModelTeamRole(
                    key="legal_compliance",
                    label="Legal/Compliance Advisor",
                    responsibility="Review disclosures, execution boundaries, marketing claims, KYC/AML touchpoints, and enterprise terms.",
                    timing="Always-on advisor",
                ),
            ],
            milestones=[
                BusinessModelMilestone(
                    horizon="0-6 months",
                    label="Trusted MVP and paper-first launch",
                    target_metrics=[
                        "Autopilot onboarding flow live",
                        "Strategy Lab exports working",
                        "Polymarket, Kalshi, and Hyperliquid connectors visible",
                        "First creator/community pilot cohort",
                    ],
                    capital_use="Engineering, UX, signal ingestion, and legal-safe onboarding.",
                ),
                BusinessModelMilestone(
                    horizon="6-12 months",
                    label="Retention and enterprise pilots",
                    target_metrics=[
                        "Retail subscription launch",
                        "5-10 enterprise pilots",
                        "AdvisorRank scorecards trusted by users",
                        "DynaTune parameter governance live",
                    ],
                    capital_use="Data/ML, enterprise readiness, security, and customer success.",
                ),
                BusinessModelMilestone(
                    horizon="12-18 months",
                    label="Scale proof and fundable expansion",
                    target_metrics=[
                        "Repeatable retail activation channel",
                        "Enterprise conversion path from alerting to execution/API",
                        "Improving gross margin from shared engine reuse",
                        "Auditable model scorecards and compliance artifacts",
                    ],
                    capital_use="Connector depth, reliability, infrastructure, and go-to-market experiments.",
                ),
            ],
            seed_raise="$1.5M-2.0M seed for roughly 18 months of runway.",
            compliance_guardrails=[
                "Position the product as research, analytics, automation tooling, simulations, and optional execution infrastructure.",
                "Do not promise guaranteed returns or fixed monthly profits.",
                "Separate paper trading, signal research, and live execution clearly in UI and legal pages.",
                "Use approvals, audit logs, risk disclosures, and auto-pause controls before performance-linked modules.",
                "Review payment, KYC/AML, investment-advice, and jurisdiction rules with counsel before live-money expansion.",
            ],
            next_build_priorities=[
                "Make business model and investor strategy visible on the public product page.",
                "Expose structured business-model data through the API for pitch, dashboard, and partner surfaces.",
                "Tie Strategy Lab outputs to strategy-family scorecards.",
                "Add enterprise pilot packaging: RBAC, audit exports, private connector setup, and review checklists.",
                "Keep compliance wording strict: software value, trust, transparency, and adaptive workflows instead of return promises.",
            ],
        )

    def get_dashboard_snapshot(self, user_slug: str) -> DashboardSnapshot:
        cache_key = user_slug or self.settings.default_user_slug
        cached_snapshot = self.dashboard_snapshot_cache.get(cache_key)
        if self._cache_is_fresh(cached_snapshot, ttl_seconds=20):
            return cached_snapshot[1]
        if self._use_fast_public_snapshots() and cache_key == self.settings.default_user_slug:
            return self._get_fast_public_dashboard_snapshot(cache_key)

        repository = BotSocietyRepository(self.database)
        provider_status = self.get_provider_status()
        latest_assets = repository.list_latest_market_snapshots()
        latest_asset_map = {row["asset"]: row for row in latest_assets}
        recent_signals = repository.list_recent_signals(limit=120)
        recent_prediction_rows = repository.list_predictions(limit=10)
        all_predictions = repository.list_predictions(limit=500)
        pending_predictions = [row for row in all_predictions if row["status"] == "pending"]
        asset_symbols = sorted({str(row["asset"]) for row in latest_assets})
        latest_operation = self._latest_operation(repository)
        leaderboard = self.get_leaderboard(user_slug)
        leaderboard_map = {bot.slug: bot for bot in leaderboard}
        if self._use_fast_public_snapshots():
            notification_health = self._lightweight_notification_health()
            alert_inbox = self._lightweight_alert_inbox()
        else:
            notification_health = self.get_notification_health(user_slug)
            alert_inbox = self.get_alert_inbox(user_slug)
        macro_snapshot = self.get_macro_snapshot(repository)
        wallet_snapshot = self.get_wallet_intelligence()
        edge_snapshot = self.get_edge_snapshot(
            repository,
            wallet_snapshot=wallet_snapshot,
            macro_snapshot=macro_snapshot,
            latest_assets=latest_assets,
            recent_signals=recent_signals,
        )
        system_pulse = self.get_system_pulse(
            repository,
            provider_status=provider_status,
            notification_health=notification_health if user_slug == self.settings.default_user_slug else None,
            recent_signals=recent_signals,
            latest_assets=latest_assets,
            pending_predictions=pending_predictions,
        )
        paper_venues = self.get_paper_venues()
        snapshot = DashboardSnapshot(
            summary=self.get_summary(
                user_slug,
                repository=repository,
                bot_summaries=leaderboard,
                predictions=all_predictions,
                assets=asset_symbols,
                signals=recent_signals,
                latest_run=latest_operation.model_dump() if latest_operation else None,
            ),
            assets=[self._to_asset_model(row) for row in latest_assets],
            leaderboard=leaderboard,
            recent_predictions=self._build_prediction_views(repository, recent_prediction_rows),
            recent_signals=[self._to_signal_model(row) for row in recent_signals[:8]],
            system_pulse=system_pulse,
            macro_snapshot=macro_snapshot,
            wallet_intelligence=wallet_snapshot,
            edge_snapshot=edge_snapshot,
            paper_trading=self.get_paper_trading_snapshot(
                user_slug,
                repository=repository,
                latest_assets=latest_asset_map,
            ),
            paper_venues=paper_venues,
            social_trading=self.get_social_trading_snapshot(user_slug, repository),
            latest_operation=latest_operation,
            auth_session=AuthSessionSnapshot(authenticated=user_slug != self.settings.default_user_slug, user=self._to_user_identity(repository.get_user(user_slug)) if user_slug != self.settings.default_user_slug else None),
            user_profile=self.get_user_profile(
                user_slug,
                repository=repository,
                leaderboard_map=leaderboard_map,
                alert_inbox=alert_inbox,
            ),
            notification_health=notification_health,
            provider_status=provider_status,
            launch_readiness=self.get_launch_readiness(provider_status=provider_status),
            connector_control=self.get_connector_control(provider_status=provider_status, paper_venues=paper_venues),
            infrastructure_readiness=self.get_infrastructure_readiness(provider_status=provider_status),
            production_cutover=self.get_production_cutover(provider_status=provider_status),
            business_model=self.get_business_model_strategy(),
        )
        self.dashboard_snapshot_cache[cache_key] = (datetime.now(timezone.utc), snapshot)
        return snapshot

    def get_landing_snapshot(self, user_slug: str | None = None) -> LandingSnapshot:
        cache_key = user_slug or self.settings.default_user_slug
        cached_snapshot = self.landing_snapshot_cache.get(cache_key)
        if self._cache_is_fresh(cached_snapshot, ttl_seconds=120):
            return cached_snapshot[1]
        if self._use_fast_public_snapshots() and cache_key == self.settings.default_user_slug:
            return self._get_fast_public_landing_snapshot(cache_key)

        repository = BotSocietyRepository(self.database)
        provider_status = self.get_provider_status()
        latest_assets = repository.list_latest_market_snapshots()
        recent_signals = repository.list_recent_signals(limit=96)
        all_predictions = repository.list_predictions(limit=500)
        pending_predictions = [row for row in all_predictions if row["status"] == "pending"]
        asset_symbols = sorted({str(row["asset"]) for row in latest_assets})
        latest_operation = self._latest_operation(repository)
        leaderboard = self.get_leaderboard(user_slug)
        macro_snapshot = self.get_macro_snapshot(repository)
        snapshot = LandingSnapshot(
            summary=self.get_summary(
                user_slug,
                repository=repository,
                bot_summaries=leaderboard,
                predictions=all_predictions,
                assets=asset_symbols,
                signals=recent_signals,
                latest_run=latest_operation.model_dump() if latest_operation else None,
            ),
            assets=[self._to_asset_model(row) for row in latest_assets],
            leaderboard=leaderboard[:4],
            recent_signals=[self._to_signal_model(row) for row in recent_signals[:4]],
            system_pulse=self.get_system_pulse(
                repository,
                provider_status=provider_status,
                recent_signals=recent_signals,
                latest_assets=latest_assets,
                pending_predictions=pending_predictions,
            ),
            macro_snapshot=macro_snapshot,
            provider_status=provider_status,
            business_model=self.get_business_model_strategy(),
        )
        self.landing_snapshot_cache[cache_key] = (datetime.now(timezone.utc), snapshot)
        return snapshot

    def _get_fast_public_landing_snapshot(self, user_slug: str) -> LandingSnapshot:
        repository = BotSocietyRepository(self.database)
        provider_status = self.get_provider_status()
        latest_assets = self._fast_public_market_rows(repository)
        recent_signals = self._fast_public_signal_rows(repository, limit=16)
        predictions = self._fast_public_prediction_rows(repository, limit=96)
        pending_predictions = [row for row in predictions if row.get("status") == "pending"]
        leaderboard = self._fast_public_leaderboard(repository, user_slug, predictions=predictions)
        macro_snapshot = self._fast_public_macro_snapshot(repository)
        snapshot = LandingSnapshot(
            summary=self._fast_public_summary(
                leaderboard=leaderboard,
                predictions=predictions,
                latest_assets=latest_assets,
                recent_signals=recent_signals,
                latest_run=None,
            ),
            assets=[self._to_asset_model(row) for row in latest_assets],
            leaderboard=leaderboard[:4],
            recent_signals=[self._to_signal_model(row) for row in recent_signals[:4]],
            system_pulse=self.get_system_pulse(
                repository,
                provider_status=provider_status,
                notification_health=self._lightweight_notification_health(),
                recent_signals=recent_signals,
                latest_assets=latest_assets,
                pending_predictions=pending_predictions,
            ),
            macro_snapshot=macro_snapshot,
            provider_status=provider_status,
            business_model=self.get_business_model_strategy(),
        )
        self.landing_snapshot_cache[user_slug] = (datetime.now(timezone.utc), snapshot)
        return snapshot

    def _get_fast_public_dashboard_snapshot(self, user_slug: str) -> DashboardSnapshot:
        repository = BotSocietyRepository(self.database)
        provider_status = self.get_provider_status()
        latest_assets = self._fast_public_market_rows(repository)
        recent_signals = self._fast_public_signal_rows(repository, limit=24)
        predictions = self._fast_public_prediction_rows(repository, limit=120)
        pending_predictions = [row for row in predictions if row.get("status") == "pending"]
        leaderboard = self._fast_public_leaderboard(repository, user_slug, predictions=predictions)
        macro_snapshot = self._fast_public_macro_snapshot(repository)
        wallet_snapshot = self._fast_public_wallet_snapshot(latest_assets)
        edge_snapshot = self._fast_public_edge_snapshot(
            latest_assets=latest_assets,
            recent_signals=recent_signals,
            macro_snapshot=macro_snapshot,
            wallet_snapshot=wallet_snapshot,
        )
        notification_health = self._lightweight_notification_health()
        alert_inbox = self._lightweight_alert_inbox()
        paper_venues = self.get_paper_venues()
        snapshot = DashboardSnapshot(
            summary=self._fast_public_summary(
                leaderboard=leaderboard,
                predictions=predictions,
                latest_assets=latest_assets,
                recent_signals=recent_signals,
                latest_run=None,
            ),
            assets=[self._to_asset_model(row) for row in latest_assets],
            leaderboard=leaderboard,
            recent_predictions=[
                self._to_prediction_model(
                    row,
                    provenance=self._prediction_provenance_metadata(row, {}),
                )
                for row in predictions[:8]
            ],
            recent_signals=[self._to_signal_model(row) for row in recent_signals[:8]],
            system_pulse=self.get_system_pulse(
                repository,
                provider_status=provider_status,
                notification_health=notification_health,
                recent_signals=recent_signals,
                latest_assets=latest_assets,
                pending_predictions=pending_predictions,
            ),
            macro_snapshot=macro_snapshot,
            wallet_intelligence=wallet_snapshot,
            edge_snapshot=edge_snapshot,
            paper_trading=self._fast_public_paper_trading_snapshot(),
            paper_venues=paper_venues,
            social_trading=self._fast_public_social_trading_snapshot(repository, user_slug),
            latest_operation=None,
            auth_session=AuthSessionSnapshot(authenticated=False, user=None),
            user_profile=self._fast_public_user_profile(user_slug, alert_inbox),
            notification_health=notification_health,
            provider_status=provider_status,
            launch_readiness=self.get_launch_readiness(provider_status=provider_status),
            connector_control=self.get_connector_control(provider_status=provider_status, paper_venues=paper_venues),
            infrastructure_readiness=self.get_infrastructure_readiness(provider_status=provider_status),
            production_cutover=self.get_production_cutover(provider_status=provider_status),
            business_model=self.get_business_model_strategy(),
        )
        self.dashboard_snapshot_cache[user_slug] = (datetime.now(timezone.utc), snapshot)
        return snapshot

    def _fast_public_market_rows(self, repository: BotSocietyRepository) -> list[dict]:
        if self._cache_is_fresh(self.assets_cache, ttl_seconds=300):
            return [asset.model_dump() for asset in self.assets_cache[1]]
        rows = self._fallback_public_market_rows()
        self.assets_cache = (datetime.now(timezone.utc), [self._to_asset_model(row) for row in rows])
        return rows

    def _fallback_public_market_rows(self) -> list[dict]:
        now = self._now()
        aliases = {
            "bitcoin": ("BTC", 67420.0),
            "ethereum": ("ETH", 3510.0),
            "solana": ("SOL", 158.0),
        }
        rows = []
        for index, coin_id in enumerate(self.settings.tracked_coin_ids or ["bitcoin", "ethereum", "solana"]):
            asset, price = aliases.get(coin_id.lower(), (coin_id.upper()[:8], 100.0 + index))
            rows.append(
                {
                    "asset": asset,
                    "as_of": now,
                    "price": price,
                    "change_24h": round(0.012 - (index * 0.006), 4),
                    "volume_24h": 1000000000.0 / max(1, index + 1),
                    "volatility": round(0.035 + (index * 0.004), 4),
                    "trend_score": round(0.18 - (index * 0.08), 4),
                    "signal_bias": round(0.12 - (index * 0.05), 4),
                    "source": "fast-public-fallback",
                }
            )
        return rows[:6]

    def _fast_public_signal_rows(self, repository: BotSocietyRepository, *, limit: int) -> list[dict]:
        assets = self._fallback_public_market_rows()
        now = self._now()
        templates = [
            ("polymarket", "prediction-market", "Venue order books repriced the crypto election/event cluster.", 0.22),
            ("kalshi", "prediction-market", "Regulated event markets are showing a softer macro-risk premium.", 0.11),
            ("youtube", "social", "Creator desk commentary is leaning toward selective BTC and SOL risk-on setups.", 0.18),
            ("hyperliquid", "venue", "Perp market breadth is firm but not euphoric across tracked majors.", 0.08),
            ("macro", "macro", "Rates and liquidity context remain mixed, so sizing discipline stays elevated.", -0.04),
        ]
        rows = []
        for index in range(limit):
            asset_row = assets[index % len(assets)]
            provider, source_type, title, sentiment = templates[index % len(templates)]
            rows.append(
                {
                    "id": 100000 + index,
                    "asset": asset_row["asset"],
                    "source": provider,
                    "provider_name": provider,
                    "source_type": source_type,
                    "author_handle": f"@{provider}_desk",
                    "engagement_score": round(0.72 - ((index % 4) * 0.04), 3),
                    "provider_trust_score": round(0.78 - ((index % 3) * 0.03), 3),
                    "freshness_score": round(0.94 - ((index % 5) * 0.05), 3),
                    "source_quality_score": round(0.82 - ((index % 4) * 0.035), 3),
                    "channel": source_type,
                    "title": title,
                    "summary": (
                        f"Fast public signal for {asset_row['asset']}: "
                        "dashboard-safe synthesis is available instantly; deep evidence remains in the signal endpoints."
                    ),
                    "sentiment": round(clamp(sentiment + float(asset_row.get("signal_bias") or 0.0) * 0.2, -1.0, 1.0), 3),
                    "relevance": round(0.86 - ((index % 4) * 0.04), 3),
                    "url": "https://bitprivat.com/dashboard",
                    "observed_at": now,
                }
            )
        return rows

    def _fast_public_prediction_rows(self, repository: BotSocietyRepository, *, limit: int) -> list[dict]:
        assets = self._fallback_public_market_rows()
        now = self._now()
        bots = self._fallback_public_bot_summaries()
        rows = []
        for index in range(min(limit, 24)):
            asset = assets[index % len(assets)]
            bot = bots[index % len(bots)]
            direction = "bullish" if float(asset.get("signal_bias") or 0.0) >= -0.02 else "bearish"
            confidence = round(clamp(0.68 + abs(float(asset.get("trend_score") or 0.0)) * 0.18 - (index % 3) * 0.025, 0.5, 0.94), 3)
            strategy_return = round((float(asset.get("change_24h") or 0.0) * (1 if direction == "bullish" else -1)) + 0.018, 4)
            rows.append(
                {
                    "id": 200000 + index,
                    "bot_slug": bot.slug,
                    "bot_name": bot.name,
                    "asset": asset["asset"],
                    "direction": direction,
                    "confidence": confidence,
                    "horizon_days": 7 + (index % 4) * 7,
                    "horizon_label": "1-4 weeks",
                    "thesis": f"{bot.name} sees {asset['asset']} as a monitored setup with controlled sizing.",
                    "trigger_conditions": "Confirm venue pricing, creator evidence, and volatility compression before sizing.",
                    "invalidation": "Auto-pause if signal quality drops below threshold or drawdown guardrails trigger.",
                    "published_at": now,
                    "status": "pending" if index % 4 else "scored",
                    "start_price": float(asset["price"]),
                    "end_price": None,
                    "market_return": None,
                    "strategy_return": strategy_return if index % 4 == 0 else None,
                    "max_adverse_excursion": -0.018 - (index % 3) * 0.006,
                    "score": round(72 + (confidence * 18), 2) if index % 4 == 0 else None,
                    "calibration_score": round(0.72 + (index % 4) * 0.025, 3) if index % 4 == 0 else None,
                    "directional_success": True if index % 4 == 0 else None,
                    "source_signal_ids": "[]",
                }
            )
        return rows

    def _fast_public_leaderboard(
        self,
        repository: BotSocietyRepository,
        user_slug: str,
        *,
        predictions: list[dict],
    ) -> list[BotSummary]:
        cached = self.leaderboard_cache.get(user_slug)
        if self._cache_is_fresh(cached, ttl_seconds=300):
            return cached[1]
        leaderboard = self._fallback_public_bot_summaries(predictions=predictions)
        self.leaderboard_cache[user_slug] = (datetime.now(timezone.utc), leaderboard)
        return leaderboard

    def _fallback_public_bot_summaries(self, predictions: list[dict] | None = None) -> list[BotSummary]:
        now = self._now()
        rows = [
            {
                "slug": "creator-flow",
                "name": "Creator Flow Sentinel",
                "archetype": "Social momentum analyst",
                "focus": "YouTube, X, prediction-market narratives",
                "horizon_label": "1-3 weeks",
                "thesis": "Ranks creator evidence, public market repricing, and cross-venue confirmation before any managed-paper allocation.",
                "risk_style": "Evidence-weighted, capped allocation",
                "asset_universe": ["BTC", "ETH", "SOL"],
                "score": 82.4,
                "hit_rate": 0.64,
                "calibration": 0.78,
                "provenance_score": 0.81,
                "average_strategy_return": 0.047,
                "latest_asset": "BTC",
                "latest_direction": "bullish",
            },
            {
                "slug": "event-arb",
                "name": "Event Arb Cartographer",
                "archetype": "Prediction market mispricing scout",
                "focus": "Polymarket and Kalshi event surfaces",
                "horizon_label": "2-6 weeks",
                "thesis": "Finds event-market edges where implied probability diverges from social, macro, and liquidity context.",
                "risk_style": "Market-neutral when possible",
                "asset_universe": ["BTC", "ETH", "POLY"],
                "score": 79.1,
                "hit_rate": 0.61,
                "calibration": 0.74,
                "provenance_score": 0.76,
                "average_strategy_return": 0.039,
                "latest_asset": "ETH",
                "latest_direction": "neutral",
            },
            {
                "slug": "macro-guard",
                "name": "Macro Guard Rail",
                "archetype": "Risk governor",
                "focus": "Rates, liquidity, volatility, and drawdown controls",
                "horizon_label": "1-8 weeks",
                "thesis": "Keeps strategy exposure aligned with macro regime, liquidity, and realized volatility.",
                "risk_style": "Capital preservation first",
                "asset_universe": ["BTC", "ETH", "SOL"],
                "score": 76.8,
                "hit_rate": 0.58,
                "calibration": 0.72,
                "provenance_score": 0.69,
                "average_strategy_return": 0.031,
                "latest_asset": "SOL",
                "latest_direction": "bullish",
            },
        ]
        prediction_count_by_bot: dict[str, int] = defaultdict(int)
        pending_count_by_bot: dict[str, int] = defaultdict(int)
        last_published_by_bot: dict[str, str] = {}
        for prediction in predictions or []:
            slug = str(prediction.get("bot_slug") or "")
            prediction_count_by_bot[slug] += 1
            if prediction.get("status") == "pending":
                pending_count_by_bot[slug] += 1
            last_published_by_bot.setdefault(slug, str(prediction.get("published_at") or now))
        return [
            BotSummary(
                **row,
                predictions=max(8, prediction_count_by_bot.get(row["slug"], 0)),
                pending_predictions=pending_count_by_bot.get(row["slug"], 2),
                last_published_at=last_published_by_bot.get(row["slug"], now),
                is_followed=False,
            )
            for row in rows
        ]

    def _fast_public_summary(
        self,
        *,
        leaderboard: list[BotSummary],
        predictions: list[dict],
        latest_assets: list[dict],
        recent_signals: list[dict],
        latest_run: dict | None,
    ) -> Summary:
        scores = [bot.score for bot in leaderboard] or [0.0]
        calibrations = [bot.calibration for bot in leaderboard] or [0.0]
        return Summary(
            active_bots=len(leaderboard),
            tracked_assets=len({str(row.get("asset")) for row in latest_assets if row.get("asset")}),
            total_predictions=len(predictions),
            scored_predictions=sum(1 for row in predictions if row.get("status") == "scored"),
            pending_predictions=sum(1 for row in predictions if row.get("status") == "pending"),
            average_bot_score=round(mean(scores), 2),
            median_calibration=round(median(calibrations), 3),
            signals_last_24h=len(recent_signals),
            last_cycle_status=latest_run.get("status") if latest_run else None,
            last_cycle_at=latest_run.get("completed_at") if latest_run else None,
        )

    def _fast_public_macro_snapshot(self, repository: BotSocietyRepository) -> MacroSnapshot:
        if self._cache_is_fresh(self.macro_snapshot_cache, ttl_seconds=300):
            return self.macro_snapshot_cache[1]
        now = self._now()
        series = [
            MacroSeriesSnapshot(
                series_id="FEDFUNDS",
                label="Fed funds",
                unit="percent",
                latest_value=5.25,
                change_percent=0.0,
                signal_bias=-0.08,
                regime_label="restrictive",
                source="fast-public-macro",
                observed_at=now,
                history=[],
            ),
            MacroSeriesSnapshot(
                series_id="VIXCLS",
                label="Volatility regime",
                unit="index",
                latest_value=16.8,
                change_percent=-0.4,
                signal_bias=0.08,
                regime_label="balanced",
                source="fast-public-macro",
                observed_at=now,
                history=[],
            ),
            MacroSeriesSnapshot(
                series_id="LIQUIDITY",
                label="Liquidity proxy",
                unit="score",
                latest_value=0.56,
                change_percent=1.2,
                signal_bias=0.12,
                regime_label="constructive",
                source="fast-public-macro",
                observed_at=now,
                history=[],
            ),
        ]
        posture_score = mean(item.signal_bias for item in series) if series else 0.0
        posture = "Macro supportive" if posture_score >= 0.18 else ("Macro restrictive" if posture_score <= -0.18 else "Macro balanced")
        snapshot = MacroSnapshot(
            generated_at=self._now(),
            posture=posture,
            summary=(
                f"Fast public macro view is tracking {len(series)} series without loading long history curves."
                if series
                else "Macro context is available in fast public mode after provider hydration."
            ),
            series=series,
        )
        self.macro_snapshot_cache = (datetime.now(timezone.utc), snapshot)
        return snapshot

    def _fast_public_wallet_snapshot(self, latest_assets: list[dict]) -> WalletIntelligenceSnapshot:
        if self._cache_is_fresh(self.wallet_snapshot_cache, ttl_seconds=300):
            return self.wallet_snapshot_cache[1]
        wallets = [
            WalletProfileView(
                address=f"public-signal-cluster-{index + 1}",
                display_name=f"{row['asset']} Smart Flow Cluster",
                bio="Aggregated public wallet-flow placeholder for the fast public dashboard.",
                primary_asset=str(row["asset"]),
                portfolio_value=round(float(row.get("volume_24h") or 0.0) * 0.006, 2),
                lifetime_volume=round(float(row.get("volume_24h") or 0.0) * 0.08, 2),
                traded_markets=18 + index,
                recent_trades=8 + index,
                win_rate=round(0.58 - (index * 0.02), 3),
                realized_pnl_30d=round(float(row.get("change_24h") or 0.0) * 120000, 2),
                buy_ratio=round(clamp(0.52 + float(row.get("signal_bias") or 0.0) * 0.16, 0.0, 1.0), 3),
                conviction_score=round(clamp(0.62 + abs(float(row.get("trend_score") or 0.0)) * 0.18, 0.0, 1.0), 3),
                smart_money_score=round(clamp(0.68 + abs(float(row.get("signal_bias") or 0.0)) * 0.16, 0.0, 1.0), 3),
                net_bias=round(clamp(float(row.get("signal_bias") or 0.0), -1.0, 1.0), 3),
                recent_markets=[str(row["asset"])],
                source="fast-public-wallet-intelligence",
            )
            for index, row in enumerate(latest_assets[:4])
        ]
        aggregate_bias = mean(wallet.net_bias for wallet in wallets) if wallets else 0.0
        snapshot = WalletIntelligenceSnapshot(
            generated_at=self._now(),
            summary=(
                f"Fast public wallet layer is summarizing {len(wallets)} asset-flow clusters for dashboard responsiveness."
                if wallets
                else "Wallet intelligence will populate after tracked assets are hydrated."
            ),
            wallets=wallets,
            aggregate_bias=round(aggregate_bias, 3),
        )
        self.wallet_snapshot_cache = (datetime.now(timezone.utc), snapshot)
        return snapshot

    def _fast_public_edge_snapshot(
        self,
        *,
        latest_assets: list[dict],
        recent_signals: list[dict],
        macro_snapshot: MacroSnapshot,
        wallet_snapshot: WalletIntelligenceSnapshot,
    ) -> EdgeSnapshot:
        macro_bias = mean(series.signal_bias for series in macro_snapshot.series) if macro_snapshot.series else 0.0
        opportunities = []
        for row in latest_assets[:6]:
            asset = str(row["asset"])
            asset_signals = [signal for signal in recent_signals if str(signal.get("asset")).upper() == asset.upper()]
            signal_bias = self._signal_sentiment_for_asset(asset_signals)
            wallet_bias = self._wallet_bias_for_asset(wallet_snapshot, asset)
            trend_bias = clamp(float(row.get("trend_score") or 0.0), -1.0, 1.0)
            implied_probability = clamp(0.5 + (trend_bias * 0.05), 0.05, 0.95)
            fair_probability = clamp(
                implied_probability + (signal_bias * 0.05) + (wallet_bias * 0.04) + (macro_bias * 0.03),
                0.05,
                0.95,
            )
            edge_bps = round((fair_probability - implied_probability) * 10000, 1)
            opportunities.append(
                EdgeOpportunityView(
                    asset=asset,
                    market_source="fast-public-edge-router",
                    market_label=f"{asset} directional edge",
                    market_slug=f"{asset.lower()}-directional-edge",
                    implied_probability=round(implied_probability, 4),
                    fair_probability=round(fair_probability, 4),
                    edge_bps=edge_bps,
                    confidence=round(clamp(0.52 + abs(edge_bps) / 3000, 0.12, 0.96), 3),
                    stance="bullish" if edge_bps >= 80 else ("bearish" if edge_bps <= -80 else "neutral"),
                    liquidity=round(float(row.get("volume_24h") or 0.0) * 0.001, 2),
                    volume_24h=round(float(row.get("volume_24h") or 0.0), 2),
                    supporting_signals=[
                        f"Recent signal bias {signal_bias:+.2f}",
                        f"Wallet bias {wallet_bias:+.2f}",
                        f"Macro bias {macro_bias:+.2f}",
                    ],
                    updated_at=str(row["as_of"]),
                )
            )
        opportunities.sort(key=lambda item: (abs(item.edge_bps), item.confidence), reverse=True)
        best_edge = opportunities[0] if opportunities else None
        return EdgeSnapshot(
            generated_at=self._now(),
            summary=(
                f"Fast public edge view ranked {len(opportunities)} assets; strongest current dislocation is {best_edge.asset} at {best_edge.edge_bps:+.0f} bps."
                if best_edge
                else "No public edge surfaces are available yet."
            ),
            opportunities=opportunities,
        )

    def _fast_public_paper_trading_snapshot(self) -> PaperTradingSnapshot:
        starting_balance = round(self.settings.paper_starting_balance, 2)
        return PaperTradingSnapshot(
            generated_at=self._now(),
            summary=PaperPortfolioSummary(
                starting_balance=starting_balance,
                cash_balance=starting_balance,
                open_exposure=0.0,
                equity=starting_balance,
                realized_pnl=0.0,
                unrealized_pnl=0.0,
                total_return=0.0,
                win_rate=0.0,
                open_positions=0,
                closed_positions=0,
            ),
            positions=[],
        )

    def _fast_public_social_trading_snapshot(
        self,
        repository: BotSocietyRepository,
        user_slug: str,
    ) -> SocialTradingSnapshot:
        now = self._now()
        top_traders = [
            SocialTraderScorecard(
                id=9001,
                slug="youtube-macro-scout",
                display_name="YouTube Macro Scout",
                handle="@macro-scout",
                platform="youtube",
                source_url="https://youtube.com",
                avatar_seed="youtube-macro-scout",
                avatar_url=None,
                description="Aggregates high-signal crypto and macro creators, then scores whether their historical calls would have improved a managed-paper portfolio.",
                primary_assets=["BTC", "ETH"],
                style_tags=["macro", "event markets", "risk timing"],
                signal_count=148,
                tracked_years=3.2,
                win_rate=0.63,
                average_roi=0.041,
                roi_if_followed=0.187,
                max_drawdown=-0.092,
                sharpe_like=1.34,
                consistency_score=0.74,
                influence_score=0.82,
                recency_score=0.88,
                composite_score=84.6,
                last_signal_at=now,
                state="watching",
                risk_level="medium",
                conviction_label="High evidence density",
                copy_trade_readiness="paper_ready",
                watch_mode_recommendation="Start with signal mode, then graduate to managed paper after 20 verified calls.",
                evidence_summary="YouTube-first model with cross-checks from venue pricing and public market response.",
                risk_notes=["Creator statements can be ambiguous; require asset, direction, and timestamp extraction before scoring."],
                allocation_guidance={
                    "recommended_mode": "signals",
                    "suggested_allocation_usd": 500.0,
                    "max_single_position_usd": 75.0,
                    "max_position_pct": 0.12,
                    "rationale": "Strong enough for alerts and small paper allocations, not live copy trading.",
                },
                evidence=[],
            ),
            SocialTraderScorecard(
                id=9002,
                slug="prediction-market-cartel",
                display_name="Prediction Market Cartographer",
                handle="@event-cartographer",
                platform="x",
                source_url="https://x.com",
                avatar_seed="prediction-market-cartographer",
                avatar_url=None,
                description="Tracks event-market specialists who publish clear probabilities, entry logic, and settlement assumptions.",
                primary_assets=["BTC", "POLY", "KALSHI"],
                style_tags=["polymarket", "kalshi", "probability"],
                signal_count=96,
                tracked_years=2.4,
                win_rate=0.59,
                average_roi=0.033,
                roi_if_followed=0.142,
                max_drawdown=-0.074,
                sharpe_like=1.12,
                consistency_score=0.69,
                influence_score=0.71,
                recency_score=0.8,
                composite_score=78.9,
                last_signal_at=now,
                state="watching",
                risk_level="medium",
                conviction_label="Good probability hygiene",
                copy_trade_readiness="signals_only",
                watch_mode_recommendation="Use as a pricing-check signal before auto-routing orders.",
                evidence_summary="Scores explicit probability calls and compares them to settlement or later market repricing.",
                risk_notes=["Prediction-market liquidity can vanish quickly; cap position size and slippage."],
                allocation_guidance={
                    "recommended_mode": "signals",
                    "suggested_allocation_usd": 350.0,
                    "max_single_position_usd": 50.0,
                    "max_position_pct": 0.1,
                    "rationale": "Useful as a signal source; managed mode needs more fill-quality evidence.",
                },
                evidence=[],
            ),
        ]
        allocations = []
        allocated_usd = round(sum(item.allocation_limit_usd for item in allocations if item.is_active), 2)
        portfolio_limit = round(max(self.settings.paper_starting_balance, allocated_usd), 2)
        return SocialTradingSnapshot(
            generated_at=self._now(),
            provider_mode=getattr(self.social_discovery_provider, "source_name", self.settings.social_discovery_provider),
            youtube_required=True,
            youtube_configured=bool(self.settings.youtube_api_key),
            summary=(
                f"{len(top_traders)} creator-trader profile(s) are ready for signal or managed-paper following."
                if top_traders
                else "Creator discovery is ready; add YouTube API credentials to expand beyond the seeded watchlist."
            ),
            top_traders=top_traders,
            allocations=allocations,
            portfolio_limit_usd=portfolio_limit,
            allocated_usd=allocated_usd,
            unallocated_usd=round(max(0.0, portfolio_limit - allocated_usd), 2),
            latest_discovery_run=None,
            discovery_runs=[],
            diversification_plan=self._social_diversification_plan(top_traders, allocations),
            portfolio_risk_notes=self._social_portfolio_risk_notes(
                top_traders,
                allocations,
                allocated_usd=allocated_usd,
                portfolio_limit=portfolio_limit,
                youtube_configured=bool(self.settings.youtube_api_key),
            ),
            safety_notes=[
                "Signal mode is alerts-only.",
                "Managed mode remains paper-only until legal, KYC, and venue approvals are complete.",
                "Creator scorecards rank historical evidence; they are not guarantees of future performance.",
            ],
        )

    def _fast_public_user_profile(self, user_slug: str, alert_inbox: AlertInbox) -> UserProfile:
        return UserProfile(
            slug=user_slug,
            display_name="BITprivat Demo Operator",
            email="demo@bitprivat.com",
            tier="demo",
            is_demo_user=True,
            billing=BillingSnapshot(
                provider="stripe",
                configured=bool(self.settings.stripe_secret_key and self.settings.stripe_publishable_key),
                checkout_ready=False,
                portal_ready=False,
                can_manage=False,
                tier="demo",
                summary="Public demo workspace: billing is hidden until Stripe is activated.",
                warnings=["Stripe production onboarding is intentionally paused."],
                available_plans=self._billing_plan_catalog(),
                publishable_key=self.settings.stripe_publishable_key,
                contact_email=self.settings.privacy_contact_email,
            ),
            follows=[],
            watchlist=[],
            alert_rules=[],
            recent_alerts=alert_inbox.alerts,
            notification_channels=[],
            unread_alert_count=alert_inbox.unread_count,
        )

    def get_system_pulse(
        self,
        repository: BotSocietyRepository | None = None,
        *,
        provider_status: ProviderStatus | None = None,
        notification_health: NotificationHealthSnapshot | None = None,
        recent_signals: list[dict] | None = None,
        latest_assets: list[dict] | None = None,
        pending_predictions: list[dict] | None = None,
    ) -> SystemPulseSnapshot:
        cacheable = (
            repository is None
            and provider_status is None
            and notification_health is None
            and recent_signals is None
            and latest_assets is None
            and pending_predictions is None
        )
        if cacheable and self._cache_is_fresh(self.system_pulse_cache, ttl_seconds=120):
            return self.system_pulse_cache[1]

        active_repository = repository or BotSocietyRepository(self.database)
        recent_signals = recent_signals if recent_signals is not None else active_repository.list_recent_signals(limit=96)
        latest_assets = latest_assets if latest_assets is not None else active_repository.list_latest_market_snapshots()
        provider_status = provider_status or self.get_provider_status()
        notification_health = notification_health or (
            self._lightweight_notification_health()
            if self._use_fast_public_snapshots()
            else self.get_notification_health(self.settings.default_user_slug)
        )
        generated_at = self._now()
        average_quality = mean(float(signal.get("source_quality_score") or 0.0) for signal in recent_signals) if recent_signals else 0.0
        average_freshness = mean(float(signal.get("freshness_score") or 0.0) for signal in recent_signals) if recent_signals else 0.0
        live_provider_count = (
            int(provider_status.market_provider_live_capable)
            + int(provider_status.signal_provider_live_capable)
            + int(provider_status.macro_provider_live_capable)
            + int(provider_status.wallet_provider_live_capable)
            + int(provider_status.social_discovery_live_capable)
        )
        live_provider_count += sum(1 for venue in provider_status.venue_signal_providers if venue.live_capable)
        pending_prediction_count = (
            len(pending_predictions)
            if pending_predictions is not None
            else len(active_repository.list_predictions(status="pending", limit=500))
        )
        snapshot = SystemPulseSnapshot(
            generated_at=generated_at,
            live_provider_count=live_provider_count,
            total_recent_signals=len(recent_signals),
            average_signal_quality=round(average_quality, 3),
            average_signal_freshness=round(average_freshness, 3),
            pending_predictions=pending_prediction_count,
            retry_queue_depth=notification_health.retry_queue_depth,
            signal_mix=self._build_signal_mix(recent_signals),
            venue_pulse=self._build_venue_pulse(recent_signals, latest_assets, provider_status),
        )
        if cacheable:
            self.system_pulse_cache = (datetime.now(timezone.utc), snapshot)
        return snapshot

    def get_latest_operation(self) -> OperationSnapshot | None:
        repository = BotSocietyRepository(self.database)
        return self._latest_operation(repository)

    def get_cycle_result_snapshot(
        self,
        *,
        cycle_started: bool = False,
        cycle_message: str | None = None,
    ) -> CycleResult:
        repository = BotSocietyRepository(self.database)
        return CycleResult(
            operation=self._latest_operation(repository),
            leaderboard=self._build_bot_summaries(repository, self.settings.default_user_slug),
            recent_predictions=self._build_prediction_views(repository, repository.list_predictions(limit=10)),
            provider_status=self.get_provider_status(),
            alert_inbox=self.get_alert_inbox(self.settings.default_user_slug),
            notification_health=self.get_notification_health(self.settings.default_user_slug),
            cycle_started=cycle_started,
            cycle_message=cycle_message,
        )

    def probe_provider_connectivity(self) -> dict[str, str]:
        repository = BotSocietyRepository(self.database)
        latest_snapshots = repository.list_latest_market_snapshots()
        market_batch = latest_snapshots
        diagnostics: dict[str, str] = {}

        try:
            market_batch = self.market_provider.generate(latest_snapshots, 0)
            diagnostics["market"] = f"ok ({len(market_batch)} snapshot(s) returned)"
        except Exception as exc:
            diagnostics["market"] = f"error ({exc.__class__.__name__}: {exc})"

        try:
            signal_batch = self.signal_provider.generate(market_batch, 0)
            diagnostics["signal"] = f"ok ({len(signal_batch)} signal(s) returned)"
        except Exception as exc:
            diagnostics["signal"] = f"error ({exc.__class__.__name__}: {exc})"

        for venue_provider in self.venue_signal_providers:
            key = f"signal_{venue_provider.source_name}"
            try:
                signal_batch = venue_provider.generate(market_batch, 0)
                diagnostics[key] = f"ok ({len(signal_batch)} signal(s) returned)"
            except Exception as exc:
                diagnostics[key] = f"error ({exc.__class__.__name__}: {exc})"

        try:
            social_batch = self.social_discovery_provider.discover()
            diagnostics["social_discovery"] = (
                f"ok ({len(social_batch.traders)} trader(s) returned; "
                f"provider={social_batch.provider}; youtube_configured={social_batch.youtube_configured})"
            )
        except Exception as exc:
            diagnostics["social_discovery"] = f"error ({exc.__class__.__name__}: {exc})"

        return diagnostics

    def run_pipeline_cycle(self) -> CycleResult:
        repository = BotSocietyRepository(self.database)
        latest_snapshots = repository.list_latest_market_snapshots()
        cycle_index = repository.count_pipeline_runs() + 1

        live_market_active = False
        live_signal_active = False
        message_prefixes: list[str] = []
        macro_observations = self._refresh_macro_data(repository)

        try:
            market_batch = self.market_provider.generate(latest_snapshots, cycle_index)
            self.market_provider_fallback = False
            self.market_provider_source = getattr(self.market_provider, "last_source_name", self.market_provider.source_name)
            live_market_active = self.market_provider_source != self.demo_market_provider.source_name
        except Exception as exc:
            market_batch = self.demo_market_provider.generate(latest_snapshots, cycle_index)
            self.market_provider_fallback = True
            self.market_provider_source = f"{self.market_provider.source_name}-fallback"
            message_prefixes.append(f"Market provider fallback after {exc.__class__.__name__}: {exc}.")

        repository.upsert_market_snapshots(market_batch)

        try:
            signal_batch = self._generate_signal_batch(market_batch, cycle_index)
            if not signal_batch:
                raise ValueError("signal providers returned zero signals")
            self.signal_provider_fallback = False
            self.signal_provider_source = self._compose_signal_provider_source()
            live_signal_active = self._signal_live_active()
        except Exception as exc:
            signal_batch = self.demo_signal_provider.generate(market_batch, cycle_index)
            self.signal_provider_fallback = True
            self.signal_provider_source = f"{self._compose_signal_provider_source()}-fallback"
            message_prefixes.append(f"Signal provider fallback after {exc.__class__.__name__}: {exc}.")

        ingested_signals = repository.upsert_signals(signal_batch)

        latest_snapshots = repository.list_latest_market_snapshots()
        recent_signals = repository.list_recent_signals(limit=24)
        pending_lookup = {row["bot_slug"] for row in repository.list_predictions(status="pending", limit=500)}
        published_at = max(snapshot["as_of"] for snapshot in latest_snapshots)
        generated_predictions = self.orchestrator.build_predictions(
            bots=repository.list_bots(),
            latest_snapshots=latest_snapshots,
            recent_signals=recent_signals,
            published_at=published_at,
            pending_lookup=pending_lookup,
        )
        created_predictions = repository.insert_predictions(generated_predictions)
        new_predictions = repository.list_predictions_by_published_at(published_at, limit=max(created_predictions, 12))
        delivered_alerts = self._deliver_alerts_for_predictions(repository, new_predictions)

        scorer = ScoringEngine(repository, self.settings.scoring_version)
        scored_predictions = scorer.score_available_predictions()
        social_updated = 0
        social_evidence_count = 0
        try:
            social_refresh = self.refresh_social_trader_discovery(repository=repository)
            social_updated = social_refresh.updated
            social_evidence_count = sum(len(trader.evidence) for trader in social_refresh.traders)
        except Exception as exc:
            message_prefixes.append(f"Social discovery fallback after {exc.__class__.__name__}: {exc}.")

        cycle_type = "live-cycle" if live_market_active or live_signal_active else "demo-cycle"
        if self.market_provider_fallback or self.signal_provider_fallback:
            cycle_type = "fallback-cycle"

        repository.insert_pipeline_run(
            {
                "cycle_type": cycle_type,
                "status": "completed",
                "started_at": published_at,
                "completed_at": published_at,
                "ingested_signals": ingested_signals,
                "generated_predictions": created_predictions,
                "scored_predictions": scored_predictions,
                "message": " ".join(
                    [
                        *message_prefixes,
                        f"Ingested {ingested_signals} market/news signals, monitored {social_updated} social trader profile(s), indexed {social_evidence_count} creator evidence item(s), generated {created_predictions} fresh predictions, scored {scored_predictions} eligible predictions, delivered {delivered_alerts} alerts, and refreshed {macro_observations} macro observations.",
                    ]
                ).strip(),
            }
        )
        operation = repository.get_latest_pipeline_run()
        self._clear_live_caches()
        return self.get_cycle_result_snapshot(
            cycle_started=True,
            cycle_message=f"Cycle {operation['id'] if operation else 'n/a'} completed.",
        )

    def _deliver_alerts_for_predictions(self, repository: BotSocietyRepository, predictions: list[dict]) -> int:
        if not predictions:
            return 0
        active_rules = repository.list_active_alert_rules()
        if not active_rules:
            return 0

        channels_by_user = {
            rule["user_slug"]: repository.list_active_notification_channels(rule["user_slug"])
            for rule in active_rules
        }

        created_at = self._now()
        total_events = 0
        for prediction in predictions:
            events: list[dict] = []
            for rule in active_rules:
                if rule["bot_slug"] and rule["bot_slug"] != prediction["bot_slug"]:
                    continue
                if rule["asset"] and rule["asset"] != prediction["asset"]:
                    continue
                if float(prediction["confidence"]) < float(rule["min_confidence"]):
                    continue
                scope = self._alert_scope(rule)
                title = f"{prediction['bot_name']} issued a {prediction['direction']} {prediction['asset']} call"
                message = (
                    f"{prediction['bot_name']} published a {prediction['horizon_label'].lower()} view on {prediction['asset']} with "
                    f"{int(round(float(prediction['confidence']) * 100))}% confidence. Matched {scope}."
                )
                base_event = {
                    "user_slug": rule["user_slug"],
                    "rule_id": rule["id"],
                    "prediction_id": prediction["id"],
                    "bot_slug": prediction["bot_slug"],
                    "asset": prediction["asset"],
                    "direction": prediction["direction"],
                    "confidence": prediction["confidence"],
                    "title": title,
                    "message": message,
                    "created_at": created_at,
                    "read_at": None,
                }
                events.append(
                    {
                        **base_event,
                        "notification_channel_id": None,
                        "channel": "in_app",
                        "channel_target": "workspace-inbox",
                        "delivery_status": "delivered",
                        "attempt_count": 1,
                        "last_attempt_at": created_at,
                        "next_attempt_at": None,
                        "error_detail": None,
                    }
                )
                outbound_payload = {
                    "title": title,
                    "message": message,
                    "prediction_id": prediction["id"],
                    "bot_slug": prediction["bot_slug"],
                    "bot_name": prediction["bot_name"],
                    "asset": prediction["asset"],
                    "direction": prediction["direction"],
                    "confidence": prediction["confidence"],
                    "published_at": prediction["published_at"],
                    "rule_id": rule["id"],
                }
                for channel in channels_by_user.get(rule["user_slug"], []):
                    delivered, error = self.dispatcher.dispatch(channel, outbound_payload)
                    delivery_status, next_attempt_at = ("delivered", None) if delivered else self._next_delivery_state(1)
                    repository.update_notification_channel_delivery(
                        rule["user_slug"],
                        int(channel["id"]),
                        delivered_at=created_at if delivered else None,
                        error=error,
                    )
                    events.append(
                        {
                            **base_event,
                            "notification_channel_id": channel["id"],
                            "channel": channel["channel_type"],
                            "channel_target": channel["target"],
                            "delivery_status": delivery_status,
                            "attempt_count": 1,
                            "last_attempt_at": created_at,
                            "next_attempt_at": next_attempt_at,
                            "error_detail": error,
                            "message": message,
                        }
                    )
            total_events += repository.upsert_alert_delivery_events(events)
        return total_events

    def _build_bot_summaries(
        self,
        repository: BotSocietyRepository,
        user_slug: str | None = None,
        *,
        predictions: list[dict] | None = None,
    ) -> list[BotSummary]:
        bots = repository.list_bots()
        predictions = predictions if predictions is not None else repository.list_predictions(limit=500)
        followed_bot_slugs = {row["bot_slug"] for row in repository.list_user_follows(user_slug)} if user_slug else set()
        bot_predictions: dict[str, list[dict]] = {bot["slug"]: [] for bot in bots}
        signal_lookup = self._load_prediction_signal_lookup(repository, predictions)
        for prediction in predictions:
            bot_predictions.setdefault(prediction["bot_slug"], []).append(prediction)

        summaries: list[BotSummary] = []
        for bot in bots:
            rows = bot_predictions.get(bot["slug"], [])
            scored_rows = [row for row in rows if row["status"] == "scored"]
            pending_rows = [row for row in rows if row["status"] == "pending"]
            latest = rows[0] if rows else None
            hit_rate = mean(row["directional_success"] for row in scored_rows) if scored_rows else 0.0
            calibration = mean(row["calibration_score"] for row in scored_rows) if scored_rows else 0.0
            avg_strategy_return = mean(row["strategy_return"] for row in scored_rows) if scored_rows else 0.0
            risk_discipline = (
                mean(clamp(1 - abs(row["max_adverse_excursion"] or 0.0) / 0.06, 0.0, 1.0) for row in scored_rows)
                if scored_rows
                else 0.0
            )
            provenance_samples = []
            for row in rows:
                provenance_value = self._prediction_provenance_score(row, signal_lookup)
                if provenance_value is not None:
                    provenance_samples.append(provenance_value)
            provenance_score = mean(provenance_samples) if provenance_samples else 0.0
            score_series = [row["score"] / 100 for row in scored_rows if row["score"] is not None]
            consistency = clamp(1 - (pstdev(score_series) / 0.25), 0.0, 1.0) if len(score_series) > 1 else (1.0 if score_series else 0.0)
            return_component = clamp((avg_strategy_return + 0.04) / 0.08, 0.0, 1.0)
            composite_score = 100 * (
                0.26 * hit_rate
                + 0.22 * return_component
                + 0.18 * calibration
                + 0.14 * consistency
                + 0.08 * risk_discipline
                + 0.12 * provenance_score
            )
            summaries.append(
                BotSummary(
                    slug=bot["slug"],
                    name=bot["name"],
                    archetype=bot["archetype"],
                    focus=bot["focus"],
                    horizon_label=bot["horizon_label"],
                    thesis=bot["thesis"],
                    risk_style=bot["risk_style"],
                    asset_universe=bot["asset_universe"].split(","),
                    score=round(composite_score, 2),
                    hit_rate=round(hit_rate, 3),
                    calibration=round(calibration, 3),
                    provenance_score=round(provenance_score, 3),
                    average_strategy_return=round(avg_strategy_return, 4),
                    predictions=len(rows),
                    pending_predictions=len(pending_rows),
                    latest_asset=latest["asset"] if latest else None,
                    latest_direction=latest["direction"] if latest else None,
                    last_published_at=latest["published_at"] if latest else None,
                    is_followed=bot["slug"] in followed_bot_slugs,
                )
            )
        return sorted(summaries, key=lambda bot: bot.score, reverse=True)

    def _build_prediction_views(self, repository: BotSocietyRepository, rows: list[dict]) -> list[PredictionView]:
        prediction_rows = list(rows)
        signal_lookup = self._load_prediction_signal_lookup(repository, prediction_rows)
        return [
            self._to_prediction_model(
                row,
                provenance=self._prediction_provenance_metadata(row, signal_lookup),
            )
            for row in prediction_rows
        ]

    @staticmethod
    def _extract_source_signal_ids(prediction: dict) -> list[int]:
        raw_ids = prediction.get("source_signal_ids")
        if not raw_ids:
            return []
        try:
            parsed = json.loads(raw_ids) if isinstance(raw_ids, str) else raw_ids
        except json.JSONDecodeError:
            return []
        if not isinstance(parsed, list):
            return []
        signal_ids: list[int] = []
        for value in parsed:
            try:
                signal_ids.append(int(value))
            except (TypeError, ValueError):
                continue
        return signal_ids

    def _load_prediction_signal_lookup(self, repository: BotSocietyRepository, predictions: list[dict]) -> dict[int, dict]:
        signal_ids = {
            signal_id
            for prediction in predictions
            for signal_id in self._extract_source_signal_ids(prediction)
        }
        if not signal_ids:
            return {}
        return {row["id"]: row for row in repository.list_signals_by_ids(signal_ids)}

    def _prediction_provenance_score(self, prediction: dict, signal_lookup: dict[int, dict]) -> float | None:
        linked_signals = self._linked_prediction_signals(prediction, signal_lookup)
        if not linked_signals:
            return None
        quality_score = mean(float(signal.get("source_quality_score") or 0.0) for signal in linked_signals)
        freshness_score = mean(float(signal.get("freshness_score") or 0.0) for signal in linked_signals)
        unique_providers = len({str(signal.get("provider_name") or signal.get("source") or "unknown") for signal in linked_signals})
        unique_types = len({str(signal.get("source_type") or signal.get("channel") or "unknown") for signal in linked_signals})
        venue_count = sum(
            1 for signal in linked_signals if str(signal.get("source_type") or "") == "prediction-market" or str(signal.get("channel") or "") == "venue"
        )
        provider_diversity = clamp((unique_providers - 1) / 3, 0.0, 1.0)
        source_diversity = clamp((unique_types - 1) / 2, 0.0, 1.0)
        venue_lift = clamp(0.55 + (0.45 * (venue_count / len(linked_signals))), 0.55, 1.0)
        return clamp(
            (0.42 * quality_score)
            + (0.18 * freshness_score)
            + (0.16 * provider_diversity)
            + (0.10 * source_diversity)
            + (0.14 * venue_lift),
            0.0,
            1.0,
        )

    def _prediction_provenance_metadata(self, prediction: dict, signal_lookup: dict[int, dict]) -> dict[str, object]:
        linked_signals = self._linked_prediction_signals(prediction, signal_lookup)
        if not linked_signals:
            return {
                "provenance_score": None,
                "source_signal_count": 0,
                "provider_mix": [],
                "source_mix": [],
                "top_signal_quality": None,
                "venue_support_share": None,
            }

        provider_counts: dict[str, int] = defaultdict(int)
        source_counts: dict[str, int] = defaultdict(int)
        venue_count = 0
        strongest_quality = 0.0

        for signal in linked_signals:
            provider_name = str(signal.get("provider_name") or signal.get("source") or "unknown")
            source_type = str(signal.get("source_type") or signal.get("channel") or "unknown")
            provider_counts[provider_name] += 1
            source_counts[source_type] += 1
            strongest_quality = max(strongest_quality, float(signal.get("source_quality_score") or 0.0))
            if source_type == "prediction-market" or str(signal.get("channel") or "") == "venue":
                venue_count += 1

        provider_mix = [
            name
            for name, _count in sorted(provider_counts.items(), key=lambda item: (-item[1], item[0]))
        ][:3]
        source_mix = [
            name
            for name, _count in sorted(source_counts.items(), key=lambda item: (-item[1], item[0]))
        ][:3]

        return {
            "provenance_score": self._prediction_provenance_score(prediction, signal_lookup),
            "source_signal_count": len(linked_signals),
            "provider_mix": provider_mix,
            "source_mix": source_mix,
            "top_signal_quality": round(strongest_quality, 6),
            "venue_support_share": round(clamp(venue_count / len(linked_signals), 0.0, 1.0), 6),
        }

    def _linked_prediction_signals(self, prediction: dict, signal_lookup: dict[int, dict]) -> list[dict]:
        return [signal_lookup[signal_id] for signal_id in self._extract_source_signal_ids(prediction) if signal_id in signal_lookup]

    def _build_signal_mix(self, recent_signals: list[dict]) -> list[SignalMixItem]:
        if not recent_signals:
            return []
        grouped: dict[str, list[dict]] = defaultdict(list)
        total = len(recent_signals)
        for signal in recent_signals:
            signal_type = str(signal.get("source_type") or signal.get("channel") or "unknown")
            grouped[signal_type].append(signal)
        ordered_labels = {
            "prediction-market": "Venue markets",
            "news": "News",
            "social": "Social",
            "macro": "Macro",
        }
        items = []
        for signal_type, rows in sorted(grouped.items(), key=lambda item: len(item[1]), reverse=True):
            average_quality = mean(float(row.get("source_quality_score") or 0.0) for row in rows)
            items.append(
                SignalMixItem(
                    label=ordered_labels.get(signal_type, signal_type.replace("-", " ").title()),
                    count=len(rows),
                    share=round(len(rows) / total, 3),
                    average_quality=round(average_quality, 3),
                )
            )
        return items

    def _build_venue_pulse(self, recent_signals: list[dict], latest_assets: list[dict], provider_status: ProviderStatus) -> list[VenuePulseItem]:
        items: list[VenuePulseItem] = []

        if "hyperliquid" in provider_status.market_provider_source:
            latest_asset_time = max((asset["as_of"] for asset in latest_assets), default=None)
            items.append(
                VenuePulseItem(
                    source=provider_status.market_provider_source,
                    label="Hyperliquid market feed",
                    signal_count=len(latest_assets),
                    assets=[asset["asset"] for asset in latest_assets],
                    average_quality=0.84 if provider_status.market_provider_ready else 0.58,
                    average_freshness=1.0,
                    average_sentiment=round(mean(float(asset.get("signal_bias") or 0.0) for asset in latest_assets), 3) if latest_assets else 0.0,
                    latest_title="Live perpetual mids and market posture",
                    latest_at=latest_asset_time,
                )
            )

        grouped: dict[str, list[dict]] = defaultdict(list)
        for signal in recent_signals:
            is_venue_signal = str(signal.get("source_type") or "") == "prediction-market" or str(signal.get("channel") or "") == "venue"
            if not is_venue_signal:
                continue
            provider_name = str(signal.get("provider_name") or signal.get("source") or "venue")
            grouped[provider_name].append(signal)

        label_map = {
            "polymarket-gamma-provider": "Polymarket event surface",
            "kalshi-public-provider": "Kalshi contract surface",
        }
        for provider_name, rows in sorted(grouped.items(), key=lambda item: len(item[1]), reverse=True):
            latest = rows[0]
            items.append(
                VenuePulseItem(
                    source=provider_name,
                    label=label_map.get(provider_name, provider_name.replace("-", " ").title()),
                    signal_count=len(rows),
                    assets=sorted({str(row.get("asset") or "n/a") for row in rows}),
                    average_quality=round(mean(float(row.get("source_quality_score") or 0.0) for row in rows), 3),
                    average_freshness=round(mean(float(row.get("freshness_score") or 0.0) for row in rows), 3),
                    average_sentiment=round(mean(float(row.get("sentiment") or 0.0) for row in rows), 3),
                    latest_title=str(latest.get("title") or ""),
                    latest_at=str(latest.get("observed_at") or ""),
                )
            )
        return items

    def _refresh_macro_data(self, repository: BotSocietyRepository) -> int:
        try:
            rows = self.macro_provider.generate(repository.count_pipeline_runs())
            self.macro_provider_fallback = False
            self.macro_provider_source = self.macro_provider.source_name
        except Exception:
            rows = self.demo_macro_provider.generate(repository.count_pipeline_runs())
            self.macro_provider_fallback = self.settings.macro_provider_mode != "demo"
            self.macro_provider_source = (
                f"{self.macro_provider.source_name}-fallback"
                if self.settings.macro_provider_mode != "demo"
                else self.demo_macro_provider.source_name
            )
        repository.upsert_macro_snapshots(rows)
        return len(rows)

    def _seed_demo_paper_trading(self, repository: BotSocietyRepository) -> int:
        if repository.list_paper_positions(self.settings.default_user_slug):
            return 0
        return self.simulate_paper_trading(self.settings.default_user_slug, limit=3).created_positions

    def _sync_paper_positions(self, repository: BotSocietyRepository, user_slug: str) -> int:
        closed_positions = 0
        for position in repository.list_paper_positions(user_slug, status="open"):
            prediction = repository.get_prediction(int(position["prediction_id"]))
            if not prediction or prediction.get("status") != "scored" or prediction.get("end_price") is None:
                continue
            realized_pnl = self._position_pnl(
                direction=str(position["direction"]),
                quantity=float(position["quantity"]),
                entry_price=float(position["entry_price"]),
                mark_price=float(prediction["end_price"]),
            ) - float(position.get("fees_paid") or 0.0)
            repository.update_paper_position(
                int(position["id"]),
                {
                    "status": "closed",
                    "closed_at": self._now(),
                    "exit_price": float(prediction["end_price"]),
                    "realized_pnl": round(realized_pnl, 2),
                },
            )
            closed_positions += 1
        return closed_positions

    def _paper_trade_allocation(self, available_cash: float, confidence: float) -> float:
        target = self.settings.paper_starting_balance * (0.04 + (0.09 * confidence))
        target = clamp(target, 350.0, self.settings.paper_starting_balance * 0.22)
        return round(min(available_cash, target), 2)

    @staticmethod
    def _position_pnl(*, direction: str, quantity: float, entry_price: float, mark_price: float) -> float:
        if direction == "bearish":
            return quantity * (entry_price - mark_price)
        if direction == "neutral":
            return -abs(quantity * (mark_price - entry_price)) * 0.25
        return quantity * (mark_price - entry_price)

    def _load_simulation_history(
        self,
        asset: str,
        lookback_years: int,
        source_mode: str = "auto",
    ) -> tuple[list[SimulationSeriesPoint], str, str | None]:
        repository = BotSocietyRepository(self.database)
        local_rows = repository.list_market_history(asset)
        local_points = [
            SimulationSeriesPoint(time=row["as_of"], value=float(row["price"]))
            for row in local_rows
        ]
        requested_end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        requested_start = requested_end - timedelta(days=365 * lookback_years)
        points = local_points
        data_source = "local-archive"
        history_note: str | None = None

        use_live_history = self.settings.simulation_live_history and source_mode != "local"
        if use_live_history:
            coin_id = self._asset_coin_id(asset)
            if coin_id:
                cached_payload = self._read_simulation_history_cache(asset)
                if self._simulation_cache_is_usable(cached_payload, requested_start, requested_end):
                    points = [
                        SimulationSeriesPoint(time=point["time"], value=float(point["value"]))
                        for point in cached_payload.get("points", [])
                    ]
                    data_source = "coingecko-history-cache"
                    history_note = "Using cached daily history for fast simulation runs."
                else:
                    try:
                        fetched_points = self.history_provider.fetch_history_range(
                            coin_id,
                            from_timestamp=int(requested_start.timestamp()),
                            to_timestamp=int(requested_end.timestamp()),
                        )
                    except Exception:
                        fetched_points = []
                    if fetched_points:
                        points = [
                            SimulationSeriesPoint(time=point["time"], value=float(point["value"]))
                            for point in fetched_points
                        ]
                        data_source = "coingecko-history"
                        history_note = "Using daily CoinGecko history for the requested lookback window."
                        self._write_simulation_history_cache(
                            asset,
                            {
                                "asset": asset,
                                "coin_id": coin_id,
                                "fetched_at": self._now(),
                                "start": points[0].time,
                                "end": points[-1].time,
                                "points": [point.model_dump() for point in points],
                            },
                        )

        filtered_points = [
            point for point in points
            if parse_timestamp(point.time) >= requested_start
        ]
        if len(filtered_points) >= 3:
            points = filtered_points

        if data_source == "local-archive":
            if source_mode == "local":
                history_note = "Using the deterministic local archive by request."
            elif source_mode == "real":
                history_note = "Real provider history was requested but unavailable, so the run fell back to the local archive."
            else:
                history_note = (
                    "Live history is disabled, so the simulation is running on the local archive."
                    if not self.settings.simulation_live_history
                    else "Live history was unavailable, so the simulation fell back to the local archive."
                )

        if len(points) >= 2:
            actual_years = (parse_timestamp(points[-1].time) - parse_timestamp(points[0].time)).days / 365.25
            if actual_years + 0.15 < lookback_years:
                suffix = f" Available coverage is {actual_years:.2f} years for {asset}."
                history_note = f"{history_note or ''}{suffix}".strip()

        return points, data_source, history_note

    def _asset_coin_id(self, asset: str) -> str | None:
        reverse_map = {symbol: coin_id for coin_id, symbol in CoinGeckoMarketProvider.SYMBOL_MAP.items()}
        return reverse_map.get(asset.upper())

    def _simulation_cache_path(self, asset: str) -> Path:
        cache_dir = self.settings.database_path.parent / "simulation_history_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir / f"{asset.lower()}.json"

    def _read_simulation_history_cache(self, asset: str) -> dict | None:
        cache_path = self._simulation_cache_path(asset)
        if not cache_path.exists():
            return None
        try:
            return json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def _write_simulation_history_cache(self, asset: str, payload: dict) -> None:
        cache_path = self._simulation_cache_path(asset)
        try:
            cache_path.write_text(json.dumps(payload), encoding="utf-8")
        except OSError:
            return

    def _simulation_cache_is_usable(
        self,
        payload: dict | None,
        requested_start: datetime,
        requested_end: datetime,
    ) -> bool:
        if not payload:
            return False
        try:
            fetched_at = parse_timestamp(payload["fetched_at"])
            cached_start = parse_timestamp(payload["start"])
            cached_end = parse_timestamp(payload["end"])
        except (KeyError, TypeError, ValueError):
            return False
        if fetched_at < datetime.now(timezone.utc) - timedelta(hours=self.settings.simulation_cache_hours):
            return False
        return cached_start <= requested_start and cached_end >= requested_end - timedelta(days=2)

    def _run_strategy_backtest(
        self,
        history_points: list[SimulationSeriesPoint],
        payload: SimulationRequest,
        strategy_id: str,
    ) -> SimulationStrategyResult:
        prices = [point.value for point in history_points]
        times = [point.time for point in history_points]
        fee_rate = payload.fee_bps / 10000
        equity = payload.starting_capital
        peak_equity = equity
        equity_curve = [SimulationSeriesPoint(time=times[0], value=round(equity, 2))]
        drawdown_curve = [SimulationSeriesPoint(time=times[0], value=0.0)]
        daily_returns: list[float] = []
        trades: list[SimulationTradeView] = []
        position = 0.0
        entry_time: str | None = None
        entry_price: float | None = None
        exposure_days = 0

        for index in range(1, len(prices)):
            previous_equity = equity
            desired_position = self._simulation_target_position(
                strategy_id,
                prices,
                index,
                position,
                payload,
                entry_price=entry_price,
            )
            execution_time = times[index - 1]
            execution_price = prices[index - 1]

            if desired_position != position:
                equity *= max(0.0, 1 - (fee_rate * abs(desired_position - position)))
                if position > 0 and entry_time is not None and entry_price is not None:
                    trades.append(
                        self._build_simulation_trade(
                            entry_time=entry_time,
                            exit_time=execution_time,
                            entry_price=entry_price,
                            exit_price=execution_price,
                            fee_rate=fee_rate,
                        )
                    )
                    entry_time = None
                    entry_price = None
                if desired_position > 0:
                    entry_time = execution_time
                    entry_price = execution_price
                position = desired_position

            interval_return = ((prices[index] / prices[index - 1]) - 1) if prices[index - 1] else 0.0
            equity *= 1 + (interval_return * position)
            if position > 0:
                exposure_days += 1
            realized_return = (equity / previous_equity) - 1 if previous_equity else 0.0
            daily_returns.append(realized_return)
            peak_equity = max(peak_equity, equity)
            drawdown = (equity / peak_equity) - 1 if peak_equity else 0.0
            equity_curve.append(SimulationSeriesPoint(time=times[index], value=round(equity, 2)))
            drawdown_curve.append(SimulationSeriesPoint(time=times[index], value=round(drawdown, 6)))

        if position > 0 and entry_time is not None and entry_price is not None:
            trades.append(
                self._build_simulation_trade(
                    entry_time=entry_time,
                    exit_time=times[-1],
                    entry_price=entry_price,
                    exit_price=prices[-1],
                    fee_rate=fee_rate,
                )
            )

        total_return = (equity / payload.starting_capital) - 1 if payload.starting_capital else 0.0
        total_days = max(1, (parse_timestamp(times[-1]) - parse_timestamp(times[0])).days)
        cagr = ((equity / payload.starting_capital) ** (365.25 / total_days) - 1) if total_days and payload.starting_capital else 0.0
        sharpe_ratio = 0.0
        if len(daily_returns) >= 2:
            volatility = pstdev(daily_returns)
            if volatility > 0:
                sharpe_ratio = (mean(daily_returns) / volatility) * (252 ** 0.5)
        positive_trades = sum(1 for trade in trades if trade.return_pct > 0)
        win_rate = (positive_trades / len(trades)) if trades else 0.0
        max_drawdown = min((point.value for point in drawdown_curve), default=0.0)
        preset = self._simulation_preset(strategy_id)
        label = payload.custom_strategy_name if strategy_id == "custom_creator" else preset.label
        summary = self._custom_creator_summary(payload) if strategy_id == "custom_creator" else preset.description
        return SimulationStrategyResult(
            strategy_id=preset.strategy_id,
            label=label,
            summary=summary,
            total_return=round(total_return, 6),
            cagr=round(cagr, 6),
            max_drawdown=round(max_drawdown, 6),
            sharpe_ratio=round(sharpe_ratio, 3),
            win_rate=round(win_rate, 3),
            trade_count=len(trades),
            exposure_ratio=round(exposure_days / max(1, len(prices) - 1), 3),
            final_equity=round(equity, 2),
            equity_curve=equity_curve,
            drawdown_curve=drawdown_curve,
            trades=trades[-12:],
        )

    def _simulation_target_position(
        self,
        strategy_id: str,
        prices: list[float],
        index: int,
        current_position: float,
        payload: SimulationRequest,
        *,
        entry_price: float | None = None,
    ) -> float:
        previous_price = prices[index - 1]
        if strategy_id == "buy_hold":
            return 1.0
        if strategy_id == "trend_follow":
            if index < payload.slow_window:
                return 0.0
            fast_average = mean(prices[index - payload.fast_window:index])
            slow_average = mean(prices[index - payload.slow_window:index])
            return 1.0 if previous_price >= fast_average and fast_average > slow_average else 0.0
        if strategy_id == "mean_reversion":
            if index < payload.mean_window:
                return 0.0
            baseline = mean(prices[index - payload.mean_window:index])
            deviation = ((previous_price / baseline) - 1) if baseline else 0.0
            if current_position > 0:
                return 0.0 if deviation >= -0.005 else 1.0
            return 1.0 if deviation <= -0.04 else 0.0
        if strategy_id == "breakout":
            if index < payload.breakout_window:
                return 0.0
            recent_window = prices[index - payload.breakout_window:index]
            recent_high = max(recent_window)
            trailing_window = prices[max(0, index - max(3, payload.breakout_window // 2)):index]
            trailing_low = min(trailing_window)
            if current_position > 0:
                return 0.0 if previous_price < trailing_low else 1.0
            return 1.0 if previous_price >= recent_high else 0.0
        if strategy_id == "custom_creator":
            return self._custom_creator_target_position(
                prices=prices,
                index=index,
                current_position=current_position,
                payload=payload,
                entry_price=entry_price,
            )
        return 0.0

    def _custom_creator_target_position(
        self,
        *,
        prices: list[float],
        index: int,
        current_position: float,
        payload: SimulationRequest,
        entry_price: float | None,
    ) -> float:
        previous_price = prices[index - 1]
        if entry_price:
            open_return = (previous_price / entry_price) - 1
            if open_return <= -payload.creator_stop_loss_pct:
                return 0.0
            if open_return >= payload.creator_take_profit_pct:
                return 0.0

        total_weight = (
            payload.creator_trend_weight
            + payload.creator_mean_reversion_weight
            + payload.creator_breakout_weight
        )
        if total_weight <= 0:
            return 0.0

        score = 0.0
        if payload.creator_trend_weight and index >= payload.slow_window:
            fast_average = mean(prices[index - payload.fast_window:index])
            slow_average = mean(prices[index - payload.slow_window:index])
            trend_signal = 1.0 if previous_price >= fast_average and fast_average > slow_average else 0.0
            score += trend_signal * payload.creator_trend_weight

        if payload.creator_mean_reversion_weight and index >= payload.mean_window:
            baseline = mean(prices[index - payload.mean_window:index])
            deviation = ((previous_price / baseline) - 1) if baseline else 0.0
            mean_signal = 1.0 if deviation <= -payload.creator_pullback_entry_pct else 0.0
            if current_position > 0 and deviation < 0:
                mean_signal = max(mean_signal, 0.45)
            score += mean_signal * payload.creator_mean_reversion_weight

        if payload.creator_breakout_weight and index >= payload.breakout_window:
            recent_window = prices[index - payload.breakout_window:index]
            recent_high = max(recent_window)
            trailing_window = prices[max(0, index - max(3, payload.breakout_window // 2)):index]
            trailing_low = min(trailing_window)
            breakout_signal = 1.0 if previous_price >= recent_high else 0.0
            if current_position > 0 and previous_price >= trailing_low:
                breakout_signal = max(breakout_signal, 0.35)
            score += breakout_signal * payload.creator_breakout_weight

        normalized_score = score / total_weight
        if current_position > 0:
            return payload.creator_max_exposure if normalized_score >= payload.creator_exit_score else 0.0
        return payload.creator_max_exposure if normalized_score >= payload.creator_entry_score else 0.0

    @staticmethod
    def _custom_creator_summary(payload: SimulationRequest) -> str:
        return (
            f"{payload.custom_strategy_name}: trend {payload.creator_trend_weight:.2f}, "
            f"pullback {payload.creator_mean_reversion_weight:.2f}, breakout {payload.creator_breakout_weight:.2f}; "
            f"enter >= {payload.creator_entry_score:.2f}, exit < {payload.creator_exit_score:.2f}, "
            f"max exposure {payload.creator_max_exposure:.0%}, stop {payload.creator_stop_loss_pct:.1%}, "
            f"take profit {payload.creator_take_profit_pct:.1%}."
        )

    def _build_simulation_trade(
        self,
        *,
        entry_time: str,
        exit_time: str,
        entry_price: float,
        exit_price: float,
        fee_rate: float,
    ) -> SimulationTradeView:
        gross_return = ((exit_price / entry_price) - 1) if entry_price else 0.0
        net_return = gross_return - (fee_rate * 2)
        holding_days = max(0, (parse_timestamp(exit_time) - parse_timestamp(entry_time)).days)
        return SimulationTradeView(
            opened_at=entry_time,
            closed_at=exit_time,
            entry_price=round(entry_price, 4),
            exit_price=round(exit_price, 4),
            return_pct=round(net_return, 6),
            holding_days=holding_days,
        )

    def _simulation_preset(self, strategy_id: str) -> SimulationStrategyPreset:
        for preset in self.SIMULATION_PRESETS:
            if preset.strategy_id == strategy_id:
                return preset
        return self.SIMULATION_PRESETS[0]

    def _provider_configuration(self, provider_type: str) -> tuple[bool, bool]:
        if provider_type == "market":
            if self.settings.market_provider_mode == "demo":
                return True, False
            if self.settings.market_provider_mode == "auto":
                return True, True
            if self.settings.market_provider_mode == "hyperliquid":
                return True, True
            configured = self.settings.coingecko_plan != "pro" or bool(self.settings.coingecko_api_key)
            return configured, configured

        if provider_type == "macro":
            if self.settings.macro_provider_mode == "demo":
                return True, False
            configured = bool(self.settings.fred_api_key)
            return configured, configured

        if provider_type == "wallet":
            if self.settings.wallet_provider_mode == "demo":
                return True, False
            configured = bool(self.settings.tracked_wallets)
            return configured, configured

        components = [self._primary_signal_provider_component()] + self._venue_signal_provider_components()
        configured = any(component.configured for component in components)
        live_capable = any(component.live_capable for component in components)
        return configured, live_capable

    def _social_discovery_provider_component(self) -> ProviderComponentStatus:
        source_name = getattr(self.social_discovery_provider, "source_name", self.settings.social_discovery_provider)
        if self.settings.social_discovery_provider == "youtube":
            configured = bool(self.settings.youtube_api_key)
            has_scope = bool(self.settings.youtube_discovery_queries or self.settings.youtube_channel_ids)
            ready = configured and has_scope
            warning = None
            if not configured:
                warning = "Set BSM_YOUTUBE_API_KEY before promoting YouTube discovery from demo fallback."
            elif not has_scope:
                warning = "Set BSM_YOUTUBE_DISCOVERY_QUERIES or BSM_YOUTUBE_CHANNEL_IDS so discovery has a search scope."
            return ProviderComponentStatus(
                mode="youtube",
                source=source_name,
                configured=configured,
                live_capable=True,
                ready=ready,
                warning=warning,
            )
        return ProviderComponentStatus(
            mode=self.settings.social_discovery_provider,
            source=source_name,
            configured=True,
            live_capable=False,
            ready=True,
            warning=None,
        )

    def _database_target(self) -> str:
        if self.database.dialect_name == "postgresql":
            if self.settings.deployment_target.startswith("render"):
                return "managed-postgres"
            target = self.settings.database_url or self.database.url
            if "render.com" in target:
                return "managed-postgres"
            return "postgres"
        return f"sqlite:{self.settings.database_path}"

    def _build_market_provider(self):
        if self.settings.market_provider_mode == "auto":
            return AutoMarketProvider(
                (
                    HyperliquidMarketProvider(
                        tracked_coin_ids=self.settings.tracked_coin_ids,
                        dex=self.settings.hyperliquid_dex,
                    ),
                    CoinGeckoMarketProvider(
                        plan=self.settings.coingecko_plan,
                        api_key=self.settings.coingecko_api_key,
                        tracked_coin_ids=self.settings.tracked_coin_ids,
                    ),
                )
            )
        if self.settings.market_provider_mode == "coingecko":
            return CoinGeckoMarketProvider(
                plan=self.settings.coingecko_plan,
                api_key=self.settings.coingecko_api_key,
                tracked_coin_ids=self.settings.tracked_coin_ids,
            )
        if self.settings.market_provider_mode == "hyperliquid":
            return HyperliquidMarketProvider(
                tracked_coin_ids=self.settings.tracked_coin_ids,
                dex=self.settings.hyperliquid_dex,
            )
        return self.demo_market_provider

    def _build_macro_provider(self):
        if self.settings.macro_provider_mode == "fred":
            return FredMacroProvider(
                api_key=self.settings.fred_api_key,
                series_ids=self.settings.fred_series_ids,
            )
        return self.demo_macro_provider

    def _build_wallet_provider(self):
        if self.settings.wallet_provider_mode == "polymarket":
            return PolymarketWalletProvider(
                tracked_wallets=self.settings.tracked_wallets,
                trade_limit=self.settings.wallet_trade_limit,
            )
        return self.demo_wallet_provider

    def _build_social_discovery_provider(self):
        if self.settings.social_discovery_provider == "youtube":
            return YouTubeSocialDiscoveryProvider(
                api_key=self.settings.youtube_api_key,
                queries=self.settings.youtube_discovery_queries,
                channel_ids=self.settings.youtube_channel_ids,
                video_limit=self.settings.youtube_video_limit,
                timeout_seconds=self.settings.outbound_timeout_seconds,
            )
        return DemoSocialDiscoveryProvider()

    def _build_signal_provider(self):
        if self.settings.signal_provider_mode == "rss":
            return RSSNewsSignalProvider(feed_urls=self.settings.rss_feed_urls)
        if self.settings.signal_provider_mode == "reddit":
            return RedditSignalProvider(
                client_id=self.settings.reddit_client_id,
                client_secret=self.settings.reddit_client_secret,
                user_agent=self.settings.reddit_user_agent,
                subreddits=self.settings.reddit_subreddits,
                post_limit=self.settings.reddit_post_limit,
            )
        return self.demo_signal_provider

    def _build_venue_signal_providers(self):
        providers = []
        for provider_mode in self.settings.venue_signal_providers:
            if provider_mode == "polymarket":
                providers.append(
                    PolymarketSignalProvider(
                        tag_id=self.settings.polymarket_tag_id,
                        event_limit=self.settings.polymarket_event_limit,
                    )
                )
            elif provider_mode == "kalshi":
                providers.append(
                    KalshiSignalProvider(
                        category=self.settings.kalshi_category,
                        series_limit=self.settings.kalshi_series_limit,
                        markets_per_series=self.settings.kalshi_markets_per_series,
                    )
                )
        return providers

    def _export_artifacts_dir(self) -> Path:
        path = Path(self.settings.export_artifacts_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _build_export_filename(self, payload: SimulationRequest) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return f"bsm-{payload.asset.lower()}-{payload.strategy_id}-{payload.lookback_years}y-{timestamp}.json"

    def _write_export_artifact(self, filename: str, payload: dict[str, object]) -> Path:
        target = self._export_artifacts_dir() / filename
        target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return target

    @staticmethod
    def _build_adapter_package_filename(export_filename: str) -> str:
        stem = export_filename[:-5] if export_filename.endswith(".json") else export_filename
        return f"{stem}-adapter-pack.zip"

    def _build_prediction_market_adapter_manifest(
        self,
        *,
        filename: str,
        package_filename: str,
        payload: SimulationRequest,
        result: SimulationRunResult,
        asset_edge: EdgeOpportunityView | None,
        related_wallets: list[WalletProfileView],
    ) -> dict[str, object]:
        strategy_mapping = self._prediction_market_strategy_mapping(payload)
        return {
            "generated_at": self._now(),
            "bridge_mode": "asset-to-event-market",
            "package_filename": package_filename,
            "export_filename": filename,
            "target_repository": "https://github.com/evan-kolberg/prediction-market-backtesting",
            "target_repository_inspected_on": "2026-04-10",
            "requires_market_mapping": True,
            "bridge_note": (
                "Bot Society Markets simulates asset-level research on BTC, ETH, and SOL. "
                "prediction-market-backtesting replays specific Polymarket event markets using PMXT historical order-book data, "
                "so the operator must map this asset thesis to one or more market slugs before running the external engine."
            ),
            "recommended_runner_data": {
                "platform": "Polymarket",
                "data_type": "QuoteTick",
                "vendor": "PMXT",
                "sources": (
                    "local:/path/to/pmxt/raw",
                    "archive:r2.pmxt.dev",
                    "relay:209-209-10-83.sslip.io",
                ),
            },
            "supported_local_file_layout": [
                "<raw_root>/polymarket_orderbook_YYYY-MM-DDTHH.parquet",
                "<raw_root>/YYYY/MM/DD/polymarket_orderbook_YYYY-MM-DDTHH.parquet",
            ],
            "required_raw_parquet_columns": ["market_id", "update_type", "data"],
            "required_json_payload_types": ["book_snapshot", "price_change"],
            "simulation_window": {
                "start_time": result.period_start,
                "end_time": result.period_end,
                "requested_lookback_years": payload.lookback_years,
                "actual_years_covered": result.actual_years_covered,
                "history_points": result.history_points,
                "data_source": result.data_source,
            },
            "selected_result_summary": {
                "strategy_id": result.selected_result.strategy_id,
                "label": result.selected_result.label,
                "total_return": result.selected_result.total_return,
                "cagr": result.selected_result.cagr,
                "max_drawdown": result.selected_result.max_drawdown,
                "sharpe_ratio": result.selected_result.sharpe_ratio,
                "trade_count": result.selected_result.trade_count,
                "win_rate": result.selected_result.win_rate,
                "benchmark_total_return": result.benchmark_total_return,
            },
            "suggested_strategy_mapping": strategy_mapping,
            "suggested_market_mapping": self._prediction_market_mapping_template(payload, result, asset_edge),
            "edge_context": asset_edge.model_dump() if asset_edge else None,
            "wallet_names": [wallet.display_name for wallet in related_wallets],
        }

    def _write_prediction_market_adapter_package(
        self,
        *,
        package_filename: str,
        export_filename: str,
        export_payload: dict[str, object],
        payload: SimulationRequest,
        result: SimulationRunResult,
        asset_edge: EdgeOpportunityView | None,
        related_wallets: list[WalletProfileView],
    ) -> Path:
        package_root = package_filename[:-4]
        target = self._export_artifacts_dir() / package_filename
        adapter_manifest = export_payload.get("prediction_market_adapter") or {}
        strategy_mapping = self._prediction_market_strategy_mapping(payload)
        market_mapping = self._prediction_market_mapping_template(payload, result, asset_edge)

        with zipfile.ZipFile(target, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                f"{package_root}/README.md",
                self._render_prediction_market_adapter_readme(
                    payload=payload,
                    result=result,
                    asset_edge=asset_edge,
                    related_wallets=related_wallets,
                    strategy_mapping=strategy_mapping,
                ),
            )
            archive.writestr(
                f"{package_root}/{export_filename}",
                json.dumps(export_payload, indent=2),
            )
            archive.writestr(
                f"{package_root}/adapter_manifest.json",
                json.dumps(adapter_manifest, indent=2),
            )
            archive.writestr(
                f"{package_root}/market_mapping_template.json",
                json.dumps(market_mapping, indent=2),
            )
            archive.writestr(
                f"{package_root}/strategy_config.json",
                json.dumps(strategy_mapping, indent=2),
            )
            archive.writestr(
                f"{package_root}/pmxt.env.example",
                self._render_prediction_market_env_example(),
            )
            archive.writestr(
                f"{package_root}/runner_template.py",
                self._render_prediction_market_runner_template(
                    payload=payload,
                    result=result,
                    strategy_mapping=strategy_mapping,
                ),
            )
        return target

    @staticmethod
    def _prediction_market_strategy_mapping(payload: SimulationRequest) -> dict[str, object]:
        trade_size = str(max(1, round(payload.starting_capital / 2000)))
        if payload.strategy_id == "trend_follow":
            return {
                "runner_label": "QuoteTick EMA crossover",
                "strategy_path": "strategies:QuoteTickEMACrossoverStrategy",
                "config_path": "strategies:QuoteTickEMACrossoverConfig",
                "config": {
                    "trade_size": trade_size,
                    "fast_period": payload.fast_window,
                    "slow_period": payload.slow_window,
                    "entry_buffer": round(max(0.0, payload.fee_bps / 10000), 4),
                    "take_profit": 0.01,
                    "stop_loss": 0.01,
                },
                "mapping_note": "Direct fit for Bot Society trend_follow.",
            }
        if payload.strategy_id == "mean_reversion":
            return {
                "runner_label": "QuoteTick mean reversion",
                "strategy_path": "strategies:QuoteTickMeanReversionStrategy",
                "config_path": "strategies:QuoteTickMeanReversionConfig",
                "config": {
                    "trade_size": trade_size,
                    "window": payload.mean_window,
                    "entry_threshold": 0.01,
                    "take_profit": 0.01,
                    "stop_loss": 0.015,
                },
                "mapping_note": "Direct fit for Bot Society mean_reversion.",
            }
        if payload.strategy_id == "breakout":
            return {
                "runner_label": "QuoteTick breakout",
                "strategy_path": "strategies:QuoteTickBreakoutStrategy",
                "config_path": "strategies:QuoteTickBreakoutConfig",
                "config": {
                    "trade_size": trade_size,
                    "window": payload.breakout_window,
                    "breakout_std": 1.5,
                    "take_profit": 0.015,
                    "stop_loss": 0.02,
                },
                "mapping_note": "Direct fit for Bot Society breakout.",
            }
        if payload.strategy_id == "custom_creator":
            return {
                "runner_label": "QuoteTick creator blend",
                "strategy_path": "strategies:QuoteTickCreatorBlendStrategy",
                "config_path": "strategies:QuoteTickCreatorBlendConfig",
                "config": {
                    "trade_size": trade_size,
                    "fast_window": payload.fast_window,
                    "slow_window": payload.slow_window,
                    "mean_window": payload.mean_window,
                    "breakout_window": payload.breakout_window,
                    "trend_weight": payload.creator_trend_weight,
                    "mean_reversion_weight": payload.creator_mean_reversion_weight,
                    "breakout_weight": payload.creator_breakout_weight,
                    "entry_score": payload.creator_entry_score,
                    "exit_score": payload.creator_exit_score,
                    "max_exposure": payload.creator_max_exposure,
                    "pullback_entry_pct": payload.creator_pullback_entry_pct,
                    "stop_loss_pct": payload.creator_stop_loss_pct,
                    "take_profit_pct": payload.creator_take_profit_pct,
                },
                "mapping_note": "Custom Bot Society creator blend; implement this strategy contract in the external engine.",
            }
        return {
            "runner_label": "QuoteTick deep value hold benchmark proxy",
            "strategy_path": "strategies:QuoteTickDeepValueHoldStrategy",
            "config_path": "strategies:QuoteTickDeepValueHoldConfig",
            "config": {
                "trade_size": trade_size,
                "entry_price_max": 0.55,
            },
            "mapping_note": "Buy-and-hold is approximated with a long-only hold proxy and should be tuned manually.",
        }

    @staticmethod
    def _prediction_market_mapping_template(
        payload: SimulationRequest,
        result: SimulationRunResult,
        asset_edge: EdgeOpportunityView | None,
    ) -> dict[str, object]:
        return {
            "mapped_from_asset": payload.asset,
            "market_slug": asset_edge.market_slug if asset_edge and asset_edge.market_slug else "replace-with-polymarket-market-slug",
            "token_index": 0,
            "condition_id": "replace-with-condition-id",
            "token_id": "replace-with-token-id",
            "outcome_label": "YES",
            "runner_start_time": result.period_start,
            "runner_end_time": result.period_end,
            "mapping_rationale": (
                f"Map the {payload.asset} thesis to a Polymarket event whose outcome depends materially on {payload.asset} direction, price, dominance, or macro spillover."
            ),
        }

    def _render_prediction_market_adapter_readme(
        self,
        *,
        payload: SimulationRequest,
        result: SimulationRunResult,
        asset_edge: EdgeOpportunityView | None,
        related_wallets: list[WalletProfileView],
        strategy_mapping: dict[str, object],
    ) -> str:
        edge_line = (
            f"- Matched edge surface: {asset_edge.market_label} ({asset_edge.edge_bps:+.0f} bps)\n"
            if asset_edge
            else "- Matched edge surface: none in the current snapshot\n"
        )
        wallet_line = (
            "- Smart-wallet overlays: " + ", ".join(wallet.display_name for wallet in related_wallets) + "\n"
            if related_wallets
            else "- Smart-wallet overlays: none specific to this asset export\n"
        )
        return dedent(
            f"""\
            # Bot Society Markets -> prediction-market-backtesting Adapter

            Generated: {self._now()}
            Asset: {payload.asset}
            Strategy: {payload.strategy_id}
            Window: {result.period_start} to {result.period_end}

            This package bridges an asset-level Bot Society Markets simulation into a prediction-market-backtesting research workflow.

            Important boundary:
            - Bot Society Markets currently simulates asset histories such as BTC, ETH, and SOL.
            - prediction-market-backtesting replays specific Polymarket event markets with PMXT historical order-book data.
            - You must map this asset thesis to a concrete Polymarket market before the runner can be used.

            Included files:
            - the original export bundle
            - `runner_template.py` shaped after the public runner contract used by prediction-market-backtesting
            - `market_mapping_template.json` for market slug, token index, condition ID, and token ID
            - `pmxt.env.example` for local raw PMXT archive setup

            Suggested bridge workflow:
            1. Open `market_mapping_template.json` and choose a Polymarket market tied to the same thesis.
            2. Fill in `market_slug`, `token_index`, `condition_id`, and `token_id`.
            3. Review `strategy_config.json` and tune the placeholder execution parameters if needed.
            4. Copy `runner_template.py` into the external repo's `backtests/` directory and run it there.

            Snapshot:
            - Selected result final equity: {result.selected_result.final_equity:.2f}
            - Selected result total return: {result.selected_result.total_return:+.4f}
            - Selected result sharpe: {result.selected_result.sharpe_ratio:.2f}
            - Selected result trade count: {result.selected_result.trade_count}
            - Benchmark total return: {result.benchmark_total_return:+.4f}
            {edge_line}{wallet_line}
            Suggested external runner:
            - Label: {strategy_mapping.get("runner_label")}
            - Strategy path: {strategy_mapping.get("strategy_path")}
            - Config path: {strategy_mapping.get("config_path")}
            - Mapping note: {strategy_mapping.get("mapping_note")}

            PMXT local raw archive expectations:
            - Supported layouts:
              - `<raw_root>/polymarket_orderbook_YYYY-MM-DDTHH.parquet`
              - `<raw_root>/YYYY/MM/DD/polymarket_orderbook_YYYY-MM-DDTHH.parquet`
            - Required raw parquet columns: `market_id`, `update_type`, `data`
            - Required JSON payload types: `book_snapshot`, `price_change`
            """
        )

    @staticmethod
    def _render_prediction_market_env_example() -> str:
        return dedent(
            """\
            # Point the external runner at a local PMXT raw archive mirror.
            PMXT_DATA_SOURCE=raw-local
            PMXT_LOCAL_RAWS_DIR=/data/pmxt/raw

            # Optional filtered-cache location.
            PMXT_CACHE_DIR=~/.cache/nautilus_trader/pmxt

            # Optional remote fallbacks.
            PMXT_SOURCE_PRIORITY=raw-local,raw-remote,relay-raw
            PMXT_REMOTE_BASE_URL=https://r2.pmxt.dev
            PMXT_RELAY_BASE_URL=https://209-209-10-83.sslip.io
            """
        )

    def _render_prediction_market_runner_template(
        self,
        *,
        payload: SimulationRequest,
        result: SimulationRunResult,
        strategy_mapping: dict[str, object],
    ) -> str:
        config = strategy_mapping.get("config") if isinstance(strategy_mapping.get("config"), dict) else {}
        config_lines = []
        for key, value in config.items():
            if key == "trade_size":
                config_lines.append(f'            "{key}": Decimal("{value}"),')
            elif isinstance(value, str):
                config_lines.append(f'            "{key}": "{value}",')
            else:
                config_lines.append(f'            "{key}": {value!r},')
        config_block = "\n".join(config_lines) if config_lines else '            # Fill strategy config values here.'
        runner_name = f"bot_society_{payload.asset.lower()}_{payload.strategy_id}_bridge"
        return dedent(
            f"""\
            \"\"\"
            Bot Society Markets bridge runner for prediction-market-backtesting.

            Fill in MARKET_MAPPING before running this file in the external repository.
            \"\"\"

            from __future__ import annotations

            from decimal import Decimal

            from prediction_market_extensions.backtesting._execution_config import ExecutionModelConfig
            from prediction_market_extensions.backtesting._execution_config import StaticLatencyConfig
            from prediction_market_extensions.backtesting._experiments import build_replay_experiment
            from prediction_market_extensions.backtesting._experiments import run_experiment
            from prediction_market_extensions.backtesting._prediction_market_backtest import MarketReportConfig
            from prediction_market_extensions.backtesting._prediction_market_runner import MarketDataConfig
            from prediction_market_extensions.backtesting._replay_specs import QuoteReplay
            from prediction_market_extensions.backtesting._timing_harness import timing_harness
            from prediction_market_extensions.backtesting.data_sources import PMXT, Polymarket, QuoteTick


            NAME = "{runner_name}"
            DESCRIPTION = "Bridge runner generated from a Bot Society Markets asset-level export"
            EMIT_HTML = True
            CHART_OUTPUT_PATH = "output"

            DATA = MarketDataConfig(
                platform=Polymarket,
                data_type=QuoteTick,
                vendor=PMXT,
                sources=(
                    "local:/path/to/pmxt/raw",
                    "archive:r2.pmxt.dev",
                    "relay:209-209-10-83.sslip.io",
                ),
            )

            MARKET_MAPPING = {{
                "market_slug": "replace-with-polymarket-market-slug",
                "token_index": 0,
                "condition_id": "replace-with-condition-id",
                "token_id": "replace-with-token-id",
                "mapped_from_asset": "{payload.asset}",
            }}

            REPLAYS = (
                QuoteReplay(
                    market_slug=MARKET_MAPPING["market_slug"],
                    token_index=MARKET_MAPPING["token_index"],
                    start_time="{result.period_start}",
                    end_time="{result.period_end}",
                ),
            )

            STRATEGY_CONFIGS = [
                {{
                    "strategy_path": "{strategy_mapping.get("strategy_path")}",
                    "config_path": "{strategy_mapping.get("config_path")}",
                    "config": {{
            {config_block}
                    }},
                }}
            ]

            REPORT = MarketReportConfig(
                count_key="quotes",
                count_label="Quotes",
                pnl_label="PnL (USDC)",
            )

            EXECUTION = ExecutionModelConfig(
                queue_position=True,
                latency_model=StaticLatencyConfig(
                    base_latency_ms=75.0,
                    insert_latency_ms=10.0,
                    update_latency_ms=5.0,
                    cancel_latency_ms=5.0,
                ),
            )

            EXPERIMENT = build_replay_experiment(
                name=NAME,
                description=DESCRIPTION,
                data=DATA,
                replays=REPLAYS,
                strategy_configs=STRATEGY_CONFIGS,
                initial_cash={max(100.0, round(payload.starting_capital * 0.01, 2))},
                probability_window=256,
                min_quotes=500,
                min_price_range=0.005,
                execution=EXECUTION,
                report=REPORT,
                empty_message="No bridge sims met the quote-tick requirements.",
                emit_html=EMIT_HTML,
                chart_output_path=CHART_OUTPUT_PATH,
            )


            @timing_harness
            def run() -> None:
                run_experiment(EXPERIMENT)


            if __name__ == "__main__":
                run()
            """
        )

    @staticmethod
    def _cache_is_fresh(cached_entry: tuple[datetime, object] | None, ttl_seconds: int = 90) -> bool:
        if not cached_entry:
            return False
        cached_at, _ = cached_entry
        return cached_at >= datetime.now(timezone.utc) - timedelta(seconds=ttl_seconds)

    def _clear_live_caches(self) -> None:
        self.provider_status_cache = None
        self.macro_snapshot_cache = None
        self.system_pulse_cache = None
        self.assets_cache = None
        self.leaderboard_cache.clear()
        self.landing_snapshot_cache.clear()
        self.dashboard_snapshot_cache.clear()

    def _use_fast_public_snapshots(self) -> bool:
        return self.settings.deployment_target == "akash" and bool(self.settings.database_url)

    def _warm_public_snapshot_caches(self) -> None:
        if not self._use_fast_public_snapshots():
            return
        try:
            user_slug = self.settings.default_user_slug
            self.get_assets()
            self.get_leaderboard(user_slug)
            self.get_macro_snapshot()
            self.get_system_pulse()
            self.get_landing_snapshot(user_slug)
            self.get_dashboard_snapshot(user_slug)
        except Exception:
            self._clear_live_caches()

    def _current_tracked_assets(self, repository: BotSocietyRepository | None = None) -> tuple[str, ...]:
        active_repository = repository or BotSocietyRepository(self.database)
        assets = tuple(asset.upper() for asset in active_repository.list_assets())
        if assets:
            return assets
        aliases = {
            "bitcoin": "BTC",
            "ethereum": "ETH",
            "solana": "SOL",
        }
        return tuple(aliases.get(coin.lower(), coin.upper()) for coin in self.settings.tracked_coin_ids)

    @staticmethod
    def _wallet_bias_for_asset(snapshot: WalletIntelligenceSnapshot, asset: str) -> float:
        relevant = [wallet for wallet in snapshot.wallets if wallet.primary_asset == asset]
        if not relevant:
            return snapshot.aggregate_bias * 0.35
        numerator = sum(wallet.net_bias * max(0.2, wallet.smart_money_score) for wallet in relevant)
        denominator = sum(max(0.2, wallet.smart_money_score) for wallet in relevant)
        return clamp(numerator / denominator if denominator else 0.0, -1.0, 1.0)

    @staticmethod
    def _wallet_confidence_for_asset(snapshot: WalletIntelligenceSnapshot, asset: str) -> float:
        relevant = [wallet for wallet in snapshot.wallets if wallet.primary_asset == asset]
        if not relevant:
            return 0.35
        return clamp(mean(wallet.smart_money_score for wallet in relevant), 0.0, 1.0)

    @staticmethod
    def _signal_sentiment_for_asset(signals: list[dict]) -> float:
        if not signals:
            return 0.0
        weighted_sum = 0.0
        weight_total = 0.0
        for signal in signals:
            weight = max(
                0.1,
                float(signal.get("source_quality_score") or 0.0) * 0.65
                + float(signal.get("relevance") or 0.0) * 0.35,
            )
            weighted_sum += float(signal.get("sentiment") or 0.0) * weight
            weight_total += weight
        return clamp(weighted_sum / weight_total if weight_total else 0.0, -1.0, 1.0)

    @staticmethod
    def _fair_probability(
        *,
        implied_probability: float,
        macro_bias: float,
        wallet_bias: float,
        signal_bias: float,
        trend_bias: float,
    ) -> float:
        adjustment = (
            (signal_bias * 0.12)
            + (wallet_bias * 0.08)
            + (macro_bias * 0.06)
            + (trend_bias * 0.04)
        )
        return clamp(implied_probability + adjustment, 0.02, 0.98)

    def _generate_signal_batch(self, market_batch: list[dict], cycle_index: int) -> list[dict]:
        signal_batch: list[dict] = []
        errors: list[str] = []
        try:
            primary_batch = self.signal_provider.generate(market_batch, cycle_index)
            if primary_batch:
                signal_batch.extend(primary_batch)
        except Exception as exc:
            errors.append(f"{self.signal_provider.source_name}: {exc.__class__.__name__}: {exc}")
        for provider in self.venue_signal_providers:
            try:
                venue_batch = provider.generate(market_batch, cycle_index)
                if venue_batch:
                    signal_batch.extend(venue_batch)
            except Exception as exc:
                errors.append(f"{provider.source_name}: {exc.__class__.__name__}: {exc}")
        if signal_batch:
            return signal_batch
        if errors:
            raise ValueError("; ".join(errors))
        return signal_batch

    def _compose_signal_provider_source(self) -> str:
        sources = [self.signal_provider.source_name] + [provider.source_name for provider in self.venue_signal_providers]
        unique_sources: list[str] = []
        for source in sources:
            if source not in unique_sources:
                unique_sources.append(source)
        return " + ".join(unique_sources)

    def _signal_live_active(self) -> bool:
        providers = [self.signal_provider] + self.venue_signal_providers
        return any(provider.source_name != self.demo_signal_provider.source_name for provider in providers)

    def _signal_provider_mode_label(self) -> str:
        if not self.venue_signal_providers:
            return self.settings.signal_provider_mode
        venue_modes = ", ".join(self.settings.venue_signal_providers)
        return f"{self.settings.signal_provider_mode} + {venue_modes}"

    def _primary_signal_provider_component(self) -> ProviderComponentStatus:
        readiness = self.signal_provider.readiness()
        if self.settings.signal_provider_mode == "demo":
            configured = True
            live_capable = False
        elif self.settings.signal_provider_mode == "rss":
            configured = bool(self.settings.rss_feed_urls)
            live_capable = configured
        else:
            configured = bool(self.settings.reddit_client_id and self.settings.reddit_client_secret and self.settings.reddit_subreddits)
            live_capable = configured
        return ProviderComponentStatus(
            mode=self.settings.signal_provider_mode,
            source=self.signal_provider.source_name,
            configured=configured,
            live_capable=live_capable,
            ready=readiness.ready,
            warning=readiness.warning,
        )

    def _venue_signal_provider_components(self) -> list[ProviderComponentStatus]:
        components: list[ProviderComponentStatus] = []
        for mode, provider in zip(self.settings.venue_signal_providers, self.venue_signal_providers):
            readiness = provider.readiness()
            components.append(
                ProviderComponentStatus(
                    mode=mode,
                    source=provider.source_name,
                    configured=True,
                    live_capable=True,
                    ready=readiness.ready,
                    warning=readiness.warning,
                )
            )
        return components

    def _signal_provider_health(self) -> tuple[bool, str | None, list[ProviderComponentStatus]]:
        components = [self._primary_signal_provider_component(), *self._venue_signal_provider_components()]
        ready = any(component.ready for component in components)
        warnings = [component.warning for component in components if component.warning]
        warning = "; ".join(warnings) if warnings else None
        return ready, warning, components[1:]

    @staticmethod
    def _to_asset_model(row: dict) -> AssetSnapshot:
        return AssetSnapshot(**row)

    def _social_trader_payload(self, trader: DiscoveredSocialTrader, *, now: str) -> dict[str, object]:
        return {
            "slug": trader.slug,
            "display_name": trader.display_name,
            "handle": trader.handle,
            "platform": trader.platform,
            "source_url": trader.source_url,
            "avatar_seed": trader.avatar_seed,
            "avatar_url": trader.avatar_url,
            "description": trader.description,
            "primary_assets_json": self._encode_json_payload(trader.primary_assets) or "[]",
            "style_tags_json": self._encode_json_payload(trader.style_tags) or "[]",
            "signal_count": trader.signal_count,
            "tracked_years": trader.tracked_years,
            "win_rate": trader.win_rate,
            "average_roi": trader.average_roi,
            "roi_if_followed": trader.roi_if_followed,
            "max_drawdown": trader.max_drawdown,
            "sharpe_like": trader.sharpe_like,
            "consistency_score": trader.consistency_score,
            "influence_score": trader.influence_score,
            "recency_score": trader.recency_score,
            "composite_score": trader.composite_score,
            "last_signal_at": trader.last_signal_at,
            "state": "discovered",
            "created_at": now,
            "updated_at": now,
        }

    def _social_event_payloads(
        self,
        trader_id: int,
        evidence: list[SocialEvidenceRecord],
        *,
        now: str,
    ) -> list[dict[str, object]]:
        return [
            {
                "trader_id": trader_id,
                "external_id": item.external_id,
                "platform": item.platform,
                "title": item.title[:255],
                "summary": item.summary,
                "url": item.url,
                "asset": item.asset,
                "direction": item.direction,
                "confidence": item.confidence,
                "engagement_score": item.engagement_score,
                "observed_at": item.observed_at,
                "derived_return": item.derived_return,
                "created_at": now,
            }
            for item in evidence
        ]

    def _social_signal_payloads(
        self,
        traders: list[DiscoveredSocialTrader],
        *,
        provider: str,
        ingest_batch_id: str,
    ) -> list[dict[str, object]]:
        payloads: list[dict[str, object]] = []
        for trader in traders:
            for item in trader.evidence:
                sentiment = self._direction_to_sentiment(item.direction, item.confidence)
                payloads.append(
                    {
                        "external_id": f"social-signal-{item.external_id}",
                        "asset": item.asset[:16],
                        "source": trader.source_url,
                        "provider_name": provider,
                        "source_type": "social",
                        "author_handle": trader.handle,
                        "engagement_score": item.engagement_score,
                        "provider_trust_score": round(min(0.96, 0.58 + trader.composite_score / 240), 6),
                        "freshness_score": self._freshness_score(item.observed_at),
                        "source_quality_score": round(
                            min(
                                0.98,
                                max(
                                    0.2,
                                    (item.confidence * 0.48)
                                    + (item.engagement_score * 0.18)
                                    + (trader.consistency_score * 0.2)
                                    + (trader.recency_score * 0.14),
                                ),
                            ),
                            6,
                        ),
                        "channel": "social",
                        "title": item.title[:255],
                        "summary": (
                            f"{trader.display_name} produced a {item.direction} {item.asset} creator signal. "
                            f"{item.summary}"
                        ),
                        "sentiment": sentiment,
                        "relevance": round(min(0.98, max(0.35, item.confidence * 0.72 + item.engagement_score * 0.28)), 6),
                        "url": item.url,
                        "observed_at": item.observed_at,
                        "ingest_batch_id": ingest_batch_id,
                    }
                )
        return payloads

    @staticmethod
    def _direction_to_sentiment(direction: str, confidence: float) -> float:
        if direction == "bullish":
            return round(min(1.0, max(0.05, confidence)), 6)
        if direction == "bearish":
            return round(max(-1.0, min(-0.05, -confidence)), 6)
        return 0.0

    @staticmethod
    def _freshness_score(observed_at: str | None) -> float:
        age_days = max(0, (datetime.now(timezone.utc) - parse_timestamp(observed_at)).days) if observed_at else 365
        return round(max(0.08, min(1.0, 1 - (age_days / 180))), 6)

    def _to_social_trader_scorecard(
        self,
        row: dict,
        event_rows: list[dict] | None = None,
    ) -> SocialTraderScorecard:
        evidence = [self._to_social_evidence_item(event_row) for event_row in (event_rows or [])]
        risk_level = self._social_trader_risk_level(row)
        copy_trade_readiness = self._social_copy_trade_readiness(row, risk_level)
        primary_assets = self._decode_string_list(row.get("primary_assets_json"))
        style_tags = self._decode_string_list(row.get("style_tags_json"))
        return SocialTraderScorecard(
            id=int(row["id"]),
            slug=str(row["slug"]),
            display_name=str(row["display_name"]),
            handle=str(row["handle"]),
            platform=str(row["platform"]),
            source_url=str(row["source_url"]),
            avatar_seed=str(row["avatar_seed"]),
            avatar_url=row.get("avatar_url"),
            description=str(row["description"]),
            primary_assets=primary_assets,
            style_tags=style_tags,
            signal_count=int(row.get("signal_count") or 0),
            tracked_years=round(float(row.get("tracked_years") or 0), 2),
            win_rate=round(float(row.get("win_rate") or 0), 3),
            average_roi=round(float(row.get("average_roi") or 0), 4),
            roi_if_followed=round(float(row.get("roi_if_followed") or 0), 4),
            max_drawdown=round(float(row.get("max_drawdown") or 0), 4),
            sharpe_like=round(float(row.get("sharpe_like") or 0), 3),
            consistency_score=round(float(row.get("consistency_score") or 0), 3),
            influence_score=round(float(row.get("influence_score") or 0), 3),
            recency_score=round(float(row.get("recency_score") or 0), 3),
            composite_score=round(float(row.get("composite_score") or 0), 2),
            last_signal_at=row.get("last_signal_at"),
            state=str(row.get("state") or "discovered"),
            risk_level=risk_level,
            conviction_label=self._social_conviction_label(row),
            copy_trade_readiness=copy_trade_readiness,
            watch_mode_recommendation=self._social_watch_mode_recommendation(row, risk_level, copy_trade_readiness),
            evidence_summary=self._social_evidence_summary(evidence),
            risk_notes=self._social_risk_notes(row, evidence, risk_level),
            allocation_guidance=self._social_allocation_guidance(row, risk_level, copy_trade_readiness),
            evidence=evidence,
            strategy_profile=self._social_strategy_profile(row, evidence, style_tags),
            current_market_view=self._social_current_market_view(row, evidence),
            pnl_history_summary=self._social_pnl_history_summary(row, evidence),
            roi_windows=self._social_roi_windows(row, evidence),
            decision_feed=self._social_decision_feed(row, evidence),
            asset_exposure=self._social_asset_exposure(evidence, primary_assets),
        )

    @staticmethod
    def _to_social_evidence_item(row: dict) -> SocialEvidenceItem:
        confidence = round(float(row.get("confidence") or 0), 3)
        engagement_score = round(float(row.get("engagement_score") or 0), 3)
        derived_return = round(float(row.get("derived_return") or 0), 4)
        return SocialEvidenceItem(
            external_id=str(row["external_id"]),
            platform=str(row["platform"]),
            title=str(row["title"]),
            summary=str(row["summary"]),
            url=str(row["url"]),
            asset=str(row["asset"]),
            direction=str(row["direction"]),
            confidence=confidence,
            engagement_score=engagement_score,
            evidence_weight=round(min(1.0, max(0.0, (confidence * 0.68) + (engagement_score * 0.32))), 3),
            impact_label=BotSocietyService._social_evidence_impact_label(derived_return),
            risk_flag=BotSocietyService._social_evidence_risk_flag(confidence, derived_return),
            observed_at=str(row["observed_at"]),
            derived_return=derived_return,
        )

    def _social_roi_windows(self, row: dict, evidence: list[SocialEvidenceItem]) -> list[SocialRoiWindow]:
        risk_level = self._social_trader_risk_level(row)
        readiness = self._social_copy_trade_readiness(row, risk_level)
        allocation = self._social_allocation_guidance(row, risk_level, readiness)
        base_capital = max(1000.0, float(allocation.get("suggested_allocation_usd") or 1000.0))
        now = datetime.now(timezone.utc)
        windows = [
            ("1W", 7),
            ("1M", 30),
            ("1Y", 365),
            ("10Y", 3650),
            ("Overall", 0),
        ]
        results: list[SocialRoiWindow] = []
        for label, days in windows:
            selected = evidence
            if days:
                selected = [
                    item for item in evidence
                    if (now - parse_timestamp(item.observed_at)).days <= days
                ]
            if not selected and label != "Overall":
                results.append(
                    SocialRoiWindow(
                        label=label,
                        period_days=days,
                        return_pct=0.0,
                        pnl_usd=0.0,
                        signal_count=0,
                        win_rate=0.0,
                    )
                )
                continue
            compounded = 1.0
            for item in selected:
                compounded *= 1 + float(item.derived_return or 0)
            return_pct = compounded - 1 if selected else float(row.get("roi_if_followed") or 0)
            win_rate = len([item for item in selected if float(item.derived_return or 0) > 0]) / len(selected) if selected else float(row.get("win_rate") or 0)
            results.append(
                SocialRoiWindow(
                    label=label,
                    period_days=days,
                    return_pct=round(return_pct, 4),
                    pnl_usd=round(base_capital * return_pct, 2),
                    signal_count=len(selected) if selected else int(row.get("signal_count") or 0),
                    win_rate=round(win_rate, 3),
                )
            )
        return results

    @staticmethod
    def _social_decision_feed(row: dict, evidence: list[SocialEvidenceItem]) -> list[SocialTraderDecision]:
        display_name = str(row.get("display_name") or "This trader")
        decisions: list[SocialTraderDecision] = []
        for item in evidence[:5]:
            if item.direction == "bullish":
                action = "paper_buy_or_watch"
                posture = "watch for a long setup"
            elif item.direction == "bearish":
                action = "reduce_or_short_watch"
                posture = "avoid longs or watch for downside"
            else:
                action = "hold_research_only"
                posture = "wait for confirmation"
            decisions.append(
                SocialTraderDecision(
                    asset=item.asset,
                    direction=item.direction,
                    action=action,
                    confidence=item.confidence,
                    rationale=(
                        f"{display_name} published a {item.direction} {item.asset} thesis; "
                        f"BITprivat would {posture} with evidence weight {item.evidence_weight:.0%}."
                    ),
                    source_title=item.title,
                    source_url=item.url,
                    observed_at=item.observed_at,
                )
            )
        return decisions

    @staticmethod
    def _social_asset_exposure(evidence: list[SocialEvidenceItem], primary_assets: list[str]) -> list[SocialTraderAssetExposure]:
        grouped: dict[str, list[SocialEvidenceItem]] = defaultdict(list)
        for item in evidence:
            grouped[item.asset].append(item)
        if not grouped:
            for asset in primary_assets[:4]:
                grouped[asset] = []
        exposures: list[SocialTraderAssetExposure] = []
        for asset, items in sorted(grouped.items(), key=lambda pair: len(pair[1]), reverse=True)[:6]:
            bullish = len([item for item in items if item.direction == "bullish"])
            bearish = len([item for item in items if item.direction == "bearish"])
            if bullish > bearish:
                bias = "bullish"
            elif bearish > bullish:
                bias = "bearish"
            else:
                bias = "neutral"
            average_return = mean(float(item.derived_return or 0) for item in items) if items else 0.0
            exposures.append(
                SocialTraderAssetExposure(
                    asset=asset,
                    signal_count=len(items),
                    bias=bias,
                    average_return=round(average_return, 4),
                )
            )
        return exposures

    @staticmethod
    def _social_strategy_profile(row: dict, evidence: list[SocialEvidenceItem], style_tags: list[str]) -> str:
        tags = ", ".join(style_tags[:3]) if style_tags else "creator signals"
        assets = sorted({item.asset for item in evidence})[:4]
        asset_text = ", ".join(assets) if assets else "tracked assets"
        win_rate = float(row.get("win_rate") or 0)
        if win_rate >= 0.6:
            posture = "follow-strength"
        elif win_rate < 0.5:
            posture = "confirmation-required"
        else:
            posture = "selective-follow"
        return f"{posture} strategy using {tags}; focuses on {asset_text}, with public calls converted into paper-only signals."

    @staticmethod
    def _social_current_market_view(row: dict, evidence: list[SocialEvidenceItem]) -> str:
        if not evidence:
            return "No fresh creator view is indexed yet; run YouTube discovery to update the thesis."
        latest = evidence[0]
        return (
            f"Latest view: {latest.direction} {latest.asset} from '{latest.title}'. "
            f"Confidence {latest.confidence:.0%}; BITprivat action is {('watch long setups' if latest.direction == 'bullish' else 'protect downside' if latest.direction == 'bearish' else 'stay neutral')}."
        )

    @staticmethod
    def _social_pnl_history_summary(row: dict, evidence: list[SocialEvidenceItem]) -> str:
        if not evidence:
            return "No simulated follow history is available yet."
        roi = float(row.get("roi_if_followed") or 0)
        avg = float(row.get("average_roi") or 0)
        drawdown = float(row.get("max_drawdown") or 0)
        return (
            f"If BITprivat had paper-followed the indexed calls, proxy ROI is {roi:+.1%}, "
            f"average call return {avg:+.1%}, max drawdown {drawdown:.1%}, across {int(row.get('signal_count') or len(evidence))} signal(s)."
        )

    @staticmethod
    def _social_evidence_impact_label(derived_return: float) -> str:
        if derived_return >= 0.08:
            return "strong positive"
        if derived_return >= 0.02:
            return "positive"
        if derived_return <= -0.08:
            return "large miss"
        if derived_return <= -0.02:
            return "negative"
        return "flat"

    @staticmethod
    def _social_evidence_risk_flag(confidence: float, derived_return: float) -> str | None:
        if confidence < 0.45:
            return "low confidence extraction"
        if derived_return <= -0.1:
            return "recent call moved sharply against thesis"
        return None

    @staticmethod
    def _social_trader_risk_level(row: dict) -> str:
        signal_count = int(row.get("signal_count") or 0)
        win_rate = float(row.get("win_rate") or 0)
        max_drawdown = float(row.get("max_drawdown") or 0)
        consistency_score = float(row.get("consistency_score") or 0)
        composite_score = float(row.get("composite_score") or 0)
        if max_drawdown <= -0.18 or win_rate < 0.46 or consistency_score < 0.42:
            return "high"
        if (
            signal_count >= 8
            and win_rate >= 0.58
            and max_drawdown >= -0.08
            and consistency_score >= 0.65
            and composite_score >= 62
        ):
            return "low"
        return "medium"

    @staticmethod
    def _social_conviction_label(row: dict) -> str:
        composite_score = float(row.get("composite_score") or 0)
        if composite_score >= 72:
            return "High conviction tracker"
        if composite_score >= 58:
            return "Validated paper candidate"
        if composite_score >= 45:
            return "Signal watchlist"
        return "Research only"

    @staticmethod
    def _social_copy_trade_readiness(row: dict, risk_level: str) -> str:
        signal_count = int(row.get("signal_count") or 0)
        win_rate = float(row.get("win_rate") or 0)
        max_drawdown = float(row.get("max_drawdown") or 0)
        composite_score = float(row.get("composite_score") or 0)
        if signal_count < 5 or composite_score < 45:
            return "needs_review"
        if risk_level == "high":
            return "signals_only"
        if composite_score >= 58 and win_rate >= 0.52 and max_drawdown > -0.22:
            return "paper_ready"
        return "signals_only"

    @staticmethod
    def _social_watch_mode_recommendation(row: dict, risk_level: str, readiness: str) -> str:
        display_name = str(row.get("display_name") or "This trader")
        if readiness == "paper_ready":
            return f"Start {display_name} in managed-paper mode with a capped allocation and weekly review."
        if readiness == "needs_review":
            return f"Keep {display_name} in research mode until more evidence is indexed."
        if risk_level == "high":
            return f"Use signal-only alerts for {display_name}; do not auto-allocate until drawdown improves."
        return f"Use signal-only alerts for {display_name}, then promote after fresh calls validate."

    @staticmethod
    def _social_evidence_summary(evidence: list[SocialEvidenceItem]) -> str:
        if not evidence:
            return "No recent public evidence has been indexed yet."
        assets = sorted({item.asset for item in evidence if item.asset})[:4]
        directions = defaultdict(int)
        for item in evidence:
            directions[item.direction] += 1
        dominant_direction = max(directions.items(), key=lambda item: item[1])[0] if directions else "neutral"
        average_confidence = mean(item.confidence for item in evidence)
        average_return = mean(item.derived_return for item in evidence)
        asset_text = ", ".join(assets) if assets else "tracked assets"
        return (
            f"{len(evidence)} recent evidence item(s) across {asset_text}; "
            f"{dominant_direction} bias, {average_confidence:.0%} average confidence, "
            f"{average_return:+.1%} average resolved move."
        )

    @staticmethod
    def _social_risk_notes(row: dict, evidence: list[SocialEvidenceItem], risk_level: str) -> list[str]:
        signal_count = int(row.get("signal_count") or 0)
        win_rate = float(row.get("win_rate") or 0)
        max_drawdown = float(row.get("max_drawdown") or 0)
        platform = str(row.get("platform") or "social")
        notes: list[str] = []
        if signal_count < 10:
            notes.append("Sample size is still thin; keep this profile below normal allocation size.")
        if max_drawdown <= -0.15:
            notes.append(f"Historical proxy drawdown reached {max_drawdown:.1%}; cap exposure aggressively.")
        if win_rate < 0.5:
            notes.append(f"Win rate is below 50% at {win_rate:.0%}; require confirmation before managed allocation.")
        if any(item.risk_flag for item in evidence):
            notes.append("At least one recent evidence item carries a confidence or adverse-move warning.")
        if platform == "youtube":
            notes.append("YouTube narratives can lag trade entries; treat videos as thesis evidence, not verified fills.")
        if risk_level == "low":
            notes.append("Risk profile is comparatively stable, but every allocation should remain paper-only until compliance is live.")
        else:
            notes.append("Managed mode remains paper-only until live execution, suitability, and audit controls are approved.")
        return notes[:4]

    def _social_allocation_guidance(self, row: dict, risk_level: str, readiness: str) -> dict[str, object]:
        portfolio = max(float(self.settings.paper_starting_balance or 0), 1000.0)
        composite_score = float(row.get("composite_score") or 0)
        risk_multiplier = {"low": 0.16, "medium": 0.1, "high": 0.04}.get(risk_level, 0.06)
        max_position_pct = {"low": 0.12, "medium": 0.08, "high": 0.04}.get(risk_level, 0.06)
        recommended_mode = "managed_paper" if readiness == "paper_ready" else "signals"
        if readiness == "needs_review":
            suggested_allocation = 0.0
        else:
            score_multiplier = min(1.15, max(0.35, composite_score / 75))
            suggested_allocation = min(portfolio * 0.25, portfolio * risk_multiplier * score_multiplier)
            if recommended_mode == "signals":
                suggested_allocation = min(suggested_allocation, portfolio * 0.05)
        suggested_allocation = round(suggested_allocation, 2)
        max_single_position = round(suggested_allocation * max_position_pct, 2)
        if readiness == "paper_ready":
            rationale = "Metrics support a small managed-paper pilot with hard caps and review cadence."
        elif readiness == "needs_review":
            rationale = "Not enough high-quality evidence yet; collect more calls before allocating capital."
        else:
            rationale = "Useful signal source, but risk or consistency keeps it out of managed-paper mode for now."
        return {
            "recommended_mode": recommended_mode,
            "suggested_allocation_usd": suggested_allocation,
            "max_single_position_usd": max_single_position,
            "max_position_pct": max_position_pct,
            "rationale": rationale,
        }

    @staticmethod
    def _to_social_trader_allocation(row: dict) -> SocialTraderAllocation:
        return SocialTraderAllocation(
            id=int(row["id"]),
            user_slug=str(row["user_slug"]),
            trader_id=int(row["trader_id"]),
            trader_slug=str(row["trader_slug"]),
            trader_name=str(row["trader_name"]),
            mode=str(row["mode"]),
            allocation_limit_usd=round(float(row.get("allocation_limit_usd") or 0), 2),
            max_position_pct=round(float(row.get("max_position_pct") or 0), 4),
            auto_rebalance=bool(row.get("auto_rebalance")),
            is_active=bool(row.get("is_active")),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    def _to_social_discovery_run(self, row: dict) -> SocialDiscoveryRunView:
        warnings_payload = self._decode_json_payload(row.get("warnings_json"))
        warnings = [str(item) for item in warnings_payload] if isinstance(warnings_payload, list) else []
        return SocialDiscoveryRunView(
            id=int(row["id"]),
            provider=str(row["provider"]),
            status=str(row["status"]),
            youtube_configured=bool(row.get("youtube_configured")),
            discovered=int(row.get("discovered_count") or 0),
            updated=int(row.get("updated_count") or 0),
            evidence_count=int(row.get("evidence_count") or 0),
            warnings=warnings,
            started_at=str(row["started_at"]),
            completed_at=str(row["completed_at"]),
        )

    def _social_monitoring_status(self, discovery_runs: list[SocialDiscoveryRunView]) -> SocialMonitoringStatus:
        latest = discovery_runs[0] if discovery_runs else None
        live_ready = self.settings.social_discovery_provider == "youtube" and bool(self.settings.youtube_api_key)
        if live_ready:
            mode = "continuous-youtube-api"
            next_action = "Worker cycle will search new YouTube videos by configured title/query terms, hydrate metadata, and create bot signals."
        else:
            mode = "demo-youtube-watchlist"
            next_action = "Add BSM_YOUTUBE_API_KEY and set BSM_SOCIAL_DISCOVERY_PROVIDER=youtube to monitor live creators."
        return SocialMonitoringStatus(
            mode=mode,
            cadence_seconds=int(self.settings.social_discovery_interval_seconds),
            provider=getattr(self.social_discovery_provider, "source_name", self.settings.social_discovery_provider),
            youtube_configured=bool(self.settings.youtube_api_key),
            query_terms=list(self.settings.youtube_discovery_queries),
            channel_ids=list(self.settings.youtube_channel_ids),
            title_filter=", ".join(self.settings.youtube_discovery_queries)
            or "configured channel uploads ordered by newest videos",
            analysis_pipeline=[
                "YouTube search.list ordered by date",
                "videos.list snippet/statistics hydration",
                "channels.list public avatar metadata",
                "public handle/channel RSS fallback when API quota is exhausted",
                "title and description asset/direction extraction",
                "normalized social signals for bot scoring",
                "paper-only allocation/deployment controls",
            ],
            auto_signal_creation=True,
            next_action=(
                f"{next_action} Last run: {latest.status} {latest.completed_at}."
                if latest
                else next_action
            ),
        )

    def _social_diversification_plan(
        self,
        top_traders: list[SocialTraderScorecard],
        allocations: list[SocialTraderAllocation],
    ) -> list[str]:
        followed_ids = {allocation.trader_id for allocation in allocations if allocation.is_active}
        candidates = [trader for trader in top_traders if trader.id not in followed_ids][:3]
        if not candidates:
            return [
                "Keep each manager below the configured allocation cap.",
                "Review paper results weekly before increasing exposure.",
                "Diversify across at least one macro, one prediction-market, and one on-chain style.",
            ]
        return [
            f"Start {trader.display_name} in {trader.allocation_guidance.recommended_mode.replace('_', ' ')} mode; suggested cap {trader.allocation_guidance.suggested_allocation_usd:,.0f} USD."
            for trader in candidates
        ]

    @staticmethod
    def _social_portfolio_risk_notes(
        top_traders: list[SocialTraderScorecard],
        allocations: list[SocialTraderAllocation],
        *,
        allocated_usd: float,
        portfolio_limit: float,
        youtube_configured: bool,
    ) -> list[str]:
        notes: list[str] = []
        exposure_ratio = allocated_usd / portfolio_limit if portfolio_limit else 0
        active_trader_ids = {allocation.trader_id for allocation in allocations if allocation.is_active}
        high_risk_followed = [
            trader.display_name for trader in top_traders if trader.id in active_trader_ids and trader.risk_level == "high"
        ]
        if allocated_usd <= 0:
            notes.append("No paper capital is assigned yet; begin with signal mode before managed-paper allocation.")
        else:
            notes.append(f"Active social-manager exposure is {exposure_ratio:.0%} of the configured paper portfolio limit.")
        if exposure_ratio > 0.35:
            notes.append("Social-manager exposure is above the recommended launch ceiling; rebalance across independent strategies.")
        if high_risk_followed:
            notes.append(f"High-risk followed profile(s): {', '.join(high_risk_followed[:3])}. Keep them signal-only or reduce caps.")
        if not youtube_configured:
            notes.append("YouTube discovery is using demo evidence until BSM_YOUTUBE_API_KEY is configured in production secrets.")
        notes.append("Never graduate social copy trading to live funds without KYC, suitability, disclosures, and venue permissions.")
        return notes[:4]

    def _decode_string_list(self, raw_payload: object) -> list[str]:
        payload = self._decode_json_payload(str(raw_payload) if raw_payload is not None else None)
        if isinstance(payload, list):
            return [str(item) for item in payload if str(item).strip()]
        return []

    @staticmethod
    def _to_signal_model(row: dict) -> SignalView:
        return SignalView(**row)

    @staticmethod
    def _to_prediction_model(row: dict, provenance: dict[str, object] | None = None) -> PredictionView:
        payload = {
            **row,
            "directional_success": bool(row["directional_success"]) if row["directional_success"] is not None else None,
            **(provenance or {}),
        }
        return PredictionView(**payload)

    @staticmethod
    def _to_alert_model(row: dict) -> AlertDelivery:
        payload = {
            **row,
            "is_read": row["read_at"] is not None,
        }
        return AlertDelivery(**payload)

    def _latest_operation(self, repository: BotSocietyRepository) -> OperationSnapshot | None:
        row = repository.get_latest_pipeline_run()
        return self._to_operation_model(row)

    @staticmethod
    def _to_operation_model(row: dict | None) -> OperationSnapshot | None:
        if not row:
            return None
        return OperationSnapshot(**row)

    @staticmethod
    def _alert_scope(rule: dict) -> str:
        target = []
        if rule["bot_slug"]:
            target.append(f"bot {rule['bot_slug']}")
        if rule["asset"]:
            target.append(f"asset {rule['asset']}")
        target_text = " and ".join(target) if target else "alert rule"
        threshold = int(round(float(rule["min_confidence"]) * 100))
        return f"{target_text} at {threshold}% min confidence"

    def _next_delivery_state(self, attempt_count: int) -> tuple[str, str | None]:
        if attempt_count >= self.settings.notification_max_attempts:
            return "exhausted", None
        retry_delay = self.settings.notification_retry_base_seconds * max(1, 2 ** (attempt_count - 1))
        next_attempt = datetime.now(timezone.utc) + timedelta(seconds=retry_delay)
        return "retry_scheduled", to_timestamp(next_attempt)

    def _billing_plan_catalog(self) -> list[BillingPlanView]:
        return [
            BillingPlanView(
                key="basic",
                label="Starter",
                headline="Retail subscription for personal research workspaces.",
                price_id=self.settings.stripe_basic_price_id,
                configured=bool(self.settings.stripe_basic_price_id),
                recommended=not bool(self.settings.stripe_pro_price_id),
                features=[
                    "Private workspace with watchlists, alerts, and signal inbox",
                    "Hosted Stripe checkout with no raw card handling on your servers",
                    "Ready for SaaS activation on the live dashboard",
                ],
            ),
            BillingPlanView(
                key="pro",
                label="Pro",
                headline="Deeper analytics, priority support, and heavier research usage.",
                price_id=self.settings.stripe_pro_price_id,
                configured=bool(self.settings.stripe_pro_price_id),
                recommended=True,
                features=[
                    "Designed for advanced retail traders and small teams",
                    "Best fit for premium Strategy Lab and connector entitlements",
                    "Clean upgrade path from Starter without rebuilding billing",
                ],
            ),
            BillingPlanView(
                key="enterprise",
                label="Enterprise",
                headline="Custom invoicing and managed deployment paths for teams.",
                price_id=self.settings.stripe_enterprise_price_id,
                configured=bool(self.settings.stripe_enterprise_price_id),
                recommended=False,
                features=[
                    "Supports enterprise onboarding and procurement workflows",
                    "Fits managed environments, SSO, and custom integrations later",
                    "Keeps the product ready for higher-trust commercial sales",
                ],
            ),
        ]

    def _billing_summary_text(
        self,
        *,
        configured: bool,
        configured_plan_count: int,
        active_subscription: bool,
        plan_key: str | None,
        subscription_status: str | None,
    ) -> str:
        if not configured:
            return "Stripe billing is not configured on this deployment yet."
        if not configured_plan_count:
            return "Stripe keys are present, but no live price IDs are wired into the app yet."
        if active_subscription:
            label = self._plan_label(plan_key) or "paid"
            return f"Workspace billing is active on the {label} plan. Subscription status: {subscription_status or 'active'}."
        if subscription_status:
            return f"Billing is linked but the latest subscription state is {subscription_status}."
        return "Hosted billing is ready. Launch checkout to start a paid workspace subscription."

    def _stripe_client(self) -> StripeClient:
        if not self.settings.stripe_secret_key:
            raise ValueError("Stripe secret key is not configured")
        return StripeClient(
            secret_key=self.settings.stripe_secret_key,
            webhook_secret=self.settings.stripe_webhook_secret,
            timeout_seconds=self.settings.outbound_timeout_seconds,
        )

    def _plan_key_for_price_id(self, price_id: str | None) -> str | None:
        if not price_id:
            return None
        for plan in self._billing_plan_catalog():
            if plan.price_id == price_id:
                return plan.key
        return None

    @staticmethod
    def _plan_label(plan_key: str | None) -> str | None:
        mapping = {
            "basic": "Starter",
            "pro": "Pro",
            "enterprise": "Enterprise",
        }
        return mapping.get(plan_key) if plan_key else None

    @staticmethod
    def _tier_for_plan(plan_key: str | None) -> str:
        mapping = {
            "basic": "starter",
            "pro": "pro",
            "enterprise": "enterprise",
        }
        return mapping.get(plan_key or "", "starter")

    @staticmethod
    def _mask_identifier(value: str | None) -> str | None:
        if not value:
            return None
        if len(value) <= 12:
            return value
        return f"{value[:6]}...{value[-4:]}"

    def _apply_stripe_event(
        self,
        repository: BotSocietyRepository,
        event: dict[str, object],
        *,
        event_id: str,
        event_type: str,
    ) -> dict[str, str | None]:
        data = event.get("data")
        event_object = data.get("object") if isinstance(data, dict) else None
        if not isinstance(event_object, dict):
            raise ValueError("Stripe webhook payload is missing its event object")

        if event_type == "checkout.session.completed":
            return self._apply_stripe_checkout_session(repository, event_object, event_id=event_id, event_type=event_type)
        if event_type in {"customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted"}:
            return self._apply_stripe_subscription_object(repository, event_object, event_id=event_id, event_type=event_type)
        if event_type in {"invoice.paid", "invoice.payment_failed"}:
            return self._apply_stripe_invoice_object(repository, event_object, event_id=event_id, event_type=event_type)
        return {
            "user_slug": self._resolve_billing_user_slug(
                repository,
                user_slug_hint=self._object_metadata(event_object).get("user_slug"),
                customer_id=self._string_or_none(event_object.get("customer")),
                subscription_id=self._string_or_none(event_object.get("subscription")),
            ),
            "provider_customer_id": self._string_or_none(event_object.get("customer")),
            "provider_subscription_id": self._string_or_none(event_object.get("subscription")) or self._string_or_none(event_object.get("id")),
        }

    def _apply_stripe_checkout_session(
        self,
        repository: BotSocietyRepository,
        session: dict[str, object],
        *,
        event_id: str,
        event_type: str,
    ) -> dict[str, str | None]:
        metadata = self._object_metadata(session)
        user_slug = self._resolve_billing_user_slug(
            repository,
            user_slug_hint=self._string_or_none(session.get("client_reference_id")) or metadata.get("user_slug"),
            customer_id=self._string_or_none(session.get("customer")),
            subscription_id=self._string_or_none(session.get("subscription")),
        )
        if not user_slug:
            raise ValueError("Stripe checkout session could not be matched to a workspace")

        user = repository.get_user(user_slug)
        if not user:
            raise ValueError(f"User {user_slug} is not available")

        now = self._now()
        customer_id = self._string_or_none(session.get("customer"))
        subscription_id = self._string_or_none(session.get("subscription"))
        plan_key = metadata.get("plan_key")
        existing = repository.get_billing_subscription(user_slug)

        if customer_id:
            customer = repository.get_billing_customer(user_slug)
            email = self._extract_customer_email(session) or user["email"]
            repository.upsert_billing_customer(
                {
                    "user_slug": user_slug,
                    "provider": "stripe",
                    "provider_customer_id": customer_id,
                    "email": email,
                    "created_at": customer["created_at"] if customer else now,
                    "updated_at": now,
                }
            )

        repository.upsert_billing_subscription(
            {
                "user_slug": user_slug,
                "provider": "stripe",
                "provider_customer_id": customer_id or (existing.get("provider_customer_id") if existing else None),
                "provider_subscription_id": subscription_id or (existing.get("provider_subscription_id") if existing else None),
                "provider_checkout_session_id": self._string_or_none(session.get("id")) or (existing.get("provider_checkout_session_id") if existing else None),
                "status": "checkout_completed",
                "plan_key": plan_key or (existing.get("plan_key") if existing else None),
                "price_id": existing.get("price_id") if existing else None,
                "current_period_end": existing.get("current_period_end") if existing else None,
                "cancel_at_period_end": bool(existing.get("cancel_at_period_end")) if existing else False,
                "last_event_id": event_id,
                "last_event_type": event_type,
                "created_at": existing.get("created_at") if existing else now,
                "updated_at": now,
            }
        )
        payment_status = self._string_or_none(session.get("payment_status")) or ""
        if payment_status in {"paid", "no_payment_required"} and plan_key:
            repository.update_user(user_slug, {"tier": self._tier_for_plan(plan_key)})

        return {
            "user_slug": user_slug,
            "provider_customer_id": customer_id,
            "provider_subscription_id": subscription_id,
        }

    def _apply_stripe_subscription_object(
        self,
        repository: BotSocietyRepository,
        subscription: dict[str, object],
        *,
        event_id: str,
        event_type: str,
    ) -> dict[str, str | None]:
        metadata = self._object_metadata(subscription)
        customer_id = self._string_or_none(subscription.get("customer"))
        subscription_id = self._string_or_none(subscription.get("id"))
        user_slug = self._resolve_billing_user_slug(
            repository,
            user_slug_hint=metadata.get("user_slug"),
            customer_id=customer_id,
            subscription_id=subscription_id,
        )
        if not user_slug:
            raise ValueError("Stripe subscription could not be matched to a workspace")

        user = repository.get_user(user_slug)
        if not user:
            raise ValueError(f"User {user_slug} is not available")

        existing = repository.get_billing_subscription(user_slug)
        price_id = self._extract_subscription_price_id(subscription)
        plan_key = metadata.get("plan_key") or self._plan_key_for_price_id(price_id) or (existing.get("plan_key") if existing else None)
        status = "canceled" if event_type == "customer.subscription.deleted" else (self._string_or_none(subscription.get("status")) or "unknown")
        now = self._now()

        if customer_id:
            customer = repository.get_billing_customer(user_slug)
            repository.upsert_billing_customer(
                {
                    "user_slug": user_slug,
                    "provider": "stripe",
                    "provider_customer_id": customer_id,
                    "email": user["email"],
                    "created_at": customer["created_at"] if customer else now,
                    "updated_at": now,
                }
            )

        repository.upsert_billing_subscription(
            {
                "user_slug": user_slug,
                "provider": "stripe",
                "provider_customer_id": customer_id or (existing.get("provider_customer_id") if existing else None),
                "provider_subscription_id": subscription_id or (existing.get("provider_subscription_id") if existing else None),
                "provider_checkout_session_id": existing.get("provider_checkout_session_id") if existing else None,
                "status": status,
                "plan_key": plan_key,
                "price_id": price_id or (existing.get("price_id") if existing else None),
                "current_period_end": self._timestamp_from_epoch(subscription.get("current_period_end")) or (existing.get("current_period_end") if existing else None),
                "cancel_at_period_end": bool(subscription.get("cancel_at_period_end")),
                "last_event_id": event_id,
                "last_event_type": event_type,
                "created_at": existing.get("created_at") if existing else now,
                "updated_at": now,
            }
        )

        if status in {"trialing", "active", "past_due", "unpaid"} and plan_key:
            repository.update_user(user_slug, {"tier": self._tier_for_plan(plan_key)})
        elif status in {"canceled", "incomplete_expired"}:
            repository.update_user(user_slug, {"tier": "starter"})

        return {
            "user_slug": user_slug,
            "provider_customer_id": customer_id,
            "provider_subscription_id": subscription_id,
        }

    def _apply_stripe_invoice_object(
        self,
        repository: BotSocietyRepository,
        invoice: dict[str, object],
        *,
        event_id: str,
        event_type: str,
    ) -> dict[str, str | None]:
        customer_id = self._string_or_none(invoice.get("customer"))
        subscription_id = self._string_or_none(invoice.get("subscription"))
        user_slug = self._resolve_billing_user_slug(
            repository,
            user_slug_hint=self._object_metadata(invoice).get("user_slug"),
            customer_id=customer_id,
            subscription_id=subscription_id,
        )
        if not user_slug:
            raise ValueError("Stripe invoice could not be matched to a workspace")

        existing = repository.get_billing_subscription(user_slug)
        if not existing and not subscription_id:
            raise ValueError("Stripe invoice could not find an existing billing subscription")

        price_id = self._extract_invoice_price_id(invoice) or (existing.get("price_id") if existing else None)
        plan_key = self._plan_key_for_price_id(price_id) or (existing.get("plan_key") if existing else None)
        status = "active" if event_type == "invoice.paid" else "past_due"
        now = self._now()
        repository.upsert_billing_subscription(
            {
                "user_slug": user_slug,
                "provider": "stripe",
                "provider_customer_id": customer_id or (existing.get("provider_customer_id") if existing else None),
                "provider_subscription_id": subscription_id or (existing.get("provider_subscription_id") if existing else None),
                "provider_checkout_session_id": existing.get("provider_checkout_session_id") if existing else None,
                "status": status,
                "plan_key": plan_key,
                "price_id": price_id,
                "current_period_end": existing.get("current_period_end") if existing else None,
                "cancel_at_period_end": bool(existing.get("cancel_at_period_end")) if existing else False,
                "last_event_id": event_id,
                "last_event_type": event_type,
                "created_at": existing.get("created_at") if existing else now,
                "updated_at": now,
            }
        )
        if event_type == "invoice.paid" and plan_key:
            repository.update_user(user_slug, {"tier": self._tier_for_plan(plan_key)})

        return {
            "user_slug": user_slug,
            "provider_customer_id": customer_id,
            "provider_subscription_id": subscription_id,
        }

    def _resolve_billing_user_slug(
        self,
        repository: BotSocietyRepository,
        *,
        user_slug_hint: str | None = None,
        customer_id: str | None = None,
        subscription_id: str | None = None,
    ) -> str | None:
        if user_slug_hint and repository.get_user(user_slug_hint):
            return user_slug_hint
        if customer_id:
            customer = repository.get_billing_customer_by_provider_customer_id(customer_id)
            if customer:
                return str(customer["user_slug"])
        if subscription_id:
            subscription = repository.get_billing_subscription_by_provider_subscription_id(subscription_id)
            if subscription:
                return str(subscription["user_slug"])
        return None

    @staticmethod
    def _object_metadata(payload: dict[str, object]) -> dict[str, str]:
        metadata = payload.get("metadata")
        if not isinstance(metadata, dict):
            return {}
        return {
            str(key): str(value)
            for key, value in metadata.items()
            if value is not None and str(value).strip()
        }

    @staticmethod
    def _string_or_none(value: object) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @staticmethod
    def _timestamp_from_epoch(value: object) -> str | None:
        if not isinstance(value, (int, float)) or value <= 0:
            return None
        return datetime.fromtimestamp(float(value), tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _extract_customer_email(payload: dict[str, object]) -> str | None:
        customer_details = payload.get("customer_details")
        if isinstance(customer_details, dict):
            email = customer_details.get("email")
            if isinstance(email, str) and email.strip():
                return email.strip().lower()
        customer_email = payload.get("customer_email")
        if isinstance(customer_email, str) and customer_email.strip():
            return customer_email.strip().lower()
        return None

    @staticmethod
    def _extract_subscription_price_id(payload: dict[str, object]) -> str | None:
        items = payload.get("items")
        if not isinstance(items, dict):
            return None
        data = items.get("data")
        if not isinstance(data, list) or not data:
            return None
        first_item = data[0]
        if not isinstance(first_item, dict):
            return None
        price = first_item.get("price")
        if not isinstance(price, dict):
            return None
        price_id = price.get("id")
        return str(price_id).strip() if price_id else None

    @staticmethod
    def _extract_invoice_price_id(payload: dict[str, object]) -> str | None:
        lines = payload.get("lines")
        if not isinstance(lines, dict):
            return None
        data = lines.get("data")
        if not isinstance(data, list) or not data:
            return None
        for line in data:
            if not isinstance(line, dict):
                continue
            price = line.get("price")
            if isinstance(price, dict) and price.get("id"):
                return str(price["id"]).strip()
        return None

    @staticmethod
    def _to_user_identity(user: dict) -> UserIdentity:
        return UserIdentity(
            slug=user["slug"],
            display_name=user["display_name"],
            email=user["email"],
            tier=user["tier"],
            is_demo_user=bool(user.get("is_demo_user")),
        )

    def _create_session_for_user(self, user_slug: str) -> tuple[AuthSessionSnapshot, str]:
        repository = BotSocietyRepository(self.database)
        user = repository.get_user(user_slug)
        if not user:
            raise ValueError("Unable to start a session for that account")
        now = self._now()
        session_token = self.auth.new_session_token()
        repository.create_session(
            {
                "token_hash": session_token.token_hash,
                "user_slug": user_slug,
                "created_at": now,
                "expires_at": self._session_expires_at(),
                "last_seen_at": now,
            }
        )
        return AuthSessionSnapshot(authenticated=True, user=self._to_user_identity(user)), session_token.raw_token

    def _generate_user_slug(self, repository: BotSocietyRepository, display_name: str, email: str) -> str:
        base = display_name.strip().lower() or email.split("@", 1)[0].lower()
        base = SLUG_RE.sub("-", base).strip("-") or email.split("@", 1)[0].lower()
        candidate = base[:80]
        suffix = 1
        while repository.get_user(candidate):
            suffix += 1
            candidate = f"{base[:72]}-{suffix}"
        return candidate

    def _session_expires_at(self) -> str:
        return to_timestamp(datetime.now(timezone.utc) + timedelta(hours=self.settings.session_ttl_hours))

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _encode_audit_state(state: dict[str, object] | None) -> str | None:
        if state is None:
            return None
        return json.dumps(state, separators=(",", ":"), sort_keys=True, default=str)

    @staticmethod
    def _decode_audit_state(raw_state: str | None) -> dict[str, object] | None:
        if not raw_state:
            return None
        try:
            payload = json.loads(raw_state)
        except json.JSONDecodeError:
            return {"raw": raw_state}
        return payload if isinstance(payload, dict) else {"value": payload}

    @staticmethod
    def _encode_json_payload(payload: object | None) -> str | None:
        if payload is None:
            return None
        return json.dumps(payload, separators=(",", ":"), sort_keys=True, default=str)

    @staticmethod
    def _decode_json_payload(raw_payload: str | None) -> object | None:
        if not raw_payload:
            return None
        try:
            return json.loads(raw_payload)
        except json.JSONDecodeError:
            return {"raw": raw_payload}

    def _strategy_view_from_row(self, row: dict) -> StrategyView:
        config_payload = self._decode_json_payload(row.get("config_json"))
        if not isinstance(config_payload, dict):
            config_payload = {"asset": "BTC"}
        return StrategyView(
            id=int(row["id"]),
            user_slug=str(row["user_slug"]),
            name=str(row["name"]),
            description=row.get("description"),
            config=SimulationRequest(**config_payload),
            is_active=bool(row["is_active"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    def _backtest_run_view_from_row(self, row: dict) -> BacktestRunView:
        summary_payload = self._decode_json_payload(row.get("summary_json"))
        result_payload = self._decode_json_payload(row.get("result_json"))
        return BacktestRunView(
            id=int(row["id"]),
            strategy_id=int(row["strategy_id"]),
            user_slug=str(row["user_slug"]),
            asset=str(row["asset"]),
            strategy_key=str(row["strategy_key"]),
            lookback_years=int(row["lookback_years"]),
            status=str(row["status"]),
            started_at=str(row["started_at"]),
            completed_at=row.get("completed_at"),
            summary=summary_payload if isinstance(summary_payload, dict) else {},
            result=SimulationRunResult(**result_payload) if isinstance(result_payload, dict) else None,
            error_message=row.get("error_message"),
        )

    def _trading_order_view_from_row(self, row: dict) -> TradingOrderView:
        metadata_payload = self._decode_json_payload(row.get("metadata_json"))
        return TradingOrderView(
            id=int(row["id"]),
            user_slug=str(row["user_slug"]),
            prediction_id=int(row["prediction_id"]) if row.get("prediction_id") is not None else None,
            venue=str(row["venue"]),
            asset=str(row["asset"]),
            side=row["side"],
            order_type=row["order_type"],
            is_paper=bool(row["is_paper"]),
            quantity=round(float(row["quantity"]), 8),
            notional_usd=round(float(row["notional_usd"]), 2),
            price=float(row["price"]) if row.get("price") is not None else None,
            status=row["status"],
            filled_quantity=round(float(row["filled_quantity"]), 8),
            avg_fill_price=float(row["avg_fill_price"]) if row.get("avg_fill_price") is not None else None,
            fee=round(float(row.get("fee") or 0.0), 2),
            fee_currency=str(row.get("fee_currency") or "USD"),
            exchange_order_id=row.get("exchange_order_id"),
            rejection_reason=row.get("rejection_reason"),
            submitted_at=str(row["submitted_at"]),
            filled_at=row.get("filled_at"),
            cancelled_at=row.get("cancelled_at"),
            metadata=metadata_payload if isinstance(metadata_payload, dict) else None,
        )
