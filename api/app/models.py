from __future__ import annotations

import re
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
OrderSide = Literal["buy", "sell", "long", "short"]
OrderType = Literal["market", "limit", "stop", "stop_limit", "trailing"]
OrderStatus = Literal["pending", "open", "filled", "cancelled", "rejected"]
LaunchReadinessLevel = Literal["selected", "building", "ready", "live"]
BillingPlanKey = Literal["basic", "pro", "enterprise"]
ConnectorState = Literal["live", "ready", "demo", "attention", "planned"]
ConnectorDiagnosticStatus = Literal["pass", "warn", "fail", "blocked"]
RiskCheckStatus = Literal["pass", "warn", "fail", "blocked"]
InfrastructureTaskState = Literal["ready", "attention", "planned"]
FeatureReadinessState = Literal["live", "paper_only", "partial", "blocked", "planned"]
SocialPlatform = Literal["youtube", "x", "reddit", "telegram", "newsletter", "other"]
SocialTradeMode = Literal["signals", "managed_paper"]
SocialTraderState = Literal["discovered", "watching", "followed", "paused"]
SocialRiskLevel = Literal["low", "medium", "high"]
SocialCopyTradeReadiness = Literal["paper_ready", "signals_only", "needs_review"]
SocialValidationState = Literal["validated", "proxy"]
SocialSourceState = Literal["live", "indexed", "ready_to_scan", "planned", "connector_build_required"]
CreatorBotLearningStage = Literal["awaiting_evidence", "youtube_profile_active", "multi_source_profile", "paper_validation"]
TraderIntelligenceCategory = Literal["trader", "investor", "educator", "founder", "analyst", "macro_thinker", "other"]
TraderIntelligenceSourceType = Literal["youtube_channel", "youtube_playlist", "youtube_video", "podcast", "blog", "newsletter", "document", "manual_url_list", "other"]
TraderIntelligenceStatus = Literal["queued", "importing", "transcribing", "analyzing", "completed", "failed"]
AuthOnboardingStage = Literal["identity", "risk", "suitability", "kyc", "complete"]
KycStatus = Literal["not_started", "pending", "approved", "rejected"]
UiTheme = Literal["day", "night"]
UiLanguage = Literal["en", "ro"]
WorkspaceMode = Literal["simple", "pro"]


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
    provenance_score: float | None = Field(default=None, ge=0, le=1)
    source_signal_count: int = Field(default=0, ge=0)
    provider_mix: list[str] = Field(default_factory=list)
    source_mix: list[str] = Field(default_factory=list)
    top_signal_quality: float | None = Field(default=None, ge=0, le=1)
    venue_support_share: float | None = Field(default=None, ge=0, le=1)


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
    social_discovery_provider_mode: str = "demo"
    social_discovery_provider_source: str = "demo-social-discovery"
    social_discovery_configured: bool = True
    social_discovery_live_capable: bool = False
    social_discovery_ready: bool = True
    social_discovery_warning: str | None = None
    youtube_discovery_queries: list[str] = Field(default_factory=list)
    youtube_channel_ids: list[str] = Field(default_factory=list)
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
    social_discovery_fallback_active: bool = False


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


class SocialManagedPaperExecutionRequest(BaseModel):
    trader_id: int | None = Field(default=None, ge=1)
    max_positions: int = Field(default=3, ge=1, le=12)
    min_confidence: float = Field(default=0.55, ge=0, le=1)


class SocialManagedPaperDecision(BaseModel):
    trader_id: int = Field(ge=1)
    trader_name: str
    signal_id: int | None = Field(default=None, ge=1)
    prediction_id: int | None = Field(default=None, ge=1)
    position_id: int | None = Field(default=None, ge=1)
    asset: str
    direction: Direction
    action: str
    confidence: float = Field(ge=0, le=1)
    notional_usd: float = Field(default=0, ge=0)
    reason: str
    source_title: str
    source_url: str
    observed_at: str


class SocialManagedPaperExecutionResult(BaseModel):
    evaluated_allocations: int = Field(ge=0)
    created_predictions: int = Field(ge=0)
    created_positions: int = Field(ge=0)
    closed_positions: int = Field(ge=0)
    skipped_signals: int = Field(ge=0)
    messages: list[str] = Field(default_factory=list)
    decisions: list[SocialManagedPaperDecision] = Field(default_factory=list)
    snapshot: PaperTradingSnapshot


