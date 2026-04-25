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

    def bootstrap(self) -> None:
        self.database.initialize()
        repository = BotSocietyRepository(self.database)
        seeded = seed_demo_dataset(repository) if self.settings.seed_demo_data else False
        ensure_demo_user_state(repository)
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
                        f"hydrated {macro_refreshed} macro observations, and seeded {demo_paper_positions} demo paper positions."
                    ),
                }
            )

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

    def get_summary(self, user_slug: str | None = None) -> Summary:
        repository = BotSocietyRepository(self.database)
        bots = self._build_bot_summaries(repository, user_slug)
        predictions = repository.list_predictions(limit=500)
        assets = repository.list_assets()
        signals = repository.list_recent_signals(limit=100)
        latest_run = repository.get_latest_pipeline_run()
        latest_signal_time = parse_timestamp(signals[0]["observed_at"]) if signals else None
        signals_last_24h = (
            repository.count_signals_since(to_timestamp(latest_signal_time.replace(hour=0, minute=0, second=0)))
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
        repository = BotSocietyRepository(self.database)
        return [self._to_asset_model(row) for row in repository.list_latest_market_snapshots()]

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
        active_repository = repository or BotSocietyRepository(self.database)
        latest_rows = active_repository.list_latest_macro_snapshots()
        series = []
        for row in latest_rows:
            history_rows = active_repository.list_macro_history(str(row["series_id"]))
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
        return MacroSnapshot(
            generated_at=self._now(),
            posture=posture,
            summary=summary,
            series=series,
        )

    def get_signals(self, limit: int = 12) -> list[SignalView]:
        repository = BotSocietyRepository(self.database)
        return [self._to_signal_model(row) for row in repository.list_recent_signals(limit=limit)]

    def get_predictions(self, limit: int = 20, status: str | None = None) -> list[PredictionView]:
        repository = BotSocietyRepository(self.database)
        return self._build_prediction_views(repository, repository.list_predictions(limit=limit, status=status))

    def get_leaderboard(self, user_slug: str | None = None) -> list[BotSummary]:
        repository = BotSocietyRepository(self.database)
        return self._build_bot_summaries(repository, user_slug)

    def get_bot_detail(self, slug: str, user_slug: str | None = None) -> BotDetail | None:
        repository = BotSocietyRepository(self.database)
        summaries = self._build_bot_summaries(repository, user_slug)
        summary = next((bot for bot in summaries if bot.slug == slug), None)
        if not summary:
            return None
        recent_predictions = self._build_prediction_views(repository, repository.list_predictions(bot_slug=slug, limit=8))
        return BotDetail(**summary.model_dump(), recent_predictions=recent_predictions)

    def get_paper_trading_snapshot(self, user_slug: str) -> PaperTradingSnapshot:
        repository = BotSocietyRepository(self.database)
        closed_positions = self._sync_paper_positions(repository, user_slug)
        positions = repository.list_paper_positions(user_slug)
        latest_assets = {row["asset"]: row for row in repository.list_latest_market_snapshots()}
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
                id="papermarket",
                name="PaperMarket",
                category="Manual Polymarket paper terminal",
                priority=6,
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
                "Promote any adapter to live trading only after kill switches, position limits, and audit logs exist.",
            ],
            safety_rules=[
                "Paper mode only until an explicit human approval gate is implemented.",
                "Never store seed phrases. Use API keys or testnet-only private keys in .env.local.",
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
    ) -> EdgeSnapshot:
        if not force_refresh and self._cache_is_fresh(self.edge_snapshot_cache):
            return self.edge_snapshot_cache[1]

        active_repository = repository or BotSocietyRepository(self.database)
        tracked_assets = self._current_tracked_assets(active_repository)
        latest_assets = {row["asset"]: row for row in active_repository.list_latest_market_snapshots()}
        recent_signals = active_repository.list_recent_signals(limit=120)
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

    def mark_alert_read(self, user_slug: str, alert_id: int) -> AlertInbox:
        repository = BotSocietyRepository(self.database)
        repository.mark_alert_delivery_read(user_slug, alert_id, self._now())
        return self.get_alert_inbox(user_slug)

    def mark_all_alerts_read(self, user_slug: str) -> AlertInbox:
        repository = BotSocietyRepository(self.database)
        repository.mark_all_alert_deliveries_read(user_slug, self._now())
        return self.get_alert_inbox(user_slug)

    def get_user_profile(self, user_slug: str) -> UserProfile:
        repository = BotSocietyRepository(self.database)
        user = repository.get_user(user_slug)
        if not user:
            raise ValueError(f"User {user_slug} is not available")

        leaderboard_map = {bot.slug: bot for bot in self._build_bot_summaries(repository, user_slug)}
        follows = [
            FollowedBot(
                bot_slug=row["bot_slug"],
                name=row["name"],
                score=leaderboard_map[row["bot_slug"]].score if row["bot_slug"] in leaderboard_map else 0.0,
                created_at=row["created_at"],
            )
            for row in repository.list_user_follows(user_slug)
        ]
        watchlist = [WatchlistItem(**row) for row in repository.list_watchlist_items(user_slug)]
        alert_rules = [
            AlertRule(**{**row, "is_active": bool(row["is_active"])})
            for row in repository.list_alert_rules(user_slug)
        ]
        notification_channels = [
            NotificationChannel(**{**row, "is_active": bool(row["is_active"])})
            for row in repository.list_notification_channels(user_slug)
        ]
        alert_inbox = self.get_alert_inbox(user_slug)
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
        deliveries = repository.list_alert_deliveries(user_slug, limit=None)
        now = datetime.now(timezone.utc)
        since = now - timedelta(hours=24)

        delivered_last_24h = 0
        retry_queue_depth = 0
        exhausted_deliveries = 0
        last_delivery_at: str | None = None
        channel_health_map: dict[int, dict[str, object]] = {}

        for channel in channels:
            channel_health_map[int(channel["id"])] = {
                "channel_id": int(channel["id"]),
                "channel_type": channel["channel_type"],
                "target": channel["target"],
                "is_active": bool(channel["is_active"]),
                "delivered_count": 0,
                "retry_scheduled_count": 0,
                "exhausted_count": 0,
                "last_delivered_at": channel.get("last_delivered_at"),
                "last_error": channel.get("last_error"),
            }

        for delivery in deliveries:
            status = str(delivery["delivery_status"])
            channel_id = delivery.get("notification_channel_id")
            created_at = parse_timestamp(delivery["created_at"])
            if channel_id is not None and status == "delivered" and created_at >= since:
                delivered_last_24h += 1
            if channel_id is not None and status == "retry_scheduled":
                retry_queue_depth += 1
            if channel_id is not None and status == "exhausted":
                exhausted_deliveries += 1

            last_attempt_at = delivery.get("last_attempt_at") or delivery["created_at"]
            if channel_id is not None and status == "delivered" and (last_delivery_at is None or last_attempt_at > last_delivery_at):
                last_delivery_at = last_attempt_at

            if channel_id is None or channel_id not in channel_health_map:
                continue
            channel_health = channel_health_map[int(channel_id)]
            if status == "delivered":
                channel_health["delivered_count"] = int(channel_health["delivered_count"]) + 1
            elif status == "retry_scheduled":
                channel_health["retry_scheduled_count"] = int(channel_health["retry_scheduled_count"]) + 1
            elif status == "exhausted":
                channel_health["exhausted_count"] = int(channel_health["exhausted_count"]) + 1
                if delivery.get("error_detail"):
                    channel_health["last_error"] = delivery["error_detail"]

        channel_health = [
            NotificationChannelHealth(**payload)
            for payload in sorted(channel_health_map.values(), key=lambda item: str(item["target"]).lower())
        ]
        return NotificationHealthSnapshot(
            active_channels=sum(1 for channel in channels if bool(channel["is_active"])),
            delivered_last_24h=delivered_last_24h,
            retry_queue_depth=retry_queue_depth,
            exhausted_deliveries=exhausted_deliveries,
            last_delivery_at=last_delivery_at,
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
        return self.get_user_profile(user_slug)

    def unfollow_bot(self, user_slug: str, bot_slug: str) -> UserProfile:
        repository = BotSocietyRepository(self.database)
        repository.delete_follow(user_slug, bot_slug)
        return self.get_user_profile(user_slug)

    def add_watchlist_asset(self, user_slug: str, asset: str) -> UserProfile:
        repository = BotSocietyRepository(self.database)
        normalized_asset = asset.upper()
        if normalized_asset not in repository.list_assets():
            raise ValueError(f"Unknown asset: {normalized_asset}")
        repository.create_watchlist_item(user_slug, normalized_asset, self._now())
        return self.get_user_profile(user_slug)

    def remove_watchlist_asset(self, user_slug: str, asset: str) -> UserProfile:
        repository = BotSocietyRepository(self.database)
        repository.delete_watchlist_item(user_slug, asset.upper())
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
        return self.get_user_profile(user_slug)

    def delete_alert_rule(self, user_slug: str, rule_id: int) -> UserProfile:
        repository = BotSocietyRepository(self.database)
        repository.delete_alert_rule(user_slug, rule_id)
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
        return self.get_user_profile(user_slug)

    def delete_notification_channel(self, user_slug: str, channel_id: int) -> UserProfile:
        repository = BotSocietyRepository(self.database)
        repository.delete_notification_channel(user_slug, channel_id)
        return self.get_user_profile(user_slug)

    def get_provider_status(self) -> ProviderStatus:
        market_readiness = self.market_provider.readiness()
        signal_ready, signal_warning, venue_statuses = self._signal_provider_health()
        macro_readiness = self.macro_provider.readiness()
        wallet_readiness = self.wallet_provider.readiness()
        market_configured, market_live_capable = self._provider_configuration("market")
        signal_configured, signal_live_capable = self._provider_configuration("signal")
        macro_configured, macro_live_capable = self._provider_configuration("macro")
        wallet_configured, wallet_live_capable = self._provider_configuration("wallet")
        return ProviderStatus(
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
        )

    def get_connector_control(self) -> ConnectorControlSnapshot:
        provider_status = self.get_provider_status()
        paper_venues = self.get_paper_venues()
        venue_lookup = {venue.id: venue for venue in paper_venues.venues}

        signal_source = provider_status.signal_provider_source
        if provider_status.venue_signal_providers:
            signal_source = f"{signal_source} + venue adapters"

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
                target_surface="Spot market tracking and historical archive hydration",
                env_keys=["BSM_COINGECKO_API_KEY"],
                next_actions=[
                    "Move market mode to coingecko on production deployments.",
                    "Attach a live API key before increasing tracked assets.",
                ],
            ),
            self._connector_item(
                connector_id="hyperliquid-market-feed",
                label="Hyperliquid Market Feed",
                category="Derivatives",
                mode="hyperliquid" if self.settings.market_provider_mode == "hyperliquid" else "planned",
                source="Hyperliquid perpetual futures surfaces",
                configured=bool(self.settings.hyperliquid_dex),
                live_capable=True,
                ready=self.settings.market_provider_mode == "hyperliquid" and bool(self.settings.hyperliquid_dex),
                fallback_active=self.settings.market_provider_mode != "hyperliquid",
                target_surface="Perpetuals monitoring, momentum context, and future execution adapters",
                env_keys=["BSM_HYPERLIQUID_DEX"],
                next_actions=[
                    "Set BSM_MARKET_PROVIDER=hyperliquid only after production data storage is durable.",
                    "Pair the live feed with testnet credentials before any execution-adjacent work.",
                ],
                app_url=self.settings.hyperliquid_testnet_app_url,
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
                target_surface="Tracked public trader personas and conviction ranking",
                env_keys=["BSM_WALLET_PROVIDER", "BSM_TRACKED_WALLETS"],
                next_actions=[
                    "Curate a first production wallet list instead of relying on generic demo traffic.",
                    "Keep provenance weighting visible as smart-money surfaces expand.",
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

    def get_infrastructure_readiness(self) -> InfrastructureReadinessSnapshot:
        provider_status = self.get_provider_status()
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

    def get_production_cutover(self) -> ProductionCutoverSnapshot:
        provider_status = self.get_provider_status()
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

        return ConnectorStatusItem(
            id=connector_id,
            label=label,
            category=category,
            state=state,
            mode=mode,
            source=source,
            configured=configured,
            live_capable=live_capable,
            summary=summary,
            target_surface=target_surface,
            env_keys=env_keys,
            next_actions=next_actions,
            app_url=app_url,
        )

    @staticmethod
    def _readiness_level_from_counts(completed: int, total: int, *, live: bool = False) -> str:
        if live:
            return "live"
        if total > 0 and completed >= total:
            return "ready"
        if completed > 0:
            return "building"
        return "selected"

    def get_launch_readiness(self) -> LaunchReadinessSnapshot:
        provider_status = self.get_provider_status()
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
                ),
            ),
            headline="Market intelligence connectors are already online; revenue and operations connectors come next.",
            summary=(
                f"{live_connector_count} live-capable data connectors are already exposed across market, signal, macro, "
                "wallet, and venue layers. Next connectors should add billing webhooks, onramp callbacks, CRM alerts, and exports."
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
        repository = BotSocietyRepository(self.database)
        macro_snapshot = self.get_macro_snapshot(repository)
        wallet_snapshot = self.get_wallet_intelligence()
        edge_snapshot = self.get_edge_snapshot(repository, wallet_snapshot=wallet_snapshot, macro_snapshot=macro_snapshot)
        system_pulse = self.get_system_pulse(repository)
        recent_prediction_rows = repository.list_predictions(limit=10)
        return DashboardSnapshot(
            summary=self.get_summary(user_slug),
            assets=self.get_assets(),
            leaderboard=self._build_bot_summaries(repository, user_slug),
            recent_predictions=self._build_prediction_views(repository, recent_prediction_rows),
            recent_signals=[self._to_signal_model(row) for row in repository.list_recent_signals(limit=8)],
            system_pulse=system_pulse,
            macro_snapshot=macro_snapshot,
            wallet_intelligence=wallet_snapshot,
            edge_snapshot=edge_snapshot,
            paper_trading=self.get_paper_trading_snapshot(user_slug),
            paper_venues=self.get_paper_venues(),
            latest_operation=self._latest_operation(repository),
            auth_session=AuthSessionSnapshot(authenticated=user_slug != self.settings.default_user_slug, user=self._to_user_identity(repository.get_user(user_slug)) if user_slug != self.settings.default_user_slug else None),
            user_profile=self.get_user_profile(user_slug),
            notification_health=self.get_notification_health(user_slug),
            provider_status=self.get_provider_status(),
            launch_readiness=self.get_launch_readiness(),
            connector_control=self.get_connector_control(),
            infrastructure_readiness=self.get_infrastructure_readiness(),
            production_cutover=self.get_production_cutover(),
            business_model=self.get_business_model_strategy(),
        )

    def get_landing_snapshot(self, user_slug: str | None = None) -> LandingSnapshot:
        repository = BotSocietyRepository(self.database)
        return LandingSnapshot(
            summary=self.get_summary(user_slug),
            assets=self.get_assets(),
            leaderboard=self._build_bot_summaries(repository, user_slug)[:4],
            recent_signals=[self._to_signal_model(row) for row in repository.list_recent_signals(limit=4)],
            system_pulse=self.get_system_pulse(repository),
            macro_snapshot=self.get_macro_snapshot(repository),
            provider_status=self.get_provider_status(),
            business_model=self.get_business_model_strategy(),
        )

    def get_system_pulse(self, repository: BotSocietyRepository | None = None) -> SystemPulseSnapshot:
        active_repository = repository or BotSocietyRepository(self.database)
        recent_signals = active_repository.list_recent_signals(limit=96)
        latest_assets = active_repository.list_latest_market_snapshots()
        provider_status = self.get_provider_status()
        notification_health = self.get_notification_health(self.settings.default_user_slug)
        generated_at = self._now()
        average_quality = mean(float(signal.get("source_quality_score") or 0.0) for signal in recent_signals) if recent_signals else 0.0
        average_freshness = mean(float(signal.get("freshness_score") or 0.0) for signal in recent_signals) if recent_signals else 0.0
        live_provider_count = (
            int(provider_status.market_provider_live_capable)
            + int(provider_status.signal_provider_live_capable)
            + int(provider_status.macro_provider_live_capable)
            + int(provider_status.wallet_provider_live_capable)
        )
        live_provider_count += sum(1 for venue in provider_status.venue_signal_providers if venue.live_capable)
        pending_predictions = len(active_repository.list_predictions(status="pending", limit=500))
        return SystemPulseSnapshot(
            generated_at=generated_at,
            live_provider_count=live_provider_count,
            total_recent_signals=len(recent_signals),
            average_signal_quality=round(average_quality, 3),
            average_signal_freshness=round(average_freshness, 3),
            pending_predictions=pending_predictions,
            retry_queue_depth=notification_health.retry_queue_depth,
            signal_mix=self._build_signal_mix(recent_signals),
            venue_pulse=self._build_venue_pulse(recent_signals, latest_assets, provider_status),
        )

    def get_latest_operation(self) -> OperationSnapshot | None:
        repository = BotSocietyRepository(self.database)
        return self._latest_operation(repository)

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
            self.market_provider_source = self.market_provider.source_name
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
                        f"Ingested {ingested_signals} signals, generated {created_predictions} fresh predictions, scored {scored_predictions} eligible predictions, delivered {delivered_alerts} alerts, and refreshed {macro_observations} macro observations.",
                    ]
                ).strip(),
            }
        )
        operation = repository.get_latest_pipeline_run()
        return CycleResult(
            operation=self._to_operation_model(operation),
            leaderboard=self._build_bot_summaries(repository, self.settings.default_user_slug),
            recent_predictions=self._build_prediction_views(repository, repository.list_predictions(limit=10)),
            provider_status=self.get_provider_status(),
            alert_inbox=self.get_alert_inbox(self.settings.default_user_slug),
            notification_health=self.get_notification_health(self.settings.default_user_slug),
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

    def _build_bot_summaries(self, repository: BotSocietyRepository, user_slug: str | None = None) -> list[BotSummary]:
        bots = repository.list_bots()
        predictions = repository.list_predictions(limit=500)
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
