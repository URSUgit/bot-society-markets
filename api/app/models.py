from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

Direction = Literal["bullish", "bearish", "neutral"]
PredictionStatus = Literal["pending", "scored"]
NotificationChannelType = Literal["email", "webhook"]
NotificationDeliveryStatus = Literal["delivered", "retry_scheduled", "failed", "exhausted"]
PaperPositionStatus = Literal["open", "closed"]
SimulationStrategyId = Literal["buy_hold", "trend_follow", "mean_reversion", "breakout", "custom_creator"]
SimulationHistorySourceMode = Literal["auto", "real", "local"]
PaperVenueStatus = Literal["ready", "needs_credentials", "manual_only", "watchlist"]
LaunchReadinessLevel = Literal["selected", "building", "ready", "live"]
BillingPlanKey = Literal["basic", "pro", "enterprise"]
ConnectorState = Literal["live", "ready", "demo", "attention", "planned"]
InfrastructureTaskState = Literal["ready", "attention", "planned"]


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
    wallet_provider_mode: str
    wallet_provider_source: str
    wallet_provider_configured: bool = True
    wallet_provider_live_capable: bool = False
    wallet_provider_ready: bool = True
    wallet_provider_warning: str | None = None
    tracked_coin_ids: list[str]
    fred_series_ids: list[str] = Field(default_factory=list)
    tracked_wallets: list[str] = Field(default_factory=list)
    rss_feed_urls: list[str]
    reddit_subreddits: list[str] = Field(default_factory=list)
    venue_signal_providers: list[ProviderComponentStatus] = Field(default_factory=list)
    market_fallback_active: bool = False
    signal_fallback_active: bool = False
    macro_fallback_active: bool = False
    wallet_fallback_active: bool = False


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


class PaperVenueCapability(BaseModel):
    label: str
    detail: str


class PaperVenueView(BaseModel):
    id: str
    name: str
    category: str
    priority: int = Field(ge=1)
    status: PaperVenueStatus
    configured: bool = False
    live_capable: bool = False
    api_capable: bool = False
    manual_capable: bool = False
    historical_replay_capable: bool = False
    supported_markets: list[str] = Field(default_factory=list)
    api_base_url: str | None = None
    app_url: str
    docs_url: str | None = None
    capability_summary: str
    capabilities: list[PaperVenueCapability] = Field(default_factory=list)
    setup_steps: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    env_keys: list[str] = Field(default_factory=list)
    next_action: str
    safety_note: str
    readiness_score: float = Field(ge=0, le=1)


class PaperVenuesSnapshot(BaseModel):
    generated_at: str
    execution_provider_mode: str
    recommended_venue_id: str
    summary: str
    ready_venues: int = Field(ge=0)
    api_ready_venues: int = Field(ge=0)
    venues: list[PaperVenueView] = Field(default_factory=list)
    activation_sequence: list[str] = Field(default_factory=list)
    safety_rules: list[str] = Field(default_factory=list)


class WalletProfileView(BaseModel):
    address: str
    display_name: str
    bio: str | None = None
    primary_asset: str | None = None
    portfolio_value: float = Field(ge=0)
    lifetime_volume: float = Field(ge=0)
    traded_markets: int = Field(ge=0)
    recent_trades: int = Field(ge=0)
    win_rate: float = Field(ge=0, le=1)
    realized_pnl_30d: float
    buy_ratio: float = Field(ge=0, le=1)
    conviction_score: float = Field(ge=0, le=1)
    smart_money_score: float = Field(ge=0, le=1)
    net_bias: float = Field(ge=-1, le=1)
    recent_markets: list[str] = Field(default_factory=list)
    source: str


class WalletIntelligenceSnapshot(BaseModel):
    generated_at: str
    summary: str
    wallets: list[WalletProfileView] = Field(default_factory=list)
    aggregate_bias: float = Field(ge=-1, le=1)


class EdgeOpportunityView(BaseModel):
    asset: str
    market_source: str
    market_label: str
    market_slug: str | None = None
    implied_probability: float = Field(ge=0, le=1)
    fair_probability: float = Field(ge=0, le=1)
    edge_bps: float
    confidence: float = Field(ge=0, le=1)
    stance: Direction
    liquidity: float = Field(ge=0)
    volume_24h: float = Field(ge=0)
    supporting_signals: list[str] = Field(default_factory=list)
    updated_at: str


class EdgeSnapshot(BaseModel):
    generated_at: str
    summary: str
    opportunities: list[EdgeOpportunityView] = Field(default_factory=list)


class AdvancedBacktestExport(BaseModel):
    generated_at: str
    engine_target: str
    asset: str
    summary: str
    filename: str
    download_url: str | None = None
    filesystem_path: str | None = None
    saved_to_disk: bool = False
    package_filename: str | None = None
    package_download_url: str | None = None
    package_filesystem_path: str | None = None
    payload: dict[str, object]