class TradingOrderRequest(BaseModel):
    venue: str = Field(default="paper", min_length=2, max_length=64)
    asset: str = Field(min_length=2, max_length=16)
    side: OrderSide
    order_type: OrderType = "market"
    quantity: float | None = Field(default=None, gt=0)
    notional_usd: float | None = Field(default=None, gt=0)
    price: float | None = Field(default=None, gt=0)
    prediction_id: int | None = Field(default=None, ge=1)
    is_paper: bool = True
    client_order_id: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def normalize_order_request(self) -> "TradingOrderRequest":
        self.venue = self.venue.strip().lower()
        self.asset = self.asset.strip().upper()
        if self.quantity is None and self.notional_usd is None:
            raise ValueError("Provide either quantity or notional_usd")
        if self.order_type == "limit" and self.price is None:
            raise ValueError("Limit orders require a price")
        if self.client_order_id is not None:
            self.client_order_id = self.client_order_id.strip() or None
        return self


class TradingRiskCheckItem(BaseModel):
    key: str
    label: str
    status: RiskCheckStatus
    detail: str
    observed_value: float | None = None
    limit_value: float | None = None
    unit: str = "USD"


class TradingRiskCheckResult(BaseModel):
    approved: bool
    live_trading_blocked: bool
    execution_mode: str
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    checks: list[TradingRiskCheckItem] = Field(default_factory=list)


class TradingOrderPreview(BaseModel):
    preview_id: str
    generated_at: str
    user_slug: str
    venue: str
    asset: str
    side: OrderSide
    order_type: OrderType
    is_paper: bool
    execution_mode: str
    reference_price: float | None = Field(default=None, ge=0)
    estimated_fill_price: float | None = Field(default=None, ge=0)
    quantity: float = Field(default=0, ge=0)
    notional_usd: float = Field(default=0, ge=0)
    estimated_fee: float = Field(default=0, ge=0)
    estimated_total_cost: float = Field(default=0, ge=0)
    estimated_slippage_bps: float = Field(default=0, ge=0)
    fee_bps: float = Field(default=0, ge=0)
    cash_balance: float | None = None
    open_exposure: float | None = None
    equity: float | None = None
    risk_limits: dict[str, float] = Field(default_factory=dict)
    risk: TradingRiskCheckResult
    message: str
    next_action: str


class TradingOrderView(BaseModel):
    id: int
    user_slug: str
    prediction_id: int | None = None
    venue: str
    asset: str
    side: OrderSide
    order_type: OrderType
    is_paper: bool
    quantity: float = Field(ge=0)
    notional_usd: float = Field(ge=0)
    price: float | None = Field(default=None, ge=0)
    status: OrderStatus
    filled_quantity: float = Field(ge=0)
    avg_fill_price: float | None = Field(default=None, ge=0)
    fee: float = Field(ge=0)
    fee_currency: str
    exchange_order_id: str | None = None
    rejection_reason: str | None = None
    submitted_at: str
    filled_at: str | None = None
    cancelled_at: str | None = None
    metadata: dict[str, object] | None = None


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


class StrategyCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    config: SimulationRequest

    @model_validator(mode="after")
    def normalize_strategy_create(self) -> "StrategyCreateRequest":
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("Strategy name is required")
        if self.description is not None:
            self.description = self.description.strip() or None
        return self


class StrategyUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    config: SimulationRequest | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def normalize_strategy_update(self) -> "StrategyUpdateRequest":
        if self.name is not None:
            self.name = self.name.strip()
            if not self.name:
                raise ValueError("Strategy name is required")
        if self.description is not None:
            self.description = self.description.strip() or None
        return self


class StrategyBacktestRequest(BaseModel):
    config_override: SimulationRequest | None = None


class StrategyView(BaseModel):
    id: int
    user_slug: str
    name: str
    description: str | None = None
    config: SimulationRequest
    is_active: bool
    created_at: str
    updated_at: str


class BacktestRunView(BaseModel):
    id: int
    strategy_id: int
    user_slug: str
    asset: str
    strategy_key: str
    lookback_years: int = Field(ge=1, le=10)
    status: str
    started_at: str
    completed_at: str | None = None
    summary: dict[str, object]
    result: SimulationRunResult | None = None
    error_message: str | None = None


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
    readiness_score: float = Field(default=0.0, ge=0, le=1)
    activation_phase: str = "Selected"
    owner: str = "Platform"
    risk_level: str = "medium"
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


class ConnectorDiagnosticCheck(BaseModel):
    key: str
    label: str
    status: ConnectorDiagnosticStatus
    detail: str
    required: bool = True


class ConnectorDiagnosticResult(BaseModel):
    connector_id: str
    label: str
    generated_at: str
    overall_status: ConnectorDiagnosticStatus
    ready_to_activate: bool = False
    safe_to_promote: bool = False
    checks: list[ConnectorDiagnosticCheck] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)


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


