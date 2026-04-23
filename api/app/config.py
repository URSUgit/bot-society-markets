from __future__ import annotations
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional during bootstrap before deps install
    load_dotenv = None

MarketProviderMode = Literal["demo", "coingecko", "hyperliquid"]
SignalProviderMode = Literal["demo", "rss", "reddit"]
VenueSignalProviderMode = Literal["polymarket", "kalshi"]
MacroProviderMode = Literal["demo", "fred"]
WalletProviderMode = Literal["demo", "polymarket"]
PaperExecutionProviderMode = Literal["internal", "polysandbox", "kalshi_demo", "hyperliquid_testnet", "lorem_ipsum_trade"]
SiteHomePage = Literal["landing", "dashboard"]
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_environment_files() -> None:
    if load_dotenv is None:
        return
    load_dotenv(PROJECT_ROOT / ".env")
    load_dotenv(PROJECT_ROOT / ".env.local", override=True)


_load_environment_files()


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


def _default_export_artifacts_dir() -> Path:
    return PROJECT_ROOT / "artifacts" / "strategy-exports"


@dataclass(slots=True)
class Settings:
    project_name: str = "Bot Society Markets"
    version: str = "0.6.0"
    environment_name: str = "development"
    deployment_target: str = "local"
    site_home_page: SiteHomePage = "landing"
    canonical_host: str | None = None
    canonical_redirect_hosts: tuple[str, ...] = ()
    force_https: bool = False
    secure_session_cookie: bool | None = None
    database_path: Path = field(default_factory=_default_database_path)
    export_artifacts_dir: Path = field(default_factory=_default_export_artifacts_dir)
    database_url: str | None = None
    seed_demo_data: bool = True
    scoring_version: str = "v1"
    default_user_slug: str = "demo-operator"
    market_provider_mode: MarketProviderMode = "demo"
    signal_provider_mode: SignalProviderMode = "demo"
    venue_signal_providers: tuple[VenueSignalProviderMode, ...] = ()
    macro_provider_mode: MacroProviderMode = "demo"
    wallet_provider_mode: WalletProviderMode = "demo"
    coingecko_api_key: str | None = None
    coingecko_plan: Literal["demo", "pro"] = "demo"
    tracked_coin_ids: tuple[str, ...] = ("bitcoin", "ethereum", "solana")
    fred_api_key: str | None = None
    fred_series_ids: tuple[str, ...] = ("FEDFUNDS", "DGS10", "CPIAUCSL", "WALCL", "VIXCLS")
    hyperliquid_dex: str = ""
    rss_feed_urls: tuple[str, ...] = ()
    reddit_client_id: str | None = None
    reddit_client_secret: str | None = None
    reddit_user_agent: str = "BotSocietyMarkets/0.7"
    reddit_subreddits: tuple[str, ...] = ("CryptoCurrency", "Bitcoin", "ethtrader", "solana")
    reddit_post_limit: int = 15
    polymarket_tag_id: int = 21
    polymarket_event_limit: int = 30
    tracked_wallets: tuple[str, ...] = ()
    wallet_trade_limit: int = 25
    kalshi_category: str = "Crypto"
    kalshi_series_limit: int = 12
    kalshi_markets_per_series: int = 4
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
    paper_starting_balance: float = 10000.0
    paper_trade_fee_bps: float = 10.0
    paper_trade_slippage_bps: float = 15.0
    paper_execution_provider: PaperExecutionProviderMode = "internal"
    polysandbox_api_url: str = "https://api.polysandbox.trade/v1"
    polysandbox_app_url: str = "https://app.polysandbox.trade"
    polysandbox_docs_url: str = "https://docs.polysandbox.trade"
    polysandbox_api_key: str | None = None
    polysandbox_sandbox_id: str | None = None
    kalshi_demo_api_url: str = "https://demo-api.kalshi.co/trade-api/v2"
    kalshi_demo_app_url: str = "https://demo.kalshi.co/"
    kalshi_demo_key_id: str | None = None
    kalshi_demo_private_key_path: str | None = None
    hyperliquid_testnet_api_url: str = "https://api.hyperliquid-testnet.xyz"
    hyperliquid_testnet_ws_url: str = "wss://api.hyperliquid-testnet.xyz/ws"
    hyperliquid_testnet_app_url: str = "https://app.hyperliquid-testnet.xyz"
    hyperliquid_testnet_wallet_address: str | None = None
    hyperliquid_testnet_private_key: str | None = None
    lorem_ipsum_trade_clob_url: str = "https://clob.loremipsumtrade.com"
    lorem_ipsum_trade_app_url: str = "https://sandbox.loremipsumtrade.com"
    lorem_ipsum_trade_enabled: bool = False
    simulation_live_history: bool = True
    simulation_cache_hours: int = 12

    def __post_init__(self) -> None:
        canonical_host = self.canonical_host.strip().lower() if self.canonical_host else None
        redirect_hosts = tuple(
            host
            for host in dict.fromkeys(host.strip().lower() for host in self.canonical_redirect_hosts if host.strip())
            if host and host != canonical_host
        )
        secure_session_cookie = self.force_https if self.secure_session_cookie is None else self.secure_session_cookie

        object.__setattr__(self, "canonical_host", canonical_host)
        object.__setattr__(self, "canonical_redirect_hosts", redirect_hosts)
        object.__setattr__(self, "secure_session_cookie", secure_session_cookie)


