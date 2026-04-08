from __future__ import annotations

from .repository import BotSocietyRepository
from .utils import parse_timestamp



def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))


class ScoringEngine:
    def __init__(self, repository: BotSocietyRepository, scoring_version: str) -> None:
        self.repository = repository
        self.scoring_version = scoring_version

    def score_available_predictions(self) -> int:
        scored = 0
        pending_predictions = self.repository.list_prediction_rows_for_scoring()
        histories = {asset: self.repository.list_market_history(asset) for asset in self.repository.list_assets()}

        for prediction in pending_predictions:
            asset_history = histories.get(prediction["asset"], [])
            score_payload = self._build_score_payload(prediction, asset_history)
            if not score_payload:
                continue
            self.repository.update_prediction_score(prediction["id"], score_payload)
            scored += 1
        return scored

    def _build_score_payload(self, prediction: dict, history: list[dict]) -> dict | None:
        if not history:
            return None

        published_at = parse_timestamp(prediction["published_at"])
        target_date = published_at.date().toordinal() + prediction["horizon_days"]

        start_snapshot = self._select_start_snapshot(history, published_at)
        end_snapshot = self._select_end_snapshot(history, target_date)
        if not start_snapshot or not end_snapshot:
            return None

        start_price = float(start_snapshot["price"])
        end_price = float(end_snapshot["price"])
        window_prices = [
            float(snapshot["price"])
            for snapshot in history
            if parse_timestamp(snapshot["as_of"]).date() >= parse_timestamp(start_snapshot["as_of"]).date()
            and parse_timestamp(snapshot["as_of"]).date() <= parse_timestamp(end_snapshot["as_of"]).date()
        ]
        market_return = (end_price - start_price) / start_price
        strategy_return = self._strategy_return(prediction["direction"], market_return)
        success = self._direction_success(prediction["direction"], market_return)
        max_adverse_excursion = self._max_adverse_excursion(prediction["direction"], start_price, window_prices)
        calibration_score = clamp(1 - abs((1 if success else 0) - prediction["confidence"]), 0.0, 1.0)
        return_component = clamp(max(strategy_return, 0.0) / 0.06, 0.0, 1.0)
        risk_component = clamp(1 - (abs(max_adverse_excursion) / 0.06), 0.0, 1.0)
        score = 100 * (
            0.35 * (1 if success else 0)
            + 0.25 * return_component
            + 0.25 * calibration_score
            + 0.15 * risk_component
        )

        return {
            "status": "scored",
            "start_price": start_price,
            "end_price": end_price,
            "market_return": round(market_return, 6),
            "strategy_return": round(strategy_return, 6),
            "max_adverse_excursion": round(max_adverse_excursion, 6),
            "score": round(score, 2),
            "calibration_score": round(calibration_score, 6),
            "directional_success": 1 if success else 0,
            "scoring_version": self.scoring_version,
        }

    @staticmethod
    def _select_start_snapshot(history: list[dict], published_at) -> dict | None:
        candidates = [snapshot for snapshot in history if parse_timestamp(snapshot["as_of"]) <= published_at]
        if candidates:
            return candidates[-1]
        return history[0] if history else None

    @staticmethod
    def _select_end_snapshot(history: list[dict], target_ordinal: int) -> dict | None:
        for snapshot in history:
            if parse_timestamp(snapshot["as_of"]).date().toordinal() >= target_ordinal:
                return snapshot
        return None

    @staticmethod
    def _direction_success(direction: str, market_return: float) -> bool:
        if direction == "bullish":
            return market_return > 0
        if direction == "bearish":
            return market_return < 0
        return abs(market_return) <= 0.01

    @staticmethod
    def _strategy_return(direction: str, market_return: float) -> float:
        if direction == "bullish":
            return market_return
        if direction == "bearish":
            return -market_return
        return 0.01 - abs(market_return)

    @staticmethod
    def _max_adverse_excursion(direction: str, start_price: float, window_prices: list[float]) -> float:
        if not window_prices:
            return 0.0
        if direction == "bullish":
            return (min(window_prices) - start_price) / start_price
        if direction == "bearish":
            return (start_price - max(window_prices)) / start_price
        moves = [abs((price - start_price) / start_price) for price in window_prices]
        return -max(moves)