class ProductionCutoverStep(BaseModel):
    key: str
    label: str
    state: InfrastructureTaskState
    detail: str
    command: str | None = None


class ProductionCutoverSnapshot(BaseModel):
    generated_at: str
    posture: InfrastructureTaskState
    current_backend: str
    current_target: str
    target_backend: str
    summary: str
    source_data_note: str
    verification_urls: list[str] = Field(default_factory=list)
    steps: list[ProductionCutoverStep] = Field(default_factory=list)


class OperationsInfraService(BaseModel):
    key: str
    label: str
    status: str
    mode: str
    detail: str
    target: str | None = None
    freshness: str | None = None
    metrics: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    next_action: str


class OperationsInfraCost(BaseModel):
    denom: str = "uact"
    source: str
    web_max_bid_uact_per_block: float = Field(ge=0)
    worker_max_bid_uact_per_block: float = Field(ge=0)
    total_max_bid_uact_per_block: float = Field(ge=0)
    estimated_hourly_act: float = Field(ge=0)
    estimated_daily_act: float = Field(ge=0)
    estimated_monthly_act: float = Field(ge=0)
    note: str


class OperationsInfrastructureSnapshot(BaseModel):
    generated_at: str
    posture: InfrastructureTaskState
    summary: str
    environment_name: str
    deployment_target: str
    public_hosts: list[str] = Field(default_factory=list)
    database_backend: str
    database_target: str
    services: list[OperationsInfraService] = Field(default_factory=list)
    akash_cost: OperationsInfraCost
    live_origin_required: bool = True
    risk_notes: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)


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


class FeatureReadinessItem(BaseModel):
    key: str
    label: str
    category: str
    state: FeatureReadinessState
    user_visible: str
    truth: str
    reason: str
    impact: str
    next_action: str
    route: str | None = None
    severity: int = Field(default=2, ge=1, le=5)


class FeatureReadinessSnapshot(BaseModel):
    generated_at: str
    headline: str
    summary: str
    live_count: int = Field(ge=0)
    paper_only_count: int = Field(ge=0)
    partial_count: int = Field(ge=0)
    blocked_count: int = Field(ge=0)
    planned_count: int = Field(ge=0)
    items: list[FeatureReadinessItem] = Field(default_factory=list)
    priority_fixes: list[str] = Field(default_factory=list)


class BusinessModelProduct(BaseModel):
    key: str
    name: str
    segment: str
    pricing_model: str
    buyer: str
    positioning: str
    core_capabilities: list[str] = Field(default_factory=list)
    expansion_paths: list[str] = Field(default_factory=list)
    risk_controls: list[str] = Field(default_factory=list)


class BusinessModelRevenueStream(BaseModel):
    key: str
    label: str
    model: str
    detail: str
    priority: str


class BusinessModelStrategyFamily(BaseModel):
    key: str
    label: str
    description: str
    monetization_role: str
    required_data: list[str] = Field(default_factory=list)
    enabled_by: list[str] = Field(default_factory=list)


class BusinessModelMoatStep(BaseModel):
    key: str
    label: str
    description: str
    output: str


class BusinessModelTeamRole(BaseModel):
    key: str
    label: str
    responsibility: str
    timing: str


class BusinessModelMilestone(BaseModel):
    horizon: str
    label: str
    target_metrics: list[str] = Field(default_factory=list)
    capital_use: str


class BusinessModelSnapshot(BaseModel):
    generated_at: str
    source_deck: str
    thesis: str
    wedge: str
    engine_workflow: list[str] = Field(default_factory=list)
    products: list[BusinessModelProduct] = Field(default_factory=list)
    revenue_streams: list[BusinessModelRevenueStream] = Field(default_factory=list)
    strategy_families: list[BusinessModelStrategyFamily] = Field(default_factory=list)
    moat_loop: list[BusinessModelMoatStep] = Field(default_factory=list)
    go_to_market: list[str] = Field(default_factory=list)
    investor_model: list[str] = Field(default_factory=list)
    team_plan: list[BusinessModelTeamRole] = Field(default_factory=list)
    milestones: list[BusinessModelMilestone] = Field(default_factory=list)
    seed_raise: str
    compliance_guardrails: list[str] = Field(default_factory=list)
    next_build_priorities: list[str] = Field(default_factory=list)


class SocialEvidenceItem(BaseModel):
    external_id: str
    platform: SocialPlatform
    title: str
    summary: str
    url: str
    asset: str
    direction: Direction
    confidence: float = Field(ge=0, le=1)
    engagement_score: float = Field(ge=0, le=1)
    evidence_weight: float = Field(ge=0, le=1)
    impact_label: str
    risk_flag: str | None = None
    observed_at: str
    derived_return: float


