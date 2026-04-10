from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

Direction = Literal["bullish", "bearish", "neutral"]
PredictionStatus = Literal["pending", "scored"]
NotificationChannelType = Literal["email", "webhook"]
NotificationDeliveryStatus = Literal["delivered", "retry_scheduled", "failed", "exhausted"]
PaperPositionStatus = Literal["open", "closed"]


class Summary(BaseModel):
    active_bots: int
    tracked_assets: int
    total_predictions: int
    scored_predictions: int
    pending_predictions: int
    average_bot_score: float = Field(ge=0, le=100)
    median_calibration: float = Field(ge=0, le=1)
    signals_last_24h: int
    last_cycle_status: str | None = None
    last_cycle_at: str | None = None


class AssetSnapshot(BaseModel):
    asset: str
    as_of: str
    price: float
    change_24h: float
    volume_24h: float
    volatility: float
    trend_score: float = Field(ge=-1, le=1)
    signal_bias: float = Field(ge=-1, le=1)
    source: str


class AssetHistoryPoint(BaseModel):
    time: str
    value: float


class AssetHistoryEnvelope(BaseModel):
    asset: str
    points: list[AssetHistoryPoint]


class SignalView(BaseModel):
    id: int
    asset: str
    source: str
    provider_name: str
    source_type: str
    author_handle: str | None = None
    engagement_score: float | None = None
    provider_trust_score: float = Field(ge=0, le=1)
    freshness_score: float = Field(ge=0, le=1)
    source_quality_score: float = Field(ge=0, le=1)
    channel: str
    title: str
    summary: str
    sentiment: float = Field(ge=-1, le=1)
    relevance: float = Field(ge=0, le=1)
    url: str
    observed_at: str


class BotSummary(BaseModel):
    slug: str
    name: str
    archetype: str
    focus: str
    horizon_label: str
    thesis: str
    risk_style: str
    asset_universe: list[str]
    score: float = Field(ge=0, le=100)
    hit_rate: float = Field(ge=0, le=1)
    calibration: float = Field(ge=0, le=1)
    provenance_score: float = Field(ge=0, le=1)
    average_strategy_return: float
    predictions: int = Field(ge=0)
    pending_predictions: int = Field(ge=0)
    latest_asset: str | None = None
    latest_direction: Direction | None = None
    last_published_at: str | None = None
    is_followed: bool = False


class PredictionView(BaseModel):
    id: int
    bot_slug: str
    bot_name: str
    asset: str
    direction: Direction
    confidence: float = Field(ge=0, le=1)
    horizon_days: int = Field(ge=1)
    horizon_label: str
    thesis: str
    trigger_conditions: str
    invalidation: str
    published_at: str
    status: PredictionStatus
    start_price: float | None = None
    end_price: float | None = None
    market_return: float | None = None
    strategy_return: float | None = None
    max_adverse_excursion: float | None = None
    score: float | None = None
    calibration_score: float | None = None
    directional_success: bool | None = None


class BotDetail(BotSummary):
    recent_predictions: list[PredictionView]


class OperationSnapshot(BaseModel):
    id: int
    cycle_type: str
    status: str
    started_at: str
    completed_at: str | None = None
    ingested_signals: int = Field(ge=0)
    generated_predictions: int = Field(ge=0)
    scored_predictions: int = Field(ge=0)
    message: str


class ProviderComponentStatus(BaseModel):
    mode: str
    source: str
    configured: bool = True
    live_capable: bool = False
    ready: bool = True
    warning: str | None = None


class ProviderStatus(BaseModel):
    environment_name: str
    deployment_target: str
    database_backend: str
    database_target: str
    market_provider_mode: str
    market_provider_source: str
    market_provider_configured: bool = True
    market_provider_live_capable: bool = False
    market_provider_ready: bool = True
    market_provider_warning: str | None = None
    signal_provider_mode: str
    signal_provider_source: str
    signal_provider_configured: bool = True
    signal_provider_live_capable: bool = False
    signal_provider_ready: bool = True
    signal_provider_warning: str | None = None
    macro_provider_mode: str
    macro_provider_source: str
    macro_provider_configured: bool = True
    macro_provider_live_capable: bool = False
    macro_provider_ready: bool = True
    macro_provider_warning: str | None = None
    tracked_coin_ids: list[str]
    fred_series_ids: list[str] = Field(default_factory=list)
    rss_feed_urls: list[str]
    reddit_subreddits: list[str] = Field(default_factory=list)
    venue_signal_providers: list[ProviderComponentStatus] = Field(default_factory=list)
    market_fallback_active: bool = False
    signal_fallback_active: bool = False
    macro_fallback_active: bool = False


