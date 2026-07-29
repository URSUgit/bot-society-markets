from __future__ import annotations

import json

import pytest

from api.app.providers import (
    AlpacaEquityProvider,
    AutoMarketProvider,
    BinanceSpotMarketProvider,
    BlockscoutActivityProvider,
    MarketProviderBase,
    ProviderReadiness,
    SecEdgarProvider,
)


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


def test_binance_spot_market_provider_parses_public_ticker(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = [
        {
            "symbol": "BTCUSDT",
            "lastPrice": "103000.50000000",
            "priceChangePercent": "2.400",
            "quoteVolume": "5600000000.12",
            "closeTime": 1778149000000,
        },
        {
            "symbol": "ETHUSDT",
            "lastPrice": "3900.25000000",
            "priceChangePercent": "-1.500",
            "quoteVolume": "2600000000.44",
            "closeTime": 1778149000000,
        },
    ]

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self) -> bytes:
            return json.dumps(payload).encode("utf-8")

    requested_urls: list[str] = []

    def fake_urlopen(request, timeout: int):
        requested_urls.append(request.full_url)
        return FakeResponse()

    monkeypatch.setattr("api.app.providers.urlopen", fake_urlopen)

    provider = BinanceSpotMarketProvider(tracked_coin_ids=("bitcoin", "ethereum"), quote_asset="USDT")
    batch = provider.generate(
        [
            {
                "asset": "BTC",
                "signal_bias": 0.2,
                "price": 100000.0,
                "volume_24h": 1.0,
                "volatility": 0.03,
            }
        ],
        3,
    )

    assert provider.readiness().ready is True
    assert "ticker/24hr" in requested_urls[0]
    assert batch[0]["asset"] == "BTC"
    assert batch[0]["price"] == 103000.5
    assert batch[0]["change_24h"] == 0.024
    assert batch[0]["volume_24h"] == 5600000000.12
    assert batch[0]["source"] == "binance-spot-public-provider"
    assert batch[1]["asset"] == "ETH"
    assert batch[1]["trend_score"] < 0


def test_alpaca_equity_provider_parses_batched_snapshots(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "snapshots": {
            "AAPL": {
                "latestTrade": {"p": 234.5, "t": "2026-07-29T14:30:00Z"},
                "latestQuote": {"bp": 234.4, "ap": 234.6},
                "dailyBar": {"o": 231.0, "h": 235.0, "l": 230.5, "c": 234.5, "v": 1200000},
                "prevDailyBar": {"c": 230.0},
            }
        }
    }

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self) -> bytes:
            return json.dumps(payload).encode("utf-8")

    requested = []

    def fake_urlopen(request, timeout: int):
        requested.append(request)
        return FakeResponse()

    monkeypatch.setattr("api.app.providers.urlopen", fake_urlopen)
    provider = AlpacaEquityProvider(
        api_key="key",
        api_secret="secret",
        symbols=("AAPL",),
        feed="iex",
    )

    rows = provider.fetch_snapshot()

    assert provider.readiness().ready is True
    assert "symbols=AAPL" in requested[0].full_url
    assert requested[0].headers["Apca-api-key-id"] == "key"
    assert rows[0]["symbol"] == "AAPL"
    assert rows[0]["price"] == 234.5
    assert rows[0]["change"] == 4.5
    assert rows[0]["change_percent"] == pytest.approx(4.5 / 230.0)
    assert rows[0]["bid"] == 234.4
    assert rows[0]["ask"] == 234.6


def test_sec_edgar_provider_filters_recent_filings(monkeypatch: pytest.MonkeyPatch) -> None:
    ticker_payload = {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}
    submissions_payload = {
        "name": "Apple Inc.",
        "filings": {
            "recent": {
                "accessionNumber": ["0000320193-26-000001", "0000320193-26-000002"],
                "form": ["10-Q", "4"],
                "filingDate": ["2026-07-28", "2026-07-27"],
                "reportDate": ["2026-06-27", "2026-07-27"],
                "primaryDocument": ["aapl-20260627.htm", "ownership.xml"],
            }
        },
    }
    payloads = [ticker_payload, submissions_payload]

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self) -> bytes:
            return json.dumps(self.payload).encode("utf-8")

    def fake_urlopen(request, timeout: int):
        return FakeResponse(payloads.pop(0))

    monkeypatch.setattr("api.app.providers.urlopen", fake_urlopen)
    provider = SecEdgarProvider(user_agent="BITprivat tests@example.com")

    result = provider.fetch_filings("aapl", forms=("10-Q",), limit=10)

    assert result["cik"] == "0000320193"
    assert result["company_name"] == "Apple Inc."
    assert len(result["filings"]) == 1
    assert result["filings"][0]["form"] == "10-Q"
    assert result["filings"][0]["filing_url"].endswith("/320193/000032019326000001/aapl-20260627.htm")


def test_blockscout_provider_normalizes_transactions_and_token_transfers(monkeypatch: pytest.MonkeyPatch) -> None:
    address = "0x1111111111111111111111111111111111111111"
    transactions_payload = {
        "items": [
            {
                "hash": "0xtx",
                "timestamp": "2026-07-29T12:00:00Z",
                "status": "ok",
                "from": {"hash": address},
                "to": {"hash": "0x2222222222222222222222222222222222222222"},
                "value": "1000000000000000000",
                "fee": {"value": "21000000000000"},
                "method": "transfer",
                "block_number": 123,
            }
        ]
    }
    transfers_payload = {
        "items": [
            {
                "transaction_hash": "0xtoken",
                "timestamp": "2026-07-29T12:01:00Z",
                "from": {"hash": "0x3333333333333333333333333333333333333333"},
                "to": {"hash": address},
                "token": {"name": "USD Coin", "symbol": "USDC", "type": "ERC-20", "decimals": "6"},
                "total": {"value": "2500000"},
            }
        ]
    }
    payloads = [transactions_payload, transfers_payload]

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self) -> bytes:
            return json.dumps(self.payload).encode("utf-8")

    def fake_urlopen(request, timeout: int):
        return FakeResponse(payloads.pop(0))

    monkeypatch.setattr("api.app.providers.urlopen", fake_urlopen)
    provider = BlockscoutActivityProvider(base_urls={"ethereum": "https://eth.blockscout.com"})

    result = provider.fetch_activity("ethereum", address, limit=10)

    assert result["transactions"][0]["direction"] == "outbound"
    assert result["transactions"][0]["value_native"] == 1.0
    assert result["transactions"][0]["fee_native"] == pytest.approx(0.000021)
    assert result["token_transfers"][0]["direction"] == "inbound"
    assert result["token_transfers"][0]["token_symbol"] == "USDC"
    assert result["token_transfers"][0]["amount"] == 2.5