class SocialTraderAllocationGuidance(BaseModel):
    recommended_mode: SocialTradeMode
    suggested_allocation_usd: float = Field(ge=0)
    max_single_position_usd: float = Field(ge=0)
    max_position_pct: float = Field(ge=0, le=1)
    rationale: str


class SocialRoiWindow(BaseModel):
    label: str
    period_days: int = Field(ge=0)
    return_pct: float
    pnl_usd: float
    signal_count: int = Field(ge=0)
    win_rate: float = Field(ge=0, le=1)


class SocialTraderDecision(BaseModel):
    asset: str
    direction: Direction
    action: str
    confidence: float = Field(ge=0, le=1)
    rationale: str
    source_title: str
    source_url: str
    observed_at: str


class SocialTraderAssetExposure(BaseModel):
    asset: str
    signal_count: int = Field(ge=0)
    bias: Direction
    average_return: float


class SocialSourceStatus(BaseModel):
    platform: SocialPlatform
    label: str
    state: SocialSourceState
    configured: bool = False
    indexed_items: int = Field(default=0, ge=0)
    monitored_profiles: int = Field(default=0, ge=0)
    last_observed_at: str | None = None
    role: str
    content_types: list[str] = Field(default_factory=list)
    next_action: str


class CreatorBotTrainingStatus(BaseModel):
    bot_name: str
    stage: CreatorBotLearningStage
    dataset_events: int = Field(default=0, ge=0)
    indexed_sources: list[SocialPlatform] = Field(default_factory=list)
    source_coverage_pct: float = Field(default=0, ge=0, le=1)
    evidence_confidence: float = Field(default=0, ge=0, le=1)
    validation_mode: str
    model_version: str = "creator-profile-v0.1"
    last_updated_at: str | None = None
    next_action: str


class SocialBackendRuntime(BaseModel):
    api_service: str
    persistence: str
    continuous_worker: str
    execution_boundary: str
    market_validation: str


class SocialTraderScorecard(BaseModel):
    id: int
    creator_id: str | None = None
    slug: str
    display_name: str
    handle: str
    platform: SocialPlatform
    source_url: str
    avatar_seed: str
    avatar_url: str | None = None
    description: str
    primary_assets: list[str] = Field(default_factory=list)
    style_tags: list[str] = Field(default_factory=list)
    signal_count: int = Field(ge=0)
    tracked_years: float = Field(ge=0)
    win_rate: float = Field(ge=0, le=1)
    average_roi: float
    roi_if_followed: float
    validation_state: SocialValidationState = "proxy"
    resolved_call_count: int = Field(default=0, ge=0)
    hit_rate: float | None = Field(default=None, ge=0, le=1)
    hit_rate_ci: float | None = Field(default=None, ge=0, le=1)
    avg_return: float | None = None
    risk_adjusted_return: float | None = None
    proxy_roi: float | None = None
    score_history: list[float] = Field(default_factory=list)
    primary_asset: str | None = None
    risk_tier: SocialRiskLevel | None = None
    deploy_status: str = "not_deployed"
    last_resolved_at: str | None = None
    max_drawdown: float = Field(le=0)
    sharpe_like: float
    consistency_score: float = Field(ge=0, le=1)
    influence_score: float = Field(ge=0, le=1)
    recency_score: float = Field(ge=0, le=1)
    composite_score: float = Field(ge=0, le=100)
    last_signal_at: str | None = None
    state: SocialTraderState = "discovered"
    risk_level: SocialRiskLevel
    conviction_label: str
    copy_trade_readiness: SocialCopyTradeReadiness
    watch_mode_recommendation: str
    evidence_summary: str
    risk_notes: list[str] = Field(default_factory=list)
    allocation_guidance: SocialTraderAllocationGuidance
    evidence: list[SocialEvidenceItem] = Field(default_factory=list)
    is_deployed: bool = False
    deployment_mode: SocialTradeMode | None = None
    delegated_usd: float = Field(default=0, ge=0)
    deployed_max_position_pct: float = Field(default=0, ge=0, le=1)
    avatar_animation: str = "youtube-pulse"
    analysis_basis: str = "YouTube title, description, channel metadata, engagement, and market-context heuristics"
    strategy_profile: str = "Strategy profile will be inferred from the trader's indexed public evidence."
    current_market_view: str = "Current market view will appear after the latest monitored video is analyzed."
    pnl_history_summary: str = "PnL history is calculated from extracted public calls and simulated paper-follow outcomes."
    roi_windows: list[SocialRoiWindow] = Field(default_factory=list)
    decision_feed: list[SocialTraderDecision] = Field(default_factory=list)
    asset_exposure: list[SocialTraderAssetExposure] = Field(default_factory=list)
    creator_bot: CreatorBotTrainingStatus | None = None
    source_coverage: list[SocialSourceStatus] = Field(default_factory=list)
    performance_basis: str = "Content-derived proxy; performance is not market-validated PnL."

    @model_validator(mode="after")
    def populate_validation_aliases(self) -> "SocialTraderScorecard":
        if self.creator_id is None:
            self.creator_id = self.slug
        if self.proxy_roi is None:
            self.proxy_roi = self.roi_if_followed
        if self.primary_asset is None and self.primary_assets:
            self.primary_asset = self.primary_assets[0]
        if self.risk_tier is None:
            self.risk_tier = self.risk_level
        if not self.score_history:
            current_score = round(float(self.composite_score or 0), 2)
            self.score_history = [
                round(max(0.0, current_score * 0.86), 2),
                round(max(0.0, current_score * 0.94), 2),
                current_score,
            ]
        if self.resolved_call_count < 20:
            self.validation_state = "proxy"
            self.hit_rate = None
            self.hit_rate_ci = None
            self.avg_return = None
            self.risk_adjusted_return = None
        elif self.validation_state == "validated" and self.hit_rate is None:
            self.hit_rate = self.win_rate
        return self