class SignalMixItem(BaseModel):
    label: str
    count: int = Field(ge=0)
    share: float = Field(ge=0, le=1)
    average_quality: float = Field(ge=0, le=1)


class VenuePulseItem(BaseModel):
    source: str
    label: str
    signal_count: int = Field(ge=0)
    assets: list[str] = Field(default_factory=list)
    average_quality: float = Field(ge=0, le=1)
    average_freshness: float = Field(ge=0, le=1)
    average_sentiment: float = Field(ge=-1, le=1)
    latest_title: str | None = None
    latest_at: str | None = None


class SystemPulseSnapshot(BaseModel):
    generated_at: str
    live_provider_count: int = Field(ge=0)
    total_recent_signals: int = Field(ge=0)
    average_signal_quality: float = Field(ge=0, le=1)
    average_signal_freshness: float = Field(ge=0, le=1)
    pending_predictions: int = Field(ge=0)
    retry_queue_depth: int = Field(ge=0)
    signal_mix: list[SignalMixItem] = Field(default_factory=list)
    venue_pulse: list[VenuePulseItem] = Field(default_factory=list)


class MacroObservationPoint(BaseModel):
    time: str
    value: float


class MacroSeriesSnapshot(BaseModel):
    series_id: str
    label: str
    unit: str
    latest_value: float
    change_percent: float
    signal_bias: float = Field(ge=-1, le=1)
    regime_label: str
    source: str
    observed_at: str
    history: list[MacroObservationPoint] = Field(default_factory=list)


class MacroSnapshot(BaseModel):
    generated_at: str
    posture: str
    summary: str
    series: list[MacroSeriesSnapshot] = Field(default_factory=list)


class PaperPortfolioSummary(BaseModel):
    starting_balance: float = Field(ge=0)
    cash_balance: float
    open_exposure: float = Field(ge=0)
    equity: float = Field(ge=0)
    realized_pnl: float
    unrealized_pnl: float
    total_return: float
    win_rate: float = Field(ge=0, le=1)
    open_positions: int = Field(ge=0)
    closed_positions: int = Field(ge=0)


class PaperPositionView(BaseModel):
    id: int
    prediction_id: int
    bot_slug: str
    bot_name: str
    asset: str
    direction: Direction
    confidence: float = Field(ge=0, le=1)
    status: PaperPositionStatus
    opened_at: str
    closed_at: str | None = None
    allocation_usd: float = Field(ge=0)
    quantity: float = Field(ge=0)
    entry_price: float = Field(ge=0)
    current_price: float = Field(ge=0)
    exit_price: float | None = None
    fees_paid: float = Field(ge=0)
    unrealized_pnl: float
    realized_pnl: float | None = None


class PaperTradingSnapshot(BaseModel):
    generated_at: str
    summary: PaperPortfolioSummary
    positions: list[PaperPositionView] = Field(default_factory=list)


class PaperSimulationResult(BaseModel):
    created_positions: int = Field(ge=0)
    closed_positions: int = Field(ge=0)
    snapshot: PaperTradingSnapshot


class NotificationChannel(BaseModel):
    id: int
    user_slug: str
    channel_type: NotificationChannelType
    target: str
    is_active: bool
    created_at: str
    last_delivered_at: str | None = None
    last_error: str | None = None


class AlertDelivery(BaseModel):
    id: int
    user_slug: str
    rule_id: int | None = None
    notification_channel_id: int | None = None
    prediction_id: int
    bot_slug: str
    asset: str
    direction: Direction
    confidence: float = Field(ge=0, le=1)
    title: str
    message: str
    channel: str
    channel_target: str
    delivery_status: NotificationDeliveryStatus
    attempt_count: int = Field(ge=0)
    last_attempt_at: str | None = None
    next_attempt_at: str | None = None
    error_detail: str | None = None
    created_at: str
    read_at: str | None = None
    is_read: bool = False


class AlertInbox(BaseModel):
    unread_count: int = Field(ge=0)
    alerts: list[AlertDelivery]


