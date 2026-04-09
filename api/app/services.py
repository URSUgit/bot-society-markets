
from __future__ import annotations

import json
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
    NotificationChannel,
    NotificationChannelHealth,
    NotificationChannelCreate,
    NotificationHealthSnapshot,
    NotificationRetryResult,
    OperationSnapshot,
    PredictionView,
    ProviderComponentStatus,
    ProviderStatus,
    SignalView,
    Summary,
    UserIdentity,
    UserProfile,
    WatchlistItem,
)
from .notifications import NotificationDispatcher
from .orchestration import PredictionOrchestrator
from .providers import (
    CoinGeckoMarketProvider,
    DemoMarketProvider,
    DemoSignalProvider,
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
    def __init__(self, database: Database, settings: Settings) -> None:
        self.database = database
        self.settings = settings
        self.auth = AuthManager()
        self.dispatcher = NotificationDispatcher(settings)
        self.demo_market_provider = DemoMarketProvider()
        self.demo_signal_provider = DemoSignalProvider()
        self.market_provider = self._build_market_provider()
        self.signal_provider = self._build_signal_provider()
        self.venue_signal_providers = self._build_venue_signal_providers()
        self.orchestrator = PredictionOrchestrator()
        self.market_provider_fallback = False
        self.signal_provider_fallback = False
        self.market_provider_source = self.market_provider.source_name
        self.signal_provider_source = self._compose_signal_provider_source()

    def bootstrap(self) -> None:
        self.database.initialize()
        repository = BotSocietyRepository(self.database)
        seeded = seed_demo_dataset(repository) if self.settings.seed_demo_data else False
        ensure_demo_user_state(repository)
        refreshed_signals = repository.refresh_signal_quality_scores()
        repository.delete_expired_sessions(self._now())
        scorer = ScoringEngine(repository, self.settings.scoring_version)
        scored = scorer.score_available_predictions()
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
                        f"Initialized {alert_deliveries} alert deliveries and refreshed {refreshed_signals} signal quality records."
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
        market_configured, market_live_capable = self._provider_configuration("market")
        signal_configured, signal_live_capable = self._provider_configuration("signal")
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
            tracked_coin_ids=list(self.settings.tracked_coin_ids),
            rss_feed_urls=list(self.settings.rss_feed_urls),
            reddit_subreddits=list(self.settings.reddit_subreddits),
            venue_signal_providers=venue_statuses,
            market_fallback_active=self.market_provider_fallback,
            signal_fallback_active=self.signal_provider_fallback,
        )

    def get_dashboard_snapshot(self, user_slug: str) -> DashboardSnapshot:
        repository = BotSocietyRepository(self.database)
        return DashboardSnapshot(
            summary=self.get_summary(user_slug),
            assets=self.get_assets(),
            leaderboard=self._build_bot_summaries(repository, user_slug),
            recent_predictions=[self._to_prediction_model(row) for row in repository.list_predictions(limit=10)],
            recent_signals=[self._to_signal_model(row) for row in repository.list_recent_signals(limit=8)],
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
            provider_status=self.get_provider_status(),
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
                        f"Ingested {ingested_signals} signals, generated {created_predictions} fresh predictions, scored {scored_predictions} eligible predictions, and delivered {delivered_alerts} alerts.",
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
                0.28 * hit_rate
                + 0.23 * return_component
                + 0.18 * calibration
                + 0.13 * consistency
                + 0.08 * risk_discipline
                + 0.10 * provenance_score
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
        linked_signals = [signal_lookup[signal_id] for signal_id in self._extract_source_signal_ids(prediction) if signal_id in signal_lookup]
        if not linked_signals:
            return None
        return mean(float(signal.get("source_quality_score") or 0.0) for signal in linked_signals)

    def _provider_configuration(self, provider_type: str) -> tuple[bool, bool]:
        if provider_type == "market":
            if self.settings.market_provider_mode == "demo":
                return True, False
            if self.settings.market_provider_mode == "hyperliquid":
                return True, True
            configured = self.settings.coingecko_plan != "pro" or bool(self.settings.coingecko_api_key)
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
