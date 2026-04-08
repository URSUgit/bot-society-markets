from __future__ import annotations

from datetime import datetime, timezone
from statistics import mean, median, pstdev

from .config import Settings
from .database import Database
from .models import (
    AlertDelivery,
    AlertInbox,
    AlertRule,
    AlertRuleCreate,
    AssetSnapshot,
    BotDetail,
    BotSummary,
    CycleResult,
    DashboardSnapshot,
    FollowedBot,
    LandingSnapshot,
    OperationSnapshot,
    PredictionView,
    ProviderStatus,
    SignalView,
    Summary,
    UserProfile,
    WatchlistItem,
)
from .orchestration import PredictionOrchestrator
from .providers import CoinGeckoMarketProvider, DemoMarketProvider, DemoSignalProvider, RSSNewsSignalProvider
from .repository import BotSocietyRepository
from .scoring import ScoringEngine, clamp
from .seed import ensure_demo_user_state, seed_demo_dataset
from .utils import parse_timestamp, to_timestamp


class BotSocietyService:
    def __init__(self, database: Database, settings: Settings) -> None:
        self.database = database
        self.settings = settings
        self.demo_market_provider = DemoMarketProvider()
        self.demo_signal_provider = DemoSignalProvider()
        self.market_provider = self._build_market_provider()
        self.signal_provider = self._build_signal_provider()
        self.orchestrator = PredictionOrchestrator()
        self.market_provider_fallback = False
        self.signal_provider_fallback = False
        self.market_provider_source = self.market_provider.source_name
        self.signal_provider_source = self.signal_provider.source_name

    def bootstrap(self) -> None:
        self.database.initialize()
        repository = BotSocietyRepository(self.database)
        seeded = seed_demo_dataset(repository) if self.settings.seed_demo_data else False
        ensure_demo_user_state(repository)
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
                        f"Initialized {alert_deliveries} in-app alert deliveries."
                    ),
                }
            )

    def get_summary(self) -> Summary:
        repository = BotSocietyRepository(self.database)
        bots = self._build_bot_summaries(repository, self.settings.default_user_slug)
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

    def get_leaderboard(self) -> list[BotSummary]:
        repository = BotSocietyRepository(self.database)
        return self._build_bot_summaries(repository, self.settings.default_user_slug)

    def get_bot_detail(self, slug: str) -> BotDetail | None:
        repository = BotSocietyRepository(self.database)
        summaries = self._build_bot_summaries(repository, self.settings.default_user_slug)
        summary = next((bot for bot in summaries if bot.slug == slug), None)
        if not summary:
            return None
        recent_predictions = [self._to_prediction_model(row) for row in repository.list_predictions(bot_slug=slug, limit=8)]
        return BotDetail(**summary.model_dump(), recent_predictions=recent_predictions)

    def get_alert_inbox(self, unread_only: bool = False) -> AlertInbox:
        repository = BotSocietyRepository(self.database)
        alerts = [
            self._to_alert_model(row)
            for row in repository.list_alert_deliveries(
                self.settings.default_user_slug,
                limit=self.settings.alert_inbox_limit,
                unread_only=unread_only,
            )
        ]
        return AlertInbox(
            unread_count=repository.count_unread_alert_deliveries(self.settings.default_user_slug),
            alerts=alerts,
        )

    def mark_alert_read(self, alert_id: int) -> AlertInbox:
        repository = BotSocietyRepository(self.database)
        repository.mark_alert_delivery_read(self.settings.default_user_slug, alert_id, self._now())
        return self.get_alert_inbox()

    def mark_all_alerts_read(self) -> AlertInbox:
        repository = BotSocietyRepository(self.database)
        repository.mark_all_alert_deliveries_read(self.settings.default_user_slug, self._now())
        return self.get_alert_inbox()

    def get_user_profile(self) -> UserProfile:
        repository = BotSocietyRepository(self.database)
        user = repository.get_user(self.settings.default_user_slug)
        if not user:
            raise ValueError(f"User {self.settings.default_user_slug} is not available")

        leaderboard_map = {bot.slug: bot for bot in self._build_bot_summaries(repository, self.settings.default_user_slug)}
        follows = [
            FollowedBot(
                bot_slug=row["bot_slug"],
                name=row["name"],
                score=leaderboard_map[row["bot_slug"]].score if row["bot_slug"] in leaderboard_map else 0.0,
                created_at=row["created_at"],
            )
            for row in repository.list_user_follows(self.settings.default_user_slug)
        ]
        watchlist = [WatchlistItem(**row) for row in repository.list_watchlist_items(self.settings.default_user_slug)]
        alert_rules = [
            AlertRule(**{**row, "is_active": bool(row["is_active"])})
            for row in repository.list_alert_rules(self.settings.default_user_slug)
        ]
        alert_inbox = self.get_alert_inbox()
        return UserProfile(
            slug=user["slug"],
            display_name=user["display_name"],
            tier=user["tier"],
            follows=follows,
            watchlist=watchlist,
            alert_rules=alert_rules,
            recent_alerts=alert_inbox.alerts,
            unread_alert_count=alert_inbox.unread_count,
        )

    def follow_bot(self, bot_slug: str) -> UserProfile:
        repository = BotSocietyRepository(self.database)
        if not repository.get_bot(bot_slug):
            raise ValueError(f"Unknown bot slug: {bot_slug}")
        repository.create_follow(self.settings.default_user_slug, bot_slug, self._now())
        return self.get_user_profile()

    def unfollow_bot(self, bot_slug: str) -> UserProfile:
        repository = BotSocietyRepository(self.database)
        repository.delete_follow(self.settings.default_user_slug, bot_slug)
        return self.get_user_profile()

    def add_watchlist_asset(self, asset: str) -> UserProfile:
        repository = BotSocietyRepository(self.database)
        normalized_asset = asset.upper()
        if normalized_asset not in repository.list_assets():
            raise ValueError(f"Unknown asset: {normalized_asset}")
        repository.create_watchlist_item(self.settings.default_user_slug, normalized_asset, self._now())
        return self.get_user_profile()

    def remove_watchlist_asset(self, asset: str) -> UserProfile:
        repository = BotSocietyRepository(self.database)
        repository.delete_watchlist_item(self.settings.default_user_slug, asset.upper())
        return self.get_user_profile()

    def add_alert_rule(self, payload: AlertRuleCreate) -> UserProfile:
        repository = BotSocietyRepository(self.database)
        asset = payload.asset.upper() if payload.asset else None
        if asset and asset not in repository.list_assets():
            raise ValueError(f"Unknown asset: {asset}")
        if payload.bot_slug and not repository.get_bot(payload.bot_slug):
            raise ValueError(f"Unknown bot slug: {payload.bot_slug}")
        repository.create_alert_rule(
            {
                "user_slug": self.settings.default_user_slug,
                "bot_slug": payload.bot_slug,
                "asset": asset,
                "min_confidence": payload.min_confidence,
                "is_active": 1,
                "created_at": self._now(),
            }
        )
        return self.get_user_profile()

    def delete_alert_rule(self, rule_id: int) -> UserProfile:
        repository = BotSocietyRepository(self.database)
        repository.delete_alert_rule(self.settings.default_user_slug, rule_id)
        return self.get_user_profile()

    def get_provider_status(self) -> ProviderStatus:
        return ProviderStatus(
            market_provider_mode=self.settings.market_provider_mode,
            market_provider_source=self.market_provider_source,
            signal_provider_mode=self.settings.signal_provider_mode,
            signal_provider_source=self.signal_provider_source,
            tracked_coin_ids=list(self.settings.tracked_coin_ids),
            rss_feed_urls=list(self.settings.rss_feed_urls),
            market_fallback_active=self.market_provider_fallback,
            signal_fallback_active=self.signal_provider_fallback,
        )

    def get_dashboard_snapshot(self) -> DashboardSnapshot:
        repository = BotSocietyRepository(self.database)
        return DashboardSnapshot(
            summary=self.get_summary(),
            assets=self.get_assets(),
            leaderboard=self._build_bot_summaries(repository, self.settings.default_user_slug),
            recent_predictions=[self._to_prediction_model(row) for row in repository.list_predictions(limit=10)],
            recent_signals=[self._to_signal_model(row) for row in repository.list_recent_signals(limit=8)],
            latest_operation=self._latest_operation(repository),
            user_profile=self.get_user_profile(),
            provider_status=self.get_provider_status(),
        )

    def get_landing_snapshot(self) -> LandingSnapshot:
        repository = BotSocietyRepository(self.database)
        return LandingSnapshot(
            summary=self.get_summary(),
            assets=self.get_assets(),
            leaderboard=self._build_bot_summaries(repository, self.settings.default_user_slug)[:4],
            recent_signals=[self._to_signal_model(row) for row in repository.list_recent_signals(limit=4)],
            provider_status=self.get_provider_status(),
        )

    def get_latest_operation(self) -> OperationSnapshot | None:
        repository = BotSocietyRepository(self.database)
        return self._latest_operation(repository)

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
            signal_batch = self.signal_provider.generate(market_batch, cycle_index)
            if not signal_batch:
                raise ValueError("signal provider returned zero signals")
            self.signal_provider_fallback = False
            self.signal_provider_source = self.signal_provider.source_name
            live_signal_active = self.signal_provider_source != self.demo_signal_provider.source_name
        except Exception as exc:
            signal_batch = self.demo_signal_provider.generate(market_batch, cycle_index)
            self.signal_provider_fallback = True
            self.signal_provider_source = f"{self.signal_provider.source_name}-fallback"
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
                    [*message_prefixes, f"Ingested {ingested_signals} signals, generated {created_predictions} fresh predictions, scored {scored_predictions} eligible predictions, and delivered {delivered_alerts} in-app alerts."]
                ).strip(),
            }
        )
        operation = repository.get_latest_pipeline_run()
        return CycleResult(
            operation=self._to_operation_model(operation),
            leaderboard=self._build_bot_summaries(repository, self.settings.default_user_slug),
            recent_predictions=[self._to_prediction_model(row) for row in repository.list_predictions(limit=10)],
            provider_status=self.get_provider_status(),
            alert_inbox=self.get_alert_inbox(),
        )

    def _deliver_alerts_for_predictions(self, repository: BotSocietyRepository, predictions: list[dict]) -> int:
        if not predictions:
            return 0
        active_rules = repository.list_active_alert_rules()
        if not active_rules:
            return 0

        events: list[dict] = []
        created_at = self._now()
        for prediction in predictions:
            for rule in active_rules:
                if rule["bot_slug"] and rule["bot_slug"] != prediction["bot_slug"]:
                    continue
                if rule["asset"] and rule["asset"] != prediction["asset"]:
                    continue
                if float(prediction["confidence"]) < float(rule["min_confidence"]):
                    continue
                scope = self._alert_scope(rule)
                events.append(
                    {
                        "user_slug": rule["user_slug"],
                        "rule_id": rule["id"],
                        "prediction_id": prediction["id"],
                        "bot_slug": prediction["bot_slug"],
                        "asset": prediction["asset"],
                        "direction": prediction["direction"],
                        "confidence": prediction["confidence"],
                        "title": f"{prediction['bot_name']} issued a {prediction['direction']} {prediction['asset']} call",
                        "message": (
                            f"{prediction['bot_name']} published a {prediction['horizon_label'].lower()} view on {prediction['asset']} with "
                            f"{int(round(float(prediction['confidence']) * 100))}% confidence. Matched {scope}."
                        ),
                        "channel": "in_app",
                        "delivery_status": "delivered",
                        "created_at": created_at,
                        "read_at": None,
                    }
                )
        return repository.upsert_alert_delivery_events(events)

    def _build_bot_summaries(self, repository: BotSocietyRepository, user_slug: str | None = None) -> list[BotSummary]:
        bots = repository.list_bots()
        predictions = repository.list_predictions(limit=500)
        followed_bot_slugs = {row["bot_slug"] for row in repository.list_user_follows(user_slug)} if user_slug else set()
        bot_predictions: dict[str, list[dict]] = {bot["slug"]: [] for bot in bots}
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
            score_series = [row["score"] / 100 for row in scored_rows if row["score"] is not None]
            consistency = clamp(1 - (pstdev(score_series) / 0.25), 0.0, 1.0) if len(score_series) > 1 else (1.0 if score_series else 0.0)
            return_component = clamp((avg_strategy_return + 0.04) / 0.08, 0.0, 1.0)
            composite_score = 100 * (
                0.30 * hit_rate
                + 0.25 * return_component
                + 0.20 * calibration
                + 0.15 * consistency
                + 0.10 * risk_discipline
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

    def _build_market_provider(self):
        if self.settings.market_provider_mode == "coingecko":
            return CoinGeckoMarketProvider(
                plan=self.settings.coingecko_plan,
                api_key=self.settings.coingecko_api_key,
                tracked_coin_ids=self.settings.tracked_coin_ids,
            )
        return self.demo_market_provider

    def _build_signal_provider(self):
        if self.settings.signal_provider_mode == "rss":
            return RSSNewsSignalProvider(feed_urls=self.settings.rss_feed_urls)
        return self.demo_signal_provider

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

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