class SocialTraderAllocation(BaseModel):
    id: int
    user_slug: str
    trader_id: int
    trader_slug: str
    trader_name: str
    mode: SocialTradeMode
    allocation_limit_usd: float = Field(ge=0)
    max_position_pct: float = Field(ge=0, le=1)
    auto_rebalance: bool
    is_active: bool
    created_at: str
    updated_at: str


class SocialDiscoveryRunView(BaseModel):
    id: int
    provider: str
    status: str
    youtube_configured: bool
    discovered: int = Field(ge=0)
    updated: int = Field(ge=0)
    evidence_count: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)
    started_at: str
    completed_at: str


class SocialMonitoringStatus(BaseModel):
    mode: str
    cadence_seconds: int = Field(ge=0)
    provider: str
    youtube_configured: bool
    query_terms: list[str] = Field(default_factory=list)
    channel_ids: list[str] = Field(default_factory=list)
    title_filter: str
    analysis_pipeline: list[str] = Field(default_factory=list)
    auto_signal_creation: bool = True
    next_action: str


class SocialTradingSnapshot(BaseModel):
    generated_at: str
    provider_mode: str
    youtube_required: bool = True
    youtube_configured: bool
    summary: str
    top_traders: list[SocialTraderScorecard] = Field(default_factory=list)
    allocations: list[SocialTraderAllocation] = Field(default_factory=list)
    portfolio_limit_usd: float = Field(ge=0)
    allocated_usd: float = Field(ge=0)
    unallocated_usd: float = Field(ge=0)
    latest_discovery_run: SocialDiscoveryRunView | None = None
    discovery_runs: list[SocialDiscoveryRunView] = Field(default_factory=list)
    diversification_plan: list[str] = Field(default_factory=list)
    portfolio_risk_notes: list[str] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)
    monitoring: SocialMonitoringStatus | None = None
    decision_feed: list[SocialTraderDecision] = Field(default_factory=list)
    source_connectors: list[SocialSourceStatus] = Field(default_factory=list)
    backend_runtime: SocialBackendRuntime | None = None
    bot_factory_pipeline: list[str] = Field(default_factory=list)
    performance_disclaimer: str = "Content-derived proxy results are not yet verified against historical market prices or fills."


class SocialTradingEnvelope(BaseModel):
    social_trading: SocialTradingSnapshot


class TraderIntelligenceCitation(BaseModel):
    source_id: int | None = None
    title: str
    url: str | None = None
    timestamp: str | None = None


class TraderIntelligenceClaim(BaseModel):
    claim: str
    confidence: float = Field(ge=0, le=1)
    citations: list[TraderIntelligenceCitation] = Field(default_factory=list)


class TraderIntelligenceSection(BaseModel):
    summary: str
    claims: list[TraderIntelligenceClaim] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class TraderIntelligenceSourceView(BaseModel):
    id: int
    profile_id: int
    external_id: str
    source_type: TraderIntelligenceSourceType | str
    title: str
    url: str
    author: str | None = None
    observed_at: str
    summary: str
    transcript_available: bool = False
    metadata: dict[str, object] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class TraderIntelligenceRunView(BaseModel):
    id: int
    profile_id: int
    user_slug: str
    status: TraderIntelligenceStatus
    stage: str
    progress: float = Field(ge=0, le=1)
    source_count: int = Field(ge=0)
    error_message: str | None = None
    started_at: str
    completed_at: str | None = None
    created_at: str
    updated_at: str