class SimulationExportArtifact(BaseModel):
    filename: str
    asset: str
    strategy_id: str
    lookback_years: int = Field(ge=1, le=10)
    engine_target: str
    generated_at: str
    size_bytes: int = Field(ge=0)
    download_url: str
    package_filename: str | None = None
    package_download_url: str | None = None


class SimulationStrategyPreset(BaseModel):
    strategy_id: SimulationStrategyId
    label: str
    description: str


class SimulationDataSourceOption(BaseModel):
    mode: SimulationHistorySourceMode
    label: str
    description: str


class SimulationConfig(BaseModel):
    available_assets: list[str] = Field(default_factory=list)
    lookback_year_options: list[int] = Field(default_factory=list)
    strategy_presets: list[SimulationStrategyPreset] = Field(default_factory=list)
    data_source_options: list[SimulationDataSourceOption] = Field(default_factory=list)
    default_strategy_id: SimulationStrategyId
    default_history_source_mode: SimulationHistorySourceMode = "auto"
    default_lookback_years: int = Field(ge=1, le=10)
    default_starting_capital: float = Field(ge=1000)
    default_fee_bps: float = Field(ge=0)
    live_history_capable: bool
    note: str


class SimulationRequest(BaseModel):
    asset: str = Field(min_length=2, max_length=10)
    lookback_years: int = Field(default=5, ge=1, le=10)
    history_source_mode: SimulationHistorySourceMode = "auto"
    strategy_id: SimulationStrategyId = "custom_creator"
    starting_capital: float = Field(default=10000, ge=1000, le=100000000)
    fee_bps: float = Field(default=10, ge=0, le=500)
    fast_window: int = Field(default=20, ge=2, le=240)
    slow_window: int = Field(default=50, ge=3, le=400)
    mean_window: int = Field(default=20, ge=3, le=240)
    breakout_window: int = Field(default=55, ge=3, le=400)
    custom_strategy_name: str = Field(default="Creator Blend", min_length=1, max_length=80)
    creator_trend_weight: float = Field(default=1.0, ge=0, le=3)
    creator_mean_reversion_weight: float = Field(default=0.7, ge=0, le=3)
    creator_breakout_weight: float = Field(default=0.8, ge=0, le=3)
    creator_entry_score: float = Field(default=0.58, ge=0.05, le=1)
    creator_exit_score: float = Field(default=0.34, ge=0, le=0.95)
    creator_max_exposure: float = Field(default=1.0, ge=0.1, le=1)
    creator_pullback_entry_pct: float = Field(default=0.035, ge=0.001, le=0.5)
    creator_stop_loss_pct: float = Field(default=0.12, ge=0.005, le=0.8)
    creator_take_profit_pct: float = Field(default=0.35, ge=0.01, le=3)

    @model_validator(mode="after")
    def validate_windows(self) -> "SimulationRequest":
        self.asset = self.asset.strip().upper()
        self.custom_strategy_name = self.custom_strategy_name.strip() or "Creator Blend"
        if self.fast_window >= self.slow_window:
            raise ValueError("fast_window must be smaller than slow_window")
        if self.creator_exit_score >= self.creator_entry_score:
            raise ValueError("creator_exit_score must be smaller than creator_entry_score")
        if self.creator_trend_weight + self.creator_mean_reversion_weight + self.creator_breakout_weight <= 0:
            raise ValueError("At least one creator signal weight must be greater than zero")
        return self


class SimulationSeriesPoint(BaseModel):
    time: str
    value: float


class SimulationTradeView(BaseModel):
    opened_at: str
    closed_at: str
    entry_price: float = Field(ge=0)
    exit_price: float = Field(ge=0)
    return_pct: float
    holding_days: int = Field(ge=0)


class SimulationLeaderboardEntry(BaseModel):
    strategy_id: SimulationStrategyId
    label: str
    total_return: float
    cagr: float
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float = Field(ge=0, le=1)
    trade_count: int = Field(ge=0)
    exposure_ratio: float = Field(ge=0, le=1)
    final_equity: float = Field(ge=0)
    beat_buy_hold: bool = False


class SimulationStrategyResult(SimulationLeaderboardEntry):
    summary: str
    equity_curve: list[SimulationSeriesPoint] = Field(default_factory=list)
    drawdown_curve: list[SimulationSeriesPoint] = Field(default_factory=list)
    trades: list[SimulationTradeView] = Field(default_factory=list)


class SimulationRunResult(BaseModel):
    asset: str
    requested_lookback_years: int = Field(ge=1, le=10)
    actual_years_covered: float = Field(ge=0)
    period_start: str
    period_end: str
    history_points: int = Field(ge=0)
    data_source: str
    history_note: str | None = None
    benchmark_label: str
    benchmark_total_return: float
    benchmark_curve: list[SimulationSeriesPoint] = Field(default_factory=list)
    selected_result: SimulationStrategyResult
    leaderboard: list[SimulationLeaderboardEntry] = Field(default_factory=list)


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


