from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
import re
from datetime import datetime, timedelta, timezone
from statistics import mean, median, pstdev

from sqlalchemy.exc import IntegrityError

from .auth import AuthManager
from .config import Settings
from .database import Database
from .models import (
    AlertDelivery,
    AlertInbox,
    AlertRule,
    AlertRuleCreate,
    AssetHistoryEnvelope,
    AssetHistoryPoint,
    AssetSnapshot,
    AuthLoginRequest,
    AuthRegisterRequest,
    AuthSessionSnapshot,
    BotDetail,
    BotSummary,
    CycleResult,
    DashboardSnapshot,
    FollowedBot,
    LandingSnapshot,
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
    PredictionView,
    ProviderComponentStatus,
    ProviderStatus,
    SignalView,
    SignalMixItem,
    SimulationConfig,
    SimulationLeaderboardEntry,
    SimulationRequest,
    SimulationRunResult,
    SimulationSeriesPoint,
    SimulationStrategyPreset,
    SimulationStrategyResult,
    SimulationTradeView,
    Summary,
    SystemPulseSnapshot,
    UserIdentity,
    UserProfile,
    VenuePulseItem,
    WatchlistItem,
)
from .notifications import NotificationDispatcher
from .orchestration import PredictionOrchestrator
from .providers import (
    CoinGeckoMarketProvider,
    DemoMarketProvider,
    DemoMacroProvider,
    DemoSignalProvider,
    FredMacroProvider,
    HyperliquidMarketProvider,
    KalshiSignalProvider,
    PolymarketSignalProvider,
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
    ]

    def __init__(self, database: Database, settings: Settings) -> None:
        self.database = database
        self.settings = settings
        self.auth = AuthManager()
        self.dispatcher = NotificationDispatcher(settings)
        self.demo_market_provider = DemoMarketProvider()
        self.demo_signal_provider = DemoSignalProvider()
        self.demo_macro_provider = DemoMacroProvider(series_ids=self.settings.fred_series_ids)
        self.history_provider = CoinGeckoMarketProvider(
            plan=self.settings.coingecko_plan,
            api_key=self.settings.coingecko_api_key,
            tracked_coin_ids=self.settings.tracked_coin_ids,
        )
        self.market_provider = self._build_market_provider()
        self.signal_provider = self._build_signal_provider()
        self.macro_provider = self._build_macro_provider()
        self.venue_signal_providers = self._build_venue_signal_providers()
        self.orchestrator = PredictionOrchestrator()
        self.market_provider_fallback = False
        self.signal_provider_fallback = False
        self.macro_provider_fallback = False
        self.market_provider_source = self.market_provider.source_name
        self.signal_provider_source = self._compose_signal_provider_source()
        self.macro_provider_source = self.macro_provider.source_name

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
        return [self._to_prediction_model(row) for row in repository.list_predictions(limit=limit, status=status)]

    def get_leaderboard(self, user_slug: str | None = None) -> list[BotSummary]:
        repository = BotSocietyRepository(self.database)
        return self._build_bot_summaries(repository, user_slug)

    def get_bot_detail(self, slug: str, user_slug: str | None = None) -> BotDetail | None:
        repository = BotSocietyRepository(self.database)
        summaries = self._build_bot_summaries(repository, user_slug)
        summary = next((bot for bot in summaries if bot.slug == slug), None)
        if not summary:
            return None
        recent_predictions = [self._to_prediction_model(row) for row in repository.list_predictions(bot_slug=slug, limit=8)]
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
            default_strategy_id="trend_follow",
            default_lookback_years=5,
            default_starting_capital=10000,
            default_fee_bps=10,
            live_history_capable=live_history_capable,
            note=note,
        )

    def run_simulation(self, payload: SimulationRequest) -> SimulationRunResult:
        if payload.asset not in BotSocietyRepository(self.database).list_assets():
            raise ValueError(f"Unknown asset: {payload.asset}")

        history_points, data_source, history_note = self._load_simulation_history(payload.asset, payload.lookback_years)
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
        market_configured, market_live_capable = self._provider_configuration("market")
        signal_configured, signal_live_capable = self._provider_configuration("signal")
        macro_configured, macro_live_capable = self._provider_configuration("macro")
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
            tracked_coin_ids=list(self.settings.tracked_coin_ids),
            fred_series_ids=list(self.settings.fred_series_ids),
            rss_feed_urls=list(self.settings.rss_feed_urls),
            reddit_subreddits=list(self.settings.reddit_subreddits),
            venue_signal_providers=venue_statuses,
            market_fallback_active=self.market_provider_fallback,
            signal_fallback_active=self.signal_provider_fallback,
            macro_fallback_active=self.macro_provider_fallback,
        )

    def get_dashboard_snapshot(self, user_slug: str) -> DashboardSnapshot:
        repository = BotSocietyRepository(self.database)
        system_pulse = self.get_system_pulse(repository)
        return DashboardSnapshot(
            summary=self.get_summary(user_slug),
            assets=self.get_assets(),
            leaderboard=self._build_bot_summaries(repository, user_slug),
            recent_predictions=[self._to_prediction_model(row) for row in repository.list_predictions(limit=10)],
            recent_signals=[self._to_signal_model(row) for row in repository.list_recent_signals(limit=8)],
            system_pulse=system_pulse,
            macro_snapshot=self.get_macro_snapshot(repository),
            paper_trading=self.get_paper_trading_snapshot(user_slug),
            latest_operation=self._latest_operation(repository),
            auth_session=AuthSessionSnapshot(authenticated=user_slug != self.settings.default_user_slug, user=self._to_user_identity(repository.get_user(user_slug)) if user_slug != self.settings.default_user_slug else None),
            user_profile=self.get_user_profile(user_slug),
            notification_health=self.get_notification_health(user_slug),
            provider_status=self.get_provider_status(),
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
        live_provider_count = int(provider_status.market_provider_live_capable) + int(provider_status.signal_provider_live_capable) + int(provider_status.macro_provider_live_capable)
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
            recent_predictions=[self._to_prediction_model(row) for row in repository.list_predictions(limit=10)],
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

    def _load_simulation_history(self, asset: str, lookback_years: int) -> tuple[list[SimulationSeriesPoint], str, str | None]:
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

        if self.settings.simulation_live_history:
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
            desired_position = self._simulation_target_position(strategy_id, prices, index, position, payload)
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
        return SimulationStrategyResult(
            strategy_id=preset.strategy_id,
            label=preset.label,
            summary=preset.description,
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
        return 0.0

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
    def _to_prediction_model(row: dict) -> PredictionView:
        payload = {
            **row,
            "directional_success": bool(row["directional_success"]) if row["directional_success"] is not None else None,
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
