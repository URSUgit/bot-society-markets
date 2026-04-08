from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

MarketProviderMode = Literal["demo", "coingecko"]
SignalProviderMode = Literal["demo", "rss"]


def _workspace_database_path() -> Path:
    return Path("api/data/bot_society_markets.db")


def _temporary_database_path() -> Path:
    return Path(tempfile.gettempdir()) / "BotSocietyMarkets" / "bot_society_markets.db"


def _default_database_path() -> Path:
    candidates: list[Path] = []
    local_appdata = os.getenv("LOCALAPPDATA")
    if local_appdata:
        candidates.append(Path(local_appdata) / "BotSocietyMarkets" / "bot_society_markets.db")
    candidates.append(_temporary_database_path())
    candidates.append(_workspace_database_path())

    for candidate in candidates:
        try:
            candidate.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            continue
        return candidate

    return _workspace_database_path()


@dataclass(slots=True)
class Settings:
    project_name: str = "Bot Society Markets"
    version: str = "0.4.0"
    database_path: Path = field(default_factory=_default_database_path)
    seed_demo_data: bool = True
    scoring_version: str = "v1"
    default_user_slug: str = "demo-operator"
    market_provider_mode: MarketProviderMode = "demo"
    signal_provider_mode: SignalProviderMode = "demo"
    coingecko_api_key: str | None = None
    coingecko_plan: Literal["demo", "pro"] = "demo"
    tracked_coin_ids: tuple[str, ...] = ("bitcoin", "ethereum", "solana")
    rss_feed_urls: tuple[str, ...] = ()
    worker_interval_seconds: int = 900
    worker_max_cycles: int = 0
    alert_inbox_limit: int = 10



def _split_csv_env(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())



def get_settings() -> Settings:
    database_path = Path(os.getenv("BSM_DATABASE_PATH", str(_default_database_path())))
    seed_demo_data = os.getenv("BSM_SEED_DEMO_DATA", "true").lower() not in {"0", "false", "no"}

    market_provider_mode = os.getenv("BSM_MARKET_PROVIDER", "demo").lower()
    if market_provider_mode not in {"demo", "coingecko"}:
        market_provider_mode = "demo"

    signal_provider_mode = os.getenv("BSM_SIGNAL_PROVIDER", "demo").lower()
    if signal_provider_mode not in {"demo", "rss"}:
        signal_provider_mode = "demo"

    plan = os.getenv("BSM_COINGECKO_PLAN", "demo").lower()
    if plan not in {"demo", "pro"}:
        plan = "demo"

    coin_ids = _split_csv_env(os.getenv("BSM_TRACKED_COIN_IDS", "bitcoin,ethereum,solana"))
    rss_feed_urls = _split_csv_env(os.getenv("BSM_RSS_FEED_URLS", ""))

    worker_interval_seconds = max(30, int(os.getenv("BSM_WORKER_INTERVAL_SECONDS", "900")))
    worker_max_cycles = max(0, int(os.getenv("BSM_WORKER_MAX_CYCLES", "0")))
    alert_inbox_limit = max(1, min(50, int(os.getenv("BSM_ALERT_INBOX_LIMIT", "10"))))

    return Settings(
        database_path=database_path,
        seed_demo_data=seed_demo_data,
        market_provider_mode=market_provider_mode,
        signal_provider_mode=signal_provider_mode,
        coingecko_api_key=os.getenv("BSM_COINGECKO_API_KEY") or None,
        coingecko_plan=plan,
        tracked_coin_ids=coin_ids or ("bitcoin", "ethereum", "solana"),
        rss_feed_urls=rss_feed_urls,
        worker_interval_seconds=worker_interval_seconds,
        worker_max_cycles=worker_max_cycles,
        alert_inbox_limit=alert_inbox_limit,
    )
