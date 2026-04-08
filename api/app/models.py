from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

Direction = Literal["bullish", "bearish", "neutral"]
PredictionStatus = Literal["pending", "scored"]
NotificationChannelType = Literal["email", "webhook"]


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


class SignalView(BaseModel):
    id: int
    asset: str
    source: str
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


class ProviderStatus(BaseModel):
    market_provider_mode: str
    market_provider_source: str
    signal_provider_mode: str
    signal_provider_source: str
    tracked_coin_ids: list[str]
    rss_feed_urls: list[str]
    market_fallback_active: bool = False
    signal_fallback_active: bool = False


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
    delivery_status: str
    created_at: str
    read_at: str | None = None
    is_read: bool = False


class AlertInbox(BaseModel):
    unread_count: int = Field(ge=0)
    alerts: list[AlertDelivery]


class DashboardSnapshot(BaseModel):
    summary: Summary
    assets: list[AssetSnapshot]
    leaderboard: list[BotSummary]
    recent_predictions: list[PredictionView]
    recent_signals: list[SignalView]
    latest_operation: OperationSnapshot | None = None
    user_profile: "UserProfile"
    provider_status: ProviderStatus


class LandingSnapshot(BaseModel):
    summary: Summary
    assets: list[AssetSnapshot]
    leaderboard: list[BotSummary]
    recent_signals: list[SignalView]
    provider_status: ProviderStatus


class CycleResult(BaseModel):
    operation: OperationSnapshot | None
    leaderboard: list[BotSummary]
    recent_predictions: list[PredictionView]
    provider_status: ProviderStatus
    alert_inbox: AlertInbox


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
    follows: list[FollowedBot]
    watchlist: list[WatchlistItem]
    alert_rules: list[AlertRule]
    recent_alerts: list[AlertDelivery]
    notification_channels: list[NotificationChannel] = Field(default_factory=list)
    unread_alert_count: int = Field(ge=0)


class ProviderStatusEnvelope(BaseModel):
    provider_status: ProviderStatus
