from __future__ import annotations

import json


class PredictionOrchestrator:
    def build_predictions(
        self,
        *,
        bots: list[dict],
        latest_snapshots: list[dict],
        recent_signals: list[dict],
        published_at: str,
        pending_lookup: set[str],
    ) -> list[dict]:
        snapshot_map = {snapshot["asset"]: snapshot for snapshot in latest_snapshots}
        signals_by_asset: dict[str, list[dict]] = {}
        for signal in recent_signals:
            signals_by_asset.setdefault(signal["asset"], []).append(signal)

        generated: list[dict] = []
        for bot in bots:
            if bot["slug"] in pending_lookup:
                continue
            prediction = self._prediction_for_bot(bot, snapshot_map, signals_by_asset, published_at)
            if prediction:
                generated.append(prediction)
        return generated

    def _prediction_for_bot(
        self,
        bot: dict,
        snapshots: dict[str, dict],
        signals_by_asset: dict[str, list[dict]],
        published_at: str,
    ) -> dict | None:
        slug = bot["slug"]
        if slug == "social-momentum":
            return self._social_momentum(bot, snapshots, signals_by_asset, published_at)
        if slug == "macro-narrative":
            return self._macro_narrative(bot, snapshots, signals_by_asset, published_at)
        if slug == "breakout":
            return self._breakout(bot, snapshots, signals_by_asset, published_at)
        if slug == "contrarian":
            return self._contrarian(bot, snapshots, signals_by_asset, published_at)
        if slug == "risk-sentinel":
            return self._risk_sentinel(bot, snapshots, signals_by_asset, published_at)
        if slug == "news-reaction":
            return self._news_reaction(bot, snapshots, signals_by_asset, published_at)
        return None

    @staticmethod
    def _top_signal(signals: list[dict], channel: str | None = None) -> dict | None:
        filtered = [signal for signal in signals if channel is None or signal["channel"] == channel]
        if not filtered:
            return None
        return max(filtered, key=lambda signal: signal["relevance"] * (abs(signal["sentiment"]) + 0.1))

    def _social_momentum(self, bot: dict, snapshots: dict[str, dict], signals_by_asset: dict[str, list[dict]], published_at: str) -> dict | None:
        ranked_assets = []
        for asset, signals in signals_by_asset.items():
            social = self._top_signal(signals, "social")
            snapshot = snapshots.get(asset)
            if social and snapshot:
                ranked_assets.append((asset, social["sentiment"] * social["relevance"] + snapshot["trend_score"], social, snapshot))
        if not ranked_assets:
            return None
        asset, _, signal, snapshot = max(ranked_assets, key=lambda item: item[1])
        confidence = min(0.82, max(0.58, 0.56 + signal["relevance"] * 0.18 + max(snapshot["trend_score"], 0) * 0.14))
        direction = "bullish" if signal["sentiment"] >= 0 else "bearish"
        return self._base_prediction(
            bot_slug=bot["slug"],
            asset=asset,
            direction=direction,
            confidence=round(confidence, 2),
            horizon_days=3,
            horizon_label="3 days",
            thesis=f"Social conviction and price structure are aligned in {asset}, creating a short continuation setup.",
            trigger_conditions="Trend and crowd participation remain aligned through the next liquid session.",
            invalidation="Narrative interest fades during the first structural retest.",
            signal_ids=[signal["id"]],
            published_at=published_at,
            start_price=snapshot["price"],
        )

    def _macro_narrative(self, bot: dict, snapshots: dict[str, dict], signals_by_asset: dict[str, list[dict]], published_at: str) -> dict | None:
        candidates = []
        for asset in ("BTC", "ETH"):
            snapshot = snapshots.get(asset)
            signals = signals_by_asset.get(asset, [])
            macro_signal = self._top_signal(signals)
            if snapshot and macro_signal:
                strength = snapshot["trend_score"] + macro_signal["sentiment"] * 0.7
                candidates.append((asset, strength, macro_signal, snapshot))
        if not candidates:
            return None
        asset, _, signal, snapshot = max(candidates, key=lambda item: item[1])
        direction = "bullish" if signal["sentiment"] >= -0.05 else "bearish"
        confidence = min(0.78, max(0.56, 0.55 + max(snapshot["trend_score"], 0) * 0.18 + signal["relevance"] * 0.1))
        return self._base_prediction(
            bot_slug=bot["slug"],
            asset=asset,
            direction=direction,
            confidence=round(confidence, 2),
            horizon_days=7,
            horizon_label="7 days",
            thesis=f"Macro flow language and broader risk tone keep {asset} in a structurally favorable position.",
            trigger_conditions="Breadth and liquidity remain constructive across the next weekly window.",
            invalidation="Cross-asset risk compresses and reverses the recent reclaim.",
            signal_ids=[signal["id"]],
            published_at=published_at,
            start_price=snapshot["price"],
        )

    def _breakout(self, bot: dict, snapshots: dict[str, dict], signals_by_asset: dict[str, list[dict]], published_at: str) -> dict | None:
        if not snapshots:
            return None
        asset, snapshot = max(snapshots.items(), key=lambda item: item[1]["change_24h"] + item[1]["trend_score"])
        signal = self._top_signal(signals_by_asset.get(asset, []))
        confidence = min(0.76, max(0.54, 0.52 + max(snapshot["change_24h"], 0) * 4 + snapshot["trend_score"] * 0.14))
        return self._base_prediction(
            bot_slug=bot["slug"],
            asset=asset,
            direction="bullish" if snapshot["change_24h"] >= 0 else "bearish",
            confidence=round(confidence, 2),
            horizon_days=1,
            horizon_label="1 day",
            thesis=f"{asset} is showing the cleanest breakout profile across price, trend, and participation.",
            trigger_conditions="Breakout level holds during the next volatility check.",
            invalidation="Immediate failure back into the prior consolidation range.",
            signal_ids=[signal["id"]] if signal else [],
            published_at=published_at,
            start_price=snapshot["price"],
        )

    def _contrarian(self, bot: dict, snapshots: dict[str, dict], signals_by_asset: dict[str, list[dict]], published_at: str) -> dict | None:
        extremes = []
        for asset, signals in signals_by_asset.items():
            signal = self._top_signal(signals)
            snapshot = snapshots.get(asset)
            if signal and snapshot:
                extremes.append((asset, abs(signal["sentiment"]) + abs(snapshot["signal_bias"]), signal, snapshot))
        if not extremes:
            return None
        asset, _, signal, snapshot = max(extremes, key=lambda item: item[1])
        direction = "bearish" if signal["sentiment"] >= 0 else "bullish"
        confidence = min(0.73, max(0.53, 0.51 + abs(signal["sentiment"]) * 0.2 + snapshot["volatility"] * 1.3))
        return self._base_prediction(
            bot_slug=bot["slug"],
            asset=asset,
            direction=direction,
            confidence=round(confidence, 2),
            horizon_days=3,
            horizon_label="3 days",
            thesis=f"{asset} looks crowded enough for a controlled counter-trend move over the next few sessions.",
            trigger_conditions="Crowd positioning remains one-sided while momentum begins to flatten.",
            invalidation="Consensus continues to strengthen alongside fresh participation.",
            signal_ids=[signal["id"]],
            published_at=published_at,
            start_price=snapshot["price"],
        )

    def _risk_sentinel(self, bot: dict, snapshots: dict[str, dict], signals_by_asset: dict[str, list[dict]], published_at: str) -> dict | None:
        if not snapshots:
            return None
        asset, snapshot = max(snapshots.items(), key=lambda item: item[1]["volatility"])
        direction = "bearish" if snapshot["volatility"] > 0.055 else "neutral"
        confidence = 0.58 if direction == "bearish" else 0.55
        signal = self._top_signal(signals_by_asset.get(asset, []))
        return self._base_prediction(
            bot_slug=bot["slug"],
            asset=asset,
            direction=direction,
            confidence=confidence,
            horizon_days=3,
            horizon_label="3 days",
            thesis=f"{asset} is carrying the highest short-term fragility signal across the monitored universe.",
            trigger_conditions="Volatility stays elevated while breadth fails to improve.",
            invalidation="Risk compresses quickly and the market absorbs the recent stress cleanly.",
            signal_ids=[signal["id"]] if signal else [],
            published_at=published_at,
            start_price=snapshot["price"],
        )

    def _news_reaction(self, bot: dict, snapshots: dict[str, dict], signals_by_asset: dict[str, list[dict]], published_at: str) -> dict | None:
        ranked_news = []
        for asset, signals in signals_by_asset.items():
            signal = self._top_signal(signals, "news")
            snapshot = snapshots.get(asset)
            if signal and snapshot:
                ranked_news.append((asset, signal["relevance"] + abs(signal["sentiment"]), signal, snapshot))
        if not ranked_news:
            return None
        asset, _, signal, snapshot = max(ranked_news, key=lambda item: item[1])
        direction = "bullish" if signal["sentiment"] >= 0 else "bearish"
        confidence = min(0.74, max(0.55, 0.53 + signal["relevance"] * 0.16 + abs(signal["sentiment"]) * 0.12))
        return self._base_prediction(
            bot_slug=bot["slug"],
            asset=asset,
            direction=direction,
            confidence=round(confidence, 2),
            horizon_days=1,
            horizon_label="1 day",
            thesis=f"The latest news pulse still looks underpriced in {asset} relative to current follow-through conditions.",
            trigger_conditions="Headline momentum keeps feeding into spot participation over the next session.",
            invalidation="The market fully absorbs the event without continuation volume.",
            signal_ids=[signal["id"]],
            published_at=published_at,
            start_price=snapshot["price"],
        )

    @staticmethod
    def _base_prediction(**kwargs) -> dict:
        signal_ids = kwargs.pop("signal_ids")
        return {
            **kwargs,
            "source_signal_ids": json.dumps(signal_ids),
            "status": "pending",
        }