class NotificationChannelHealth(BaseModel):
    channel_id: int
    channel_type: NotificationChannelType
    target: str
    is_active: bool
    delivered_count: int = Field(ge=0)
    retry_scheduled_count: int = Field(ge=0)
    exhausted_count: int = Field(ge=0)
    last_delivered_at: str | None = None
    last_error: str | None = None


class NotificationHealthSnapshot(BaseModel):
    active_channels: int = Field(ge=0)
    delivered_last_24h: int = Field(ge=0)
    retry_queue_depth: int = Field(ge=0)
    exhausted_deliveries: int = Field(ge=0)
    last_delivery_at: str | None = None
    channels: list[NotificationChannelHealth]


class NotificationRetryResult(BaseModel):
    scanned_events: int = Field(ge=0)
    delivered: int = Field(ge=0)
    rescheduled: int = Field(ge=0)
    exhausted: int = Field(ge=0)


class DashboardSnapshot(BaseModel):
    summary: Summary
    assets: list[AssetSnapshot]
    leaderboard: list[BotSummary]
    recent_predictions: list[PredictionView]
    recent_signals: list[SignalView]
    system_pulse: SystemPulseSnapshot
    macro_snapshot: MacroSnapshot
    paper_trading: PaperTradingSnapshot
    latest_operation: OperationSnapshot | None = None
    auth_session: AuthSessionSnapshot
    user_profile: "UserProfile"
    notification_health: NotificationHealthSnapshot
    provider_status: ProviderStatus


class LandingSnapshot(BaseModel):
    summary: Summary
    assets: list[AssetSnapshot]
    leaderboard: list[BotSummary]
    recent_signals: list[SignalView]
    system_pulse: SystemPulseSnapshot
    macro_snapshot: MacroSnapshot
    provider_status: ProviderStatus


class CycleResult(BaseModel):
    operation: OperationSnapshot | None
    leaderboard: list[BotSummary]
    recent_predictions: list[PredictionView]
    provider_status: ProviderStatus
    alert_inbox: AlertInbox
    notification_health: NotificationHealthSnapshot


class FollowedBot(BaseModel):
    bot_slug: str
    name: str
    score: float = Field(ge=0, le=100)
    created_at: str


class WatchlistItem(BaseModel):
    asset: str
    created_at: str
    latest_price: float | None = None
    change_24h: float | None = None


class AlertRule(BaseModel):
    id: int
    user_slug: str
    bot_slug: str | None = None
    asset: str | None = None
    min_confidence: float = Field(ge=0, le=1)
    is_active: bool
    created_at: str


class AlertRuleCreate(BaseModel):
    bot_slug: str | None = None
    asset: str | None = None
    min_confidence: float = Field(default=0.65, ge=0, le=1)

    @model_validator(mode="after")
    def validate_target(self) -> "AlertRuleCreate":
        if not self.bot_slug and not self.asset:
            raise ValueError("bot_slug or asset is required")
        return self


class NotificationChannelCreate(BaseModel):
    channel_type: NotificationChannelType
    target: str = Field(min_length=3, max_length=320)
    secret: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def validate_target(self) -> "NotificationChannelCreate":
        normalized = self.target.strip()
        if self.channel_type == "webhook" and not normalized.lower().startswith(("http://", "https://")):
            raise ValueError("Webhook targets must start with http:// or https://")
        if self.channel_type == "email" and "@" not in normalized:
            raise ValueError("Email targets must contain @")
        self.target = normalized
        return self


class FollowBotRequest(BaseModel):
    bot_slug: str


class WatchlistAssetRequest(BaseModel):
    asset: str


class UserIdentity(BaseModel):
    slug: str
    display_name: str
    email: str
    tier: str
    is_demo_user: bool = False


class AuthRegisterRequest(BaseModel):
    display_name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=8, max_length=128)


class AuthLoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=8, max_length=128)


class AuthSessionSnapshot(BaseModel):
    authenticated: bool
    user: UserIdentity | None = None


class UserProfile(BaseModel):
    slug: str
    display_name: str
    email: str
    tier: str
    is_demo_user: bool = False
    follows: list[FollowedBot]
    watchlist: list[WatchlistItem]
    alert_rules: list[AlertRule]
    recent_alerts: list[AlertDelivery]
    notification_channels: list[NotificationChannel] = Field(default_factory=list)
    unread_alert_count: int = Field(ge=0)


class ProviderStatusEnvelope(BaseModel):
    provider_status: ProviderStatus


class SystemPulseEnvelope(BaseModel):
    system_pulse: SystemPulseSnapshot