class TraderIntelligenceProfileView(BaseModel):
    id: int
    user_slug: str
    slug: str
    display_name: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    category: TraderIntelligenceCategory | str
    source_type: TraderIntelligenceSourceType | str
    source_url: str
    status: TraderIntelligenceStatus
    progress_stage: str
    source_count: int = Field(ge=0)
    confidence_score: float = Field(ge=0, le=1)
    worldview: TraderIntelligenceSection
    frameworks: TraderIntelligenceSection
    strategy: TraderIntelligenceSection
    synthesis: TraderIntelligenceSection
    contradictions: list[TraderIntelligenceClaim] = Field(default_factory=list)
    evolution: TraderIntelligenceSection
    vocabulary: list[TraderIntelligenceClaim] = Field(default_factory=list)
    decision_rules: list[TraderIntelligenceClaim] = Field(default_factory=list)
    risk_rules: list[TraderIntelligenceClaim] = Field(default_factory=list)
    recommendations: list[TraderIntelligenceClaim] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    sources: list[TraderIntelligenceSourceView] = Field(default_factory=list)
    latest_run: TraderIntelligenceRunView | None = None
    last_analyzed_at: str | None = None
    created_at: str
    updated_at: str


class TraderIntelligenceWorkspace(BaseModel):
    generated_at: str
    summary: str
    profiles: list[TraderIntelligenceProfileView] = Field(default_factory=list)
    prompt_templates: list[dict[str, str]] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)


class TraderIntelligenceCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    category: TraderIntelligenceCategory = "trader"
    source_type: TraderIntelligenceSourceType = "youtube_channel"
    source_url: str = Field(min_length=2, max_length=1000)
    description: str | None = Field(default=None, max_length=1200)
    tags: list[str] = Field(default_factory=list, max_length=12)
    max_sources: int = Field(default=12, ge=1, le=50)

    @model_validator(mode="after")
    def normalize_create_request(self) -> "TraderIntelligenceCreateRequest":
        self.name = re.sub(r"\s+", " ", self.name).strip()
        self.source_url = re.sub(r"\s+", " ", self.source_url).strip()
        if self.description is not None:
            self.description = re.sub(r"\s+", " ", self.description).strip()
        normalized_tags: list[str] = []
        for tag in self.tags:
            normalized = re.sub(r"\s+", " ", str(tag)).strip().lower()
            if normalized and normalized not in normalized_tags:
                normalized_tags.append(normalized[:40])
        self.tags = normalized_tags[:12]
        return self


class TraderIntelligenceAskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=800)

    @model_validator(mode="after")
    def normalize_question(self) -> "TraderIntelligenceAskRequest":
        self.question = re.sub(r"\s+", " ", self.question).strip()
        return self


