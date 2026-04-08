from __future__ import annotations

from datetime import timedelta

from .utils import parse_timestamp, to_timestamp


class DemoMarketProvider:
    def generate(self, latest_snapshots: list[dict], cycle_index: int) -> list[dict]:
        if not latest_snapshots:
            return []

        latest_time = max(parse_timestamp(snapshot["as_of"]) for snapshot in latest_snapshots)
        next_time = latest_time + timedelta(hours=6)
        adjustments = {
            "BTC": (0.006 + 0.001 * (cycle_index % 3), 0.03, 0.02),
            "ETH": (0.009 + 0.001 * (cycle_index % 2), 0.04, 0.025),
            "SOL": (0.013 + 0.002 * (cycle_index % 2), 0.06, 0.04),
        }

        generated = []
        for snapshot in latest_snapshots:
            base_move, volatility_bump, bias_bump = adjustments.get(snapshot["asset"], (0.005, 0.02, 0.02))
            generated.append(
                {
                    "asset": snapshot["asset"],
                    "as_of": to_timestamp(next_time),
                    "price": round(snapshot["price"] * (1 + base_move), 2),
                    "change_24h": round(base_move, 6),
                    "volume_24h": round(snapshot["volume_24h"] * (1 + 0.02 + 0.01 * cycle_index), 2),
                    "volatility": round(snapshot["volatility"] + volatility_bump * 0.05, 6),
                    "trend_score": max(-1.0, min(1.0, round(snapshot["trend_score"] + 0.06, 6))),
                    "signal_bias": max(-1.0, min(1.0, round(snapshot["signal_bias"] + bias_bump, 6))),
                    "source": "demo-market-provider",
                }
            )
        return generated


class DemoSignalProvider:
    def generate(self, market_batch: list[dict], cycle_index: int) -> list[dict]:
        generated = []
        for snapshot in market_batch:
            observed_at = snapshot["as_of"]
            asset = snapshot["asset"]
            positive = snapshot["signal_bias"] >= 0
            social_sentiment = round(snapshot["signal_bias"] * 0.92, 6)
            news_sentiment = round(snapshot["trend_score"] * 0.78, 6)

            generated.append(
                {
                    "external_id": f"demo-social-{cycle_index}-{asset.lower()}",
                    "asset": asset,
                    "source": "X",
                    "channel": "social",
                    "title": f"{asset} trader cluster {'leans' if positive else 'turns'} {'higher' if positive else 'defensive'} on the next session",
                    "summary": f"A curated watchlist of market accounts shows {'expanding' if positive else 'softening'} conviction around {asset}, with narrative strength tied to price structure.",
                    "sentiment": social_sentiment,
                    "relevance": 0.8 if asset != "SOL" else 0.86,
                    "url": f"https://example.com/live/social/{cycle_index}/{asset.lower()}",
                    "observed_at": observed_at,
                    "ingest_batch_id": f"demo-cycle-{cycle_index}",
                }
            )
            generated.append(
                {
                    "external_id": f"demo-news-{cycle_index}-{asset.lower()}",
                    "asset": asset,
                    "source": "DeskWire",
                    "channel": "news",
                    "title": f"{asset} market structure {'improves' if positive else 'faces a balance check'} as flows reset",
                    "summary": f"Desk commentary frames {asset} as {'constructive' if positive else 'fragile'} after the most recent market repricing phase.",
                    "sentiment": news_sentiment,
                    "relevance": 0.76,
                    "url": f"https://example.com/live/news/{cycle_index}/{asset.lower()}",
                    "observed_at": observed_at,
                    "ingest_batch_id": f"demo-cycle-{cycle_index}",
                }
            )
        return generated
