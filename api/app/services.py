from __future__ import annotations

from statistics import mean, median, pstdev

from .config import Settings
from .database import Database
from .models import (
    AssetSnapshot,
    BotDetail,
    BotSummary,
    CycleResult,
    DashboardSnapshot,
    LandingSnapshot,
    OperationSnapshot,
    PredictionView,
    SignalView,
    Summary,
)
from .orchestration import PredictionOrchestrator
from .providers import DemoMarketProvider, DemoSignalProvider
from .repository import BotSocietyRepository
from .scoring import ScoringEngine, clamp
from .seed import seed_demo_dataset
from .utils import parse_timestamp, to_timestamp


class BotSocietyService:
    def __init__(self, database: Database, settings: Settings) -> None:
        self.database = database
        self.settings = settings
        self.market_provider = DemoMarketProvider()
        self.signal_provider = DemoSignalProvider()
        self.orchestrator = PredictionOrchestrator()

    def bootstrap(self) -> None:
        self.database.initialize()
        repository = BotSocietyRepository(self.database)
        seeded = seed_demo_dataset(repository) if self.settings.seed_demo_data else False
        scorer = ScoringEngine(repository, self.settings.scoring_version)
        scored = scorer.score_available_predictions()
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
                    "message": "Seeded demo market data, historical signals, and scored the initial prediction archive.",
                }
            )

    def get_summary(self) -> Summary:
        repository = BotSocietyRepository(self.database)
        bots = self._build_bot_summaries(repository)
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
        return self._build_bot_summaries(repository)

    def get_bot_detail(self, slug: str) -> BotDetail | None:
        repository = BotSocietyRepository(self.database)
        summaries = self._build_bot_summaries(repository)
        summary = next((bot for bot in summaries if bot.slug == slug), None)
        if not summary:
            return None
        recent_predictions = [
            self._to_prediction_model(row)
            for row in repository.list_predictions(bot_slug=slug, limit=8)
        ]
        return BotDetail(**summary.model_dump(), recent_predictions=recent_predictions)

    def get_dashboard_snapshot(self) -> DashboardSnapshot:
        repository = BotSocietyRepository(self.database)
        return DashboardSnapshot(
            summary=self.get_summary(),
            assets=self.get_assets(),
            leaderboard=self._build_bot_summaries(repository),
            recent_predictions=[self._to_prediction_model(row) for row in repository.list_predictions(limit=10)],
            recent_signals=[self._to_signal_model(row) for row in repository.list_recent_signals(limit=8)],
            latest_operation=self._latest_operation(repository),
        )

    def get_landing_snapshot(self) -> LandingSnapshot:
        repository = BotSocietyRepository(self.database)
        return LandingSnapshot(
            summary=self.get_summary(),
            assets=self.get_assets(),
            leaderboard=self._build_bot_summaries(repository)[:4],
            recent_signals=[self._to_signal_model(row) for row in repository.list_recent_signals(limit=4)],
        )

    def get_latest_operation(self) -> OperationSnapshot | None:
        repository = BotSocietyRepository(self.database)
        return self._latest_operation(repository)

    def run_pipeline_cycle(self) -> CycleResult:
        repository = BotSocietyRepository(self.database)
        latest_snapshots = repository.list_latest_market_snapshots()
        cycle_index = repository.count_pipeline_runs("demo-cycle") + 1
        market_batch = self.market_provider.generate(latest_snapshots, cycle_index)
        repository.upsert_market_snapshots(market_batch)
        signal_batch = self.signal_provider.generate(market_batch, cycle_index)
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

        scorer = ScoringEngine(repository, self.settings.scoring_version)
        scored_predictions = scorer.score_available_predictions()
        run_id = repository.insert_pipeline_run(
            {
                "cycle_type": "demo-cycle",
                "status": "completed",
                "started_at": published_at,
                "completed_at": published_at,
                "ingested_signals": ingested_signals,
                "generated_predictions": created_predictions,
                "scored_predictions": scored_predictions,
                "message": "Ingested a new demo market batch, refreshed the signal layer, and generated fresh pending predictions.",
            }
        )
        operation = repository.get_latest_pipeline_run()
        return CycleResult(
            operation=self._to_operation_model({**operation, "id": run_id} if operation else None),
            leaderboard=self._build_bot_summaries(repository),
            recent_predictions=[self._to_prediction_model(row) for row in repository.list_predictions(limit=10)],
        )

    def _build_bot_summaries(self, repository: BotSocietyRepository) -> list[BotSummary]:
        bots = repository.list_bots()
        predictions = repository.list_predictions(limit=500)
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
            risk_discipline = mean(clamp(1 - abs(row["max_adverse_excursion"] or 0.0) / 0.06, 0.0, 1.0) for row in scored_rows) if scored_rows else 0.0
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
                )
            )
        return sorted(summaries, key=lambda bot: bot.score, reverse=True)

    @staticmethod
    def _to_asset_model(row: dict) -> AssetSnapshot:
        return AssetSnapshot(**row)

    @staticmethod
    def _to_signal_model(row: dict) -> SignalView:
        return SignalView(**row)

    @staticmethod
    def _to_prediction_model(row: dict) -> PredictionView:
        payload = {**row, "directional_success": bool(row["directional_success"]) if row["directional_success"] is not None else None}
        return PredictionView(**payload)

    def _latest_operation(self, repository: BotSocietyRepository) -> OperationSnapshot | None:
        row = repository.get_latest_pipeline_run()
        return self._to_operation_model(row)

    @staticmethod
    def _to_operation_model(row: dict | None) -> OperationSnapshot | None:
        if not row:
            return None
        return OperationSnapshot(**row)