class BillingPlanView(BaseModel):
    key: BillingPlanKey
    label: str
    headline: str
    price_id: str | None = None
    configured: bool = False
    recommended: bool = False
    features: list[str] = Field(default_factory=list)


class BillingSnapshot(BaseModel):
    provider: str
    configured: bool = False
    checkout_ready: bool = False
    portal_ready: bool = False
    can_manage: bool = False
    tier: str
    summary: str
    warnings: list[str] = Field(default_factory=list)
    available_plans: list[BillingPlanView] = Field(default_factory=list)
    publishable_key: str | None = None
    contact_email: str | None = None
    customer_state: str = "none"
    subscription_status: str | None = None
    plan_key: BillingPlanKey | None = None
    plan_label: str | None = None
    current_period_end: str | None = None
    cancel_at_period_end: bool = False
    has_active_subscription: bool = False
    last_event_type: str | None = None
    provider_customer_id: str | None = None
    provider_subscription_id: str | None = None


class BillingCheckoutSessionRequest(BaseModel):
    plan_key: BillingPlanKey = "basic"
    success_path: str = "/dashboard?billing=success"
    cancel_path: str = "/dashboard?billing=cancelled"

    @model_validator(mode="after")
    def validate_paths(self) -> "BillingCheckoutSessionRequest":
        self.success_path = self.success_path.strip() or "/dashboard?billing=success"
        self.cancel_path = self.cancel_path.strip() or "/dashboard?billing=cancelled"
        if not self.success_path.startswith("/"):
            raise ValueError("success_path must start with /")
        if not self.cancel_path.startswith("/"):
            raise ValueError("cancel_path must start with /")
        return self


class BillingPortalSessionRequest(BaseModel):
    return_path: str = "/dashboard#account-section"

    @model_validator(mode="after")
    def validate_return_path(self) -> "BillingPortalSessionRequest":
        self.return_path = self.return_path.strip() or "/dashboard#account-section"
        if not self.return_path.startswith("/"):
            raise ValueError("return_path must start with /")
        return self


class BillingSessionLaunch(BaseModel):
    provider: str
    url: str
    session_id: str | None = None
    plan_key: BillingPlanKey | None = None


class BillingWebhookAck(BaseModel):
    received: bool = True
    duplicate: bool = False
    event_type: str | None = None
    status: str = "processed"


class ConnectorStatusItem(BaseModel):
    id: str
    label: str
    category: str
    state: ConnectorState
    mode: str
    source: str
    configured: bool = False
    live_capable: bool = False
    summary: str
    target_surface: str
    env_keys: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    app_url: str | None = None


class ConnectorControlSnapshot(BaseModel):
    generated_at: str
    summary: str
    live_or_ready_count: int = Field(ge=0)
    connectors: list[ConnectorStatusItem] = Field(default_factory=list)


class InfrastructureTask(BaseModel):
    key: str
    label: str
    state: InfrastructureTaskState
    detail: str
    next_step: str


class InfrastructureReadinessSnapshot(BaseModel):
    generated_at: str
    production_posture: InfrastructureTaskState
    summary: str
    database_backend: str
    database_target: str
    tasks: list[InfrastructureTask] = Field(default_factory=list)


class LaunchReadinessTrack(BaseModel):
    key: str
    label: str
    level: LaunchReadinessLevel
    headline: str
    summary: str
    recommended_provider: str
    target_release: str
    next_actions: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)


class LaunchReadinessSnapshot(BaseModel):
    generated_at: str
    level: LaunchReadinessLevel
    summary: str
    tracks: list[LaunchReadinessTrack] = Field(default_factory=list)


class DashboardSnapshot(BaseModel):
    summary: Summary
    assets: list[AssetSnapshot]
    leaderboard: list[BotSummary]
    recent_predictions: list[PredictionView]
    recent_signals: list[SignalView]
    system_pulse: SystemPulseSnapshot
    macro_snapshot: MacroSnapshot
    wallet_intelligence: WalletIntelligenceSnapshot
    edge_snapshot: EdgeSnapshot
    paper_trading: PaperTradingSnapshot
    paper_venues: PaperVenuesSnapshot
    latest_operation: OperationSnapshot | None = None
    auth_session: AuthSessionSnapshot
    user_profile: "UserProfile"
    notification_health: NotificationHealthSnapshot
    provider_status: ProviderStatus
    launch_readiness: LaunchReadinessSnapshot
    connector_control: ConnectorControlSnapshot
    infrastructure_readiness: InfrastructureReadinessSnapshot


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
    billing: BillingSnapshot | None = None
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


class LaunchReadinessEnvelope(BaseModel):
    launch_readiness: LaunchReadinessSnapshot


class ConnectorControlEnvelope(BaseModel):
    connector_control: ConnectorControlSnapshot


class InfrastructureReadinessEnvelope(BaseModel):
    infrastructure_readiness: InfrastructureReadinessSnapshot
