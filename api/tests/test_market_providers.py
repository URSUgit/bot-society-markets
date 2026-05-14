from __future__ import annotations

import pytest

from api.app.providers import AutoMarketProvider, MarketProviderBase, ProviderReadiness


class FailingMarketProvider(MarketProviderBase):
    source_name = "failing-provider"

    def generate(self, latest_snapshots: list[dict], cycle_index: int) -> list[dict]:
        raise ValueError("feed offline")


class EmptyMarketProvider(MarketProviderBase):
    source_name = "empty-provider"

    def generate(self, latest_snapshots: list[dict], cycle_index: int) -> list[dict]:
        return []


class UnreadyMarketProvider(MarketProviderBase):
    source_name = "unready-provider"

    def readiness(self) -> ProviderReadiness:
        return ProviderReadiness(False, "missing key")

    def generate(self, latest_snapshots: list[dict], cycle_index: int) -> list[dict]:
        raise AssertionError("unready providers should not be called")


class WorkingMarketProvider(MarketProviderBase):
    source_name = "working-provider"

    def generate(self, latest_snapshots: list[dict], cycle_index: int) -> list[dict]:
        return [
            {
                "asset": "BTC",
                "as_of": "2026-05-14T00:00:00Z",
                "price": 100000.0 + cycle_index,
                "change_24h": 0.01,
                "volume_24h": 2500000000.0,
                "volatility": 0.04,
                "trend_score": 0.22,
                "signal_bias": 0.18,
                "source": self.source_name,
            }
        ]


def test_auto_market_provider_uses_first_successful_live_feed() -> None:
    provider = AutoMarketProvider(
        (
            UnreadyMarketProvider(),
            FailingMarketProvider(),
            EmptyMarketProvider(),
            WorkingMarketProvider(),
        )
    )

    readiness = provider.readiness()
    assert readiness.ready is True
    assert "unready-provider" in (readiness.warning or "")

    batch = provider.generate([], 7)

    assert batch[0]["source"] == "working-provider"
    assert batch[0]["price"] == 100007.0
    assert provider.last_source_name == "working-provider"
    assert any("unready-provider: not ready" in diagnostic for diagnostic in provider.last_diagnostics)
    assert any("failing-provider: ValueError" in diagnostic for diagnostic in provider.last_diagnostics)
    assert any("empty-provider: returned zero snapshots" in diagnostic for diagnostic in provider.last_diagnostics)


def test_auto_market_provider_fails_loudly_when_no_feed_returns_data() -> None:
    provider = AutoMarketProvider((UnreadyMarketProvider(), EmptyMarketProvider()))

    with pytest.raises(ValueError, match="could not resolve a live market feed"):
        provider.generate([], 1)

    assert provider.last_source_name == "auto-market-router-unresolved"