def _split_csv_env(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _env_bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).lower() not in {"0", "false", "no"}


def get_settings() -> Settings:
    database_path = Path(os.getenv("BSM_DATABASE_PATH", str(_default_database_path())))
    database_url = os.getenv("BSM_DATABASE_URL") or None
    seed_demo_data = _env_bool("BSM_SEED_DEMO_DATA", True)
    force_https = _env_bool("BSM_FORCE_HTTPS", False)
    secure_session_cookie_env = os.getenv("BSM_SECURE_SESSION_COOKIE")
    secure_session_cookie = None if secure_session_cookie_env is None else _env_bool("BSM_SECURE_SESSION_COOKIE", False)

    market_provider_mode = os.getenv("BSM_MARKET_PROVIDER", "demo").lower()
    if market_provider_mode not in {"demo", "coingecko", "hyperliquid"}:
        market_provider_mode = "demo"

    signal_provider_mode = os.getenv("BSM_SIGNAL_PROVIDER", "demo").lower()
    if signal_provider_mode not in {"demo", "rss", "reddit"}:
        signal_provider_mode = "demo"

    macro_provider_mode = os.getenv("BSM_MACRO_PROVIDER", "demo").lower()
    if macro_provider_mode not in {"demo", "fred"}:
        macro_provider_mode = "demo"

    wallet_provider_mode = os.getenv("BSM_WALLET_PROVIDER", "demo").lower()
    if wallet_provider_mode not in {"demo", "polymarket"}:
        wallet_provider_mode = "demo"

    paper_execution_provider = os.getenv("BSM_PAPER_EXECUTION_PROVIDER", "internal").lower()
    if paper_execution_provider not in {"internal", "polysandbox", "kalshi_demo", "hyperliquid_testnet", "lorem_ipsum_trade"}:
        paper_execution_provider = "internal"

    venue_signal_providers = tuple(
        provider
        for provider in _split_csv_env(os.getenv("BSM_VENUE_SIGNAL_PROVIDERS", ""))
        if provider in {"polymarket", "kalshi"}
    )

    plan = os.getenv("BSM_COINGECKO_PLAN", "demo").lower()
    if plan not in {"demo", "pro"}:
        plan = "demo"

    site_home_page = os.getenv("BSM_SITE_HOME_PAGE", "landing").lower()
    if site_home_page not in {"landing", "dashboard"}:
        site_home_page = "landing"
    canonical_host = os.getenv("BSM_CANONICAL_HOST") or None
    canonical_redirect_hosts = _split_csv_env(os.getenv("BSM_CANONICAL_REDIRECT_HOSTS", ""))

    coin_ids = _split_csv_env(os.getenv("BSM_TRACKED_COIN_IDS", "bitcoin,ethereum,solana"))
    fred_series_ids = _split_csv_env(os.getenv("BSM_FRED_SERIES_IDS", "FEDFUNDS,DGS10,CPIAUCSL,WALCL,VIXCLS"))
    tracked_wallets = _split_csv_env(os.getenv("BSM_TRACKED_WALLETS", ""))
    rss_feed_urls = _split_csv_env(os.getenv("BSM_RSS_FEED_URLS", ""))
    reddit_subreddits = _split_csv_env(os.getenv("BSM_REDDIT_SUBREDDITS", "CryptoCurrency,Bitcoin,ethtrader,solana"))

    worker_interval_seconds = max(30, int(os.getenv("BSM_WORKER_INTERVAL_SECONDS", "900")))
    worker_max_cycles = max(0, int(os.getenv("BSM_WORKER_MAX_CYCLES", "0")))
    alert_inbox_limit = max(1, min(50, int(os.getenv("BSM_ALERT_INBOX_LIMIT", "10"))))
    session_ttl_hours = max(1, int(os.getenv("BSM_SESSION_TTL_HOURS", "168")))
    outbound_timeout_seconds = max(3, int(os.getenv("BSM_OUTBOUND_TIMEOUT_SECONDS", "10")))
    reddit_post_limit = max(5, min(50, int(os.getenv("BSM_REDDIT_POST_LIMIT", "15"))))
    polymarket_tag_id = max(1, int(os.getenv("BSM_POLYMARKET_TAG_ID", "21")))
    polymarket_event_limit = max(5, min(100, int(os.getenv("BSM_POLYMARKET_EVENT_LIMIT", "30"))))
    wallet_trade_limit = max(5, min(100, int(os.getenv("BSM_WALLET_TRADE_LIMIT", "25"))))
    kalshi_series_limit = max(1, min(50, int(os.getenv("BSM_KALSHI_SERIES_LIMIT", "12"))))
    kalshi_markets_per_series = max(1, min(10, int(os.getenv("BSM_KALSHI_MARKETS_PER_SERIES", "4"))))
    notification_retry_limit = max(1, int(os.getenv("BSM_NOTIFICATION_RETRY_LIMIT", "25")))
    notification_max_attempts = max(1, int(os.getenv("BSM_NOTIFICATION_MAX_ATTEMPTS", "4")))
    notification_retry_base_seconds = max(30, int(os.getenv("BSM_NOTIFICATION_RETRY_BASE_SECONDS", "300")))
    simulation_cache_hours = max(1, int(os.getenv("BSM_SIMULATION_CACHE_HOURS", "12")))
    export_artifacts_dir = Path(os.getenv("BSM_EXPORT_ARTIFACTS_DIR", str(_default_export_artifacts_dir())))

    return Settings(
        environment_name=os.getenv("BSM_ENVIRONMENT_NAME", "development"),
        deployment_target=os.getenv("BSM_DEPLOYMENT_TARGET", "local"),
        site_home_page=site_home_page,
        canonical_host=canonical_host,
        canonical_redirect_hosts=canonical_redirect_hosts,
        force_https=force_https,
        secure_session_cookie=secure_session_cookie,
        database_path=database_path,
        export_artifacts_dir=export_artifacts_dir,
        database_url=database_url,
        seed_demo_data=seed_demo_data,
        market_provider_mode=market_provider_mode,
        signal_provider_mode=signal_provider_mode,
        venue_signal_providers=venue_signal_providers,
        macro_provider_mode=macro_provider_mode,
        wallet_provider_mode=wallet_provider_mode,
        coingecko_api_key=os.getenv("BSM_COINGECKO_API_KEY") or None,
        coingecko_plan=plan,
        tracked_coin_ids=coin_ids or ("bitcoin", "ethereum", "solana"),
        fred_api_key=os.getenv("BSM_FRED_API_KEY") or None,
        fred_series_ids=fred_series_ids or ("FEDFUNDS", "DGS10", "CPIAUCSL", "WALCL", "VIXCLS"),
        tracked_wallets=tracked_wallets,
        hyperliquid_dex=os.getenv("BSM_HYPERLIQUID_DEX", ""),
        rss_feed_urls=rss_feed_urls,
        reddit_client_id=os.getenv("BSM_REDDIT_CLIENT_ID") or None,
        reddit_client_secret=os.getenv("BSM_REDDIT_CLIENT_SECRET") or None,
        reddit_user_agent=os.getenv("BSM_REDDIT_USER_AGENT", "BotSocietyMarkets/0.7"),
        reddit_subreddits=reddit_subreddits or ("CryptoCurrency", "Bitcoin", "ethtrader", "solana"),
        reddit_post_limit=reddit_post_limit,
        polymarket_tag_id=polymarket_tag_id,
        polymarket_event_limit=polymarket_event_limit,
        wallet_trade_limit=wallet_trade_limit,
        kalshi_category=os.getenv("BSM_KALSHI_CATEGORY", "Crypto"),
        kalshi_series_limit=kalshi_series_limit,
        kalshi_markets_per_series=kalshi_markets_per_series,
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
        paper_starting_balance=max(1000.0, float(os.getenv("BSM_PAPER_STARTING_BALANCE", "10000"))),
        paper_trade_fee_bps=max(0.0, float(os.getenv("BSM_PAPER_TRADE_FEE_BPS", "10"))),
        paper_trade_slippage_bps=max(0.0, float(os.getenv("BSM_PAPER_TRADE_SLIPPAGE_BPS", "15"))),
        paper_execution_provider=paper_execution_provider,
        polysandbox_api_url=os.getenv("BSM_POLYSANDBOX_API_URL", "https://api.polysandbox.trade/v1"),
        polysandbox_app_url=os.getenv("BSM_POLYSANDBOX_APP_URL", "https://app.polysandbox.trade"),
        polysandbox_docs_url=os.getenv("BSM_POLYSANDBOX_DOCS_URL", "https://docs.polysandbox.trade"),
        polysandbox_api_key=os.getenv("BSM_POLYSANDBOX_API_KEY") or None,
        polysandbox_sandbox_id=os.getenv("BSM_POLYSANDBOX_SANDBOX_ID") or None,
        kalshi_demo_api_url=os.getenv("BSM_KALSHI_DEMO_API_URL", "https://demo-api.kalshi.co/trade-api/v2"),
        kalshi_demo_app_url=os.getenv("BSM_KALSHI_DEMO_APP_URL", "https://demo.kalshi.co/"),
        kalshi_demo_key_id=os.getenv("BSM_KALSHI_DEMO_KEY_ID") or None,
        kalshi_demo_private_key_path=os.getenv("BSM_KALSHI_DEMO_PRIVATE_KEY_PATH") or None,
        hyperliquid_testnet_api_url=os.getenv("BSM_HYPERLIQUID_TESTNET_API_URL", "https://api.hyperliquid-testnet.xyz"),
        hyperliquid_testnet_ws_url=os.getenv("BSM_HYPERLIQUID_TESTNET_WS_URL", "wss://api.hyperliquid-testnet.xyz/ws"),
        hyperliquid_testnet_app_url=os.getenv("BSM_HYPERLIQUID_TESTNET_APP_URL", "https://app.hyperliquid-testnet.xyz"),
        hyperliquid_testnet_wallet_address=os.getenv("BSM_HYPERLIQUID_TESTNET_WALLET_ADDRESS") or None,
        hyperliquid_testnet_private_key=os.getenv("BSM_HYPERLIQUID_TESTNET_PRIVATE_KEY") or None,
        lorem_ipsum_trade_clob_url=os.getenv("BSM_LOREM_IPSUM_TRADE_CLOB_URL", "https://clob.loremipsumtrade.com"),
        lorem_ipsum_trade_app_url=os.getenv("BSM_LOREM_IPSUM_TRADE_APP_URL", "https://sandbox.loremipsumtrade.com"),
        lorem_ipsum_trade_enabled=_env_bool("BSM_LOREM_IPSUM_TRADE_ENABLED", False),
        simulation_live_history=_env_bool("BSM_SIMULATION_LIVE_HISTORY", True),
        simulation_cache_hours=simulation_cache_hours,
    )