class TraderIntelligenceAskResponse(BaseModel):
    profile_id: int
    question: str
    answer: str
    confidence: float = Field(ge=0, le=1)
    citations: list[TraderIntelligenceCitation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class TraderIntelligenceCompareRequest(BaseModel):
    profile_ids: list[int] = Field(min_length=2, max_length=5)

    @model_validator(mode="after")
    def normalize_profile_ids(self) -> "TraderIntelligenceCompareRequest":
        self.profile_ids = list(dict.fromkeys(int(item) for item in self.profile_ids))
        if len(self.profile_ids) < 2:
            raise ValueError("Select at least two expert profiles to compare")
        return self


class TraderIntelligenceCompareResponse(BaseModel):
    generated_at: str
    profile_ids: list[int]
    agreement_points: list[TraderIntelligenceClaim] = Field(default_factory=list)
    disagreement_points: list[TraderIntelligenceClaim] = Field(default_factory=list)
    unique_edges: list[TraderIntelligenceClaim] = Field(default_factory=list)
    opportunity_gaps: list[TraderIntelligenceClaim] = Field(default_factory=list)
    summary: str
    warnings: list[str] = Field(default_factory=list)


class SocialDiscoveryRunResult(BaseModel):
    discovered: int = Field(ge=0)
    updated: int = Field(ge=0)
    provider: str
    youtube_configured: bool
    traders: list[SocialTraderScorecard] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class SocialTraderAnalyzeRequest(BaseModel):
    query: str = Field(min_length=2, max_length=240)
    video_limit: int = Field(default=12, ge=3, le=30)

    @model_validator(mode="after")
    def normalize_query(self) -> "SocialTraderAnalyzeRequest":
        self.query = re.sub(r"\s+", " ", self.query).strip()
        return self


class SocialTraderFollowRequest(BaseModel):
    trader_id: int | None = Field(default=None, ge=1)
    trader_slug: str | None = Field(default=None, min_length=2, max_length=160)
    mode: SocialTradeMode = "signals"
    allocation_limit_usd: float = Field(default=500.0, ge=0, le=100000)
    max_position_pct: float = Field(default=0.12, ge=0.01, le=1)
    auto_rebalance: bool = True

    @model_validator(mode="after")
    def validate_trader_identity(self) -> "SocialTraderFollowRequest":
        if not self.trader_id and not self.trader_slug:
            raise ValueError("trader_id or trader_slug is required")
        if self.trader_slug is not None:
            self.trader_slug = self.trader_slug.strip().lower()
        return self


class SocialPortfolioDiversifyRequest(BaseModel):
    budget_usd: float = Field(default=1500.0, ge=0, le=100000)
    mode: SocialTradeMode = "managed_paper"
    trader_count: int = Field(default=3, ge=1, le=8)
    max_position_pct: float = Field(default=0.12, ge=0.01, le=1)


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
    social_trading: SocialTradingSnapshot
    latest_operation: OperationSnapshot | None = None
    auth_session: AuthSessionSnapshot
    user_profile: "UserProfile"
    notification_health: NotificationHealthSnapshot
    provider_status: ProviderStatus
    launch_readiness: LaunchReadinessSnapshot
    connector_control: ConnectorControlSnapshot
    infrastructure_readiness: InfrastructureReadinessSnapshot
    production_cutover: ProductionCutoverSnapshot
    operations_infrastructure: OperationsInfrastructureSnapshot
    feature_readiness: FeatureReadinessSnapshot
    business_model: BusinessModelSnapshot


class LandingSnapshot(BaseModel):
    summary: Summary
    assets: list[AssetSnapshot]
    leaderboard: list[BotSummary]
    recent_signals: list[SignalView]
    system_pulse: SystemPulseSnapshot
    macro_snapshot: MacroSnapshot
    provider_status: ProviderStatus
    business_model: BusinessModelSnapshot


class CycleResult(BaseModel):
    operation: OperationSnapshot | None
    leaderboard: list[BotSummary]
    recent_predictions: list[PredictionView]
    provider_status: ProviderStatus
    alert_inbox: AlertInbox
    notification_health: NotificationHealthSnapshot
    cycle_started: bool = True
    cycle_message: str | None = None


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


class UserWalletConnection(BaseModel):
    id: int
    address: str
    chain: str
    provider: str
    label: str | None = None
    is_active: bool = True
    created_at: str
    updated_at: str


class UserWalletConnectRequest(BaseModel):
    address: str = Field(min_length=4, max_length=128)
    chain: str = Field(min_length=2, max_length=32)
    provider: str = Field(default="walletconnect", min_length=2, max_length=64)
    label: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def normalize_fields(self) -> "UserWalletConnectRequest":
        self.address = re.sub(r"\s+", "", self.address).strip()
        self.chain = re.sub(r"[^a-z0-9_-]", "", self.chain.strip().lower())
        self.provider = re.sub(r"[^a-z0-9_-]", "", self.provider.strip().lower()) or "walletconnect"
        if self.label is not None:
            normalized_label = re.sub(r"\s+", " ", self.label).strip()
            self.label = normalized_label or None
        if not self.address:
            raise ValueError("address cannot be empty")
        if not self.chain:
            raise ValueError("chain cannot be empty")
        return self


class UserWalletConnectChallenge(BaseModel):
    challenge_id: int
    address: str
    chain: str
    provider: str
    label: str | None = None
    message: str
    nonce: str
    issued_at: str
    expires_at: str


class UserWalletVerifyRequest(BaseModel):
    challenge_id: int = Field(ge=1)
    signature: str = Field(min_length=10, max_length=512)

    @model_validator(mode="after")
    def normalize_signature(self) -> "UserWalletVerifyRequest":
        normalized = self.signature.strip()
        if not normalized:
            raise ValueError("signature cannot be empty")
        self.signature = normalized
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


class AuthOnboardingSnapshot(BaseModel):
    stage: AuthOnboardingStage = "identity"
    completed: bool = False
    risk_disclosure_accepted_at: str | None = None
    suitability_score: int | None = Field(default=None, ge=0, le=100)
    suitability_completed_at: str | None = None
    kyc_status: KycStatus = "not_started"
    kyc_completed_at: str | None = None
    preferred_language: UiLanguage = "en"
    preferred_theme: UiTheme = "day"
    preferred_workspace_mode: WorkspaceMode = "pro"
    timezone: str = "UTC"
    updated_at: str | None = None
    recommended_next_step: str | None = None


class UserSecuritySnapshot(BaseModel):
    mfa_enabled: bool = False
    mfa_enrolled_at: str | None = None
    mfa_pending_setup: bool = False
    last_login_at: str | None = None


class AuthRegisterRequest(BaseModel):
    display_name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=8, max_length=128)


class AuthLoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=8, max_length=128)
    otp_code: str | None = Field(default=None, min_length=6, max_length=8)

    @model_validator(mode="after")
    def normalize_otp_code(self) -> "AuthLoginRequest":
        if self.otp_code is not None:
            self.otp_code = "".join(ch for ch in self.otp_code if ch.isdigit())
            if self.otp_code and len(self.otp_code) != 6:
                raise ValueError("otp_code must be a 6-digit code")
            if not self.otp_code:
                self.otp_code = None
        return self


class AuthForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=5, max_length=320)


class AuthForgotPasswordResponse(BaseModel):
    message: str
    debug_reset_token: str | None = None


class AuthResetPasswordRequest(BaseModel):
    token: str = Field(min_length=16, max_length=256)
    new_password: str = Field(min_length=8, max_length=128)


class AuthOnboardingUpdateRequest(BaseModel):
    stage: AuthOnboardingStage | None = None
    completed: bool | None = None
    accept_risk_disclosure: bool | None = None
    suitability_score: int | None = Field(default=None, ge=0, le=100)
    kyc_status: KycStatus | None = None
    preferred_language: UiLanguage | None = None
    preferred_theme: UiTheme | None = None
    preferred_workspace_mode: WorkspaceMode | None = None
    timezone: str | None = Field(default=None, min_length=2, max_length=64)

    @model_validator(mode="after")
    def normalize_timezone(self) -> "AuthOnboardingUpdateRequest":
        if self.timezone is not None:
            normalized = re.sub(r"\s+", " ", self.timezone).strip()
            if not normalized:
                raise ValueError("timezone cannot be empty")
            self.timezone = normalized
        return self


class AuthMfaSetupResponse(BaseModel):
    enabled: bool
    pending_setup: bool
    secret: str | None = None
    otpauth_uri: str | None = None
    issuer: str | None = None
    account_label: str | None = None


class AuthMfaCodeRequest(BaseModel):
    code: str = Field(min_length=6, max_length=8)

    @model_validator(mode="after")
    def normalize_code(self) -> "AuthMfaCodeRequest":
        self.code = "".join(ch for ch in self.code if ch.isdigit())
        if len(self.code) != 6:
            raise ValueError("code must be a 6-digit value")
        return self


class AuthMfaStatusResponse(BaseModel):
    enabled: bool
    enrolled_at: str | None = None
    pending_setup: bool = False
    last_login_at: str | None = None


class AuthSessionSnapshot(BaseModel):
    authenticated: bool
    user: UserIdentity | None = None
    mfa_enabled: bool = False
    onboarding: AuthOnboardingSnapshot | None = None


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
    wallet_connections: list[UserWalletConnection] = Field(default_factory=list)
    unread_alert_count: int = Field(ge=0)
    security: UserSecuritySnapshot | None = None
    onboarding: AuthOnboardingSnapshot | None = None


class AuditLogEntry(BaseModel):
    id: int
    actor_user_slug: str | None = None
    action: str
    resource_type: str
    resource_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    before_state: dict[str, object] | None = None
    after_state: dict[str, object] | None = None
    created_at: str


class AuditLogEnvelope(BaseModel):
    audit_logs: list[AuditLogEntry]


class ProviderStatusEnvelope(BaseModel):
    provider_status: ProviderStatus


class SystemPulseEnvelope(BaseModel):
    system_pulse: SystemPulseSnapshot


class LaunchReadinessEnvelope(BaseModel):
    launch_readiness: LaunchReadinessSnapshot


class ConnectorControlEnvelope(BaseModel):
    connector_control: ConnectorControlSnapshot


class ConnectorDiagnosticEnvelope(BaseModel):
    connector_diagnostic: ConnectorDiagnosticResult


class ConnectorDiagnosticsEnvelope(BaseModel):
    connector_diagnostics: list[ConnectorDiagnosticResult] = Field(default_factory=list)


class InfrastructureReadinessEnvelope(BaseModel):
    infrastructure_readiness: InfrastructureReadinessSnapshot


class ProductionCutoverEnvelope(BaseModel):
    production_cutover: ProductionCutoverSnapshot


class OperationsInfrastructureEnvelope(BaseModel):
    operations_infrastructure: OperationsInfrastructureSnapshot


class FeatureReadinessEnvelope(BaseModel):
    feature_readiness: FeatureReadinessSnapshot


class BusinessModelEnvelope(BaseModel):
    business_model: BusinessModelSnapshot
