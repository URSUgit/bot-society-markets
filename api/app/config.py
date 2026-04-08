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
    version: str = "0.6.0"
    database_path: Path = field(default_factory=_default_database_path)
    database_url: str | None = None
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
    auth_cookie_name: str = "bsm_session"
    session_ttl_hours: int = 168
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None
    smtp_use_tls: bool = True
    outbound_timeout_seconds: int = 10
    notification_retry_limit: int = 25
    notification_max_attempts: int = 4
    notification_retry_base_seconds: int = 300


def _split_csv_env(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _env_bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).lower() not in {"0", "false", "no"}


def get_settings() -> Settings:
    database_path = Path(os.getenv("BSM_DATABASE_PATH", str(_default_database_path())))
    database_url = os.getenv("BSM_DATABASE_URL") or None
    seed_demo_data = _env_bool("BSM_SEED_DEMO_DATA", True)

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
    session_ttl_hours = max(1, int(os.getenv("BSM_SESSION_TTL_HOURS", "168")))
    outbound_timeout_seconds = max(3, int(os.getenv("BSM_OUTBOUND_TIMEOUT_SECONDS", "10")))
    notification_retry_limit = max(1, int(os.getenv("BSM_NOTIFICATION_RETRY_LIMIT", "25")))
    notification_max_attempts = max(1, int(os.getenv("BSM_NOTIFICATION_MAX_ATTEMPTS", "4")))
    notification_retry_base_seconds = max(30, int(os.getenv("BSM_NOTIFICATION_RETRY_BASE_SECONDS", "300")))

    return Settings(
        database_path=database_path,
        database_url=database_url,
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
        auth_cookie_name=os.getenv("BSM_AUTH_COOKIE_NAME", "bsm_session"),
        session_ttl_hours=session_ttl_hours,
        smtp_host=os.getenv("BSM_SMTP_HOST") or None,
        smtp_port=max(1, int(os.getenv("BSM_SMTP_PORT", "587"))),
        smtp_username=os.getenv("BSM_SMTP_USERNAME") or None,
        smtp_password=os.getenv("BSM_SMTP_PASSWORD") or None,
        smtp_from_email=os.getenv("BSM_SMTP_FROM_EMAIL") or None,
        smtp_use_tls=_env_bool("BSM_SMTP_USE_TLS", True),
        outbound_timeout_seconds=outbound_timeout_seconds,
        notification_retry_limit=notification_retry_limit,
        notification_max_attempts=notification_max_attempts,
        notification_retry_base_seconds=notification_retry_base_seconds,
    )
