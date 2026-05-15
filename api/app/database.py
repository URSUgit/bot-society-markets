from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import (
    Boolean,
    Column,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
    inspect,
    text,
)
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Connection, Engine

metadata = MetaData()

bots_table = Table(
    "bots",
    metadata,
    Column("slug", String(120), primary_key=True),
    Column("name", String(255), nullable=False),
    Column("archetype", String(255), nullable=False),
    Column("focus", String(255), nullable=False),
    Column("horizon_label", String(255), nullable=False),
    Column("thesis", Text, nullable=False),
    Column("risk_style", String(255), nullable=False),
    Column("asset_universe", String(255), nullable=False),
    Column("is_active", Boolean, nullable=False, default=True, server_default=text("true")),
    Column("created_at", String(64), nullable=False),
)

market_snapshots_table = Table(
    "market_snapshots",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("asset", String(16), nullable=False),
    Column("as_of", String(64), nullable=False),
    Column("price", Float, nullable=False),
    Column("change_24h", Float, nullable=False),
    Column("volume_24h", Float, nullable=False),
    Column("volatility", Float, nullable=False),
    Column("trend_score", Float, nullable=False),
    Column("signal_bias", Float, nullable=False),
    Column("source", String(120), nullable=False),
    UniqueConstraint("asset", "as_of", name="uq_market_snapshots_asset_as_of"),
)

macro_snapshots_table = Table(
    "macro_snapshots",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("series_id", String(64), nullable=False),
    Column("label", String(255), nullable=False),
    Column("unit", String(64), nullable=False),
    Column("observation_date", String(64), nullable=False),
    Column("value", Float, nullable=False),
    Column("change_percent", Float, nullable=False),
    Column("signal_bias", Float, nullable=False),
    Column("regime_label", String(64), nullable=False),
    Column("source", String(120), nullable=False),
    UniqueConstraint("series_id", "observation_date", name="uq_macro_snapshots_series_date"),
)

signals_table = Table(
    "signals",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("external_id", String(255), nullable=False, unique=True),
    Column("asset", String(16), nullable=False),
    Column("source", String(255), nullable=False),
    Column("provider_name", String(120), nullable=False, default="seed-provider", server_default="seed-provider"),
    Column("source_type", String(32), nullable=False, default="news", server_default="news"),
    Column("author_handle", String(255)),
    Column("engagement_score", Float),
    Column("provider_trust_score", Float, nullable=False, default=0.7, server_default="0.7"),
    Column("freshness_score", Float, nullable=False, default=0.7, server_default="0.7"),
    Column("source_quality_score", Float, nullable=False, default=0.7, server_default="0.7"),
    Column("channel", String(64), nullable=False),
    Column("title", String(255), nullable=False),
    Column("summary", Text, nullable=False),
    Column("sentiment", Float, nullable=False),
    Column("relevance", Float, nullable=False),
    Column("url", Text, nullable=False),
    Column("observed_at", String(64), nullable=False),
    Column("ingest_batch_id", String(255), nullable=False),
)

predictions_table = Table(
    "predictions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("bot_slug", String(120), ForeignKey("bots.slug"), nullable=False),
    Column("asset", String(16), nullable=False),
    Column("direction", String(16), nullable=False),
    Column("confidence", Float, nullable=False),
    Column("horizon_days", Integer, nullable=False),
    Column("horizon_label", String(120), nullable=False),
    Column("thesis", Text, nullable=False),
    Column("trigger_conditions", Text, nullable=False),
    Column("invalidation", Text, nullable=False),
    Column("source_signal_ids", Text, nullable=False),
    Column("published_at", String(64), nullable=False),
    Column("status", String(16), nullable=False),
    Column("start_price", Float),
    Column("end_price", Float),
    Column("market_return", Float),
    Column("strategy_return", Float),
    Column("max_adverse_excursion", Float),
    Column("score", Float),
    Column("calibration_score", Float),
    Column("directional_success", Boolean),
    Column("scoring_version", String(32)),
)

paper_positions_table = Table(
    "paper_positions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_slug", String(120), ForeignKey("users.slug", ondelete="CASCADE"), nullable=False),
    Column("prediction_id", Integer, ForeignKey("predictions.id", ondelete="CASCADE"), nullable=False),
    Column("bot_slug", String(120), ForeignKey("bots.slug", ondelete="CASCADE"), nullable=False),
    Column("asset", String(16), nullable=False),
    Column("direction", String(16), nullable=False),
    Column("confidence", Float, nullable=False),
    Column("allocation_usd", Float, nullable=False),
    Column("quantity", Float, nullable=False),
    Column("entry_price", Float, nullable=False),
    Column("fees_paid", Float, nullable=False, default=0.0, server_default="0"),
    Column("slippage_bps", Float, nullable=False, default=0.0, server_default="0"),
    Column("status", String(16), nullable=False),
    Column("opened_at", String(64), nullable=False),
    Column("closed_at", String(64)),
    Column("exit_price", Float),
    Column("realized_pnl", Float),
    UniqueConstraint("user_slug", "prediction_id", name="uq_paper_positions_user_prediction"),
)

orders_table = Table(
    "orders",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_slug", String(120), ForeignKey("users.slug", ondelete="CASCADE"), nullable=False),
    Column("prediction_id", Integer, ForeignKey("predictions.id", ondelete="SET NULL")),
    Column("venue", String(64), nullable=False),
    Column("asset", String(16), nullable=False),
    Column("side", String(16), nullable=False),
    Column("order_type", String(16), nullable=False),
    Column("is_paper", Boolean, nullable=False, default=True, server_default=text("true")),
    Column("quantity", Float, nullable=False),
    Column("notional_usd", Float, nullable=False),
    Column("price", Float),
    Column("status", String(32), nullable=False),
    Column("filled_quantity", Float, nullable=False, default=0.0, server_default="0"),
    Column("avg_fill_price", Float),
    Column("fee", Float, nullable=False, default=0.0, server_default="0"),
    Column("fee_currency", String(16), nullable=False, default="USD", server_default="USD"),
    Column("exchange_order_id", String(255)),
    Column("rejection_reason", Text),
    Column("submitted_at", String(64), nullable=False),
    Column("filled_at", String(64)),
    Column("cancelled_at", String(64)),
    Column("metadata_json", Text),
)

pipeline_runs_table = Table(
    "pipeline_runs",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("cycle_type", String(64), nullable=False),
    Column("status", String(32), nullable=False),
    Column("started_at", String(64), nullable=False),
    Column("completed_at", String(64)),
    Column("ingested_signals", Integer, nullable=False, default=0, server_default="0"),
    Column("generated_predictions", Integer, nullable=False, default=0, server_default="0"),
    Column("scored_predictions", Integer, nullable=False, default=0, server_default="0"),
    Column("message", Text, nullable=False),
)

users_table = Table(
    "users",
    metadata,
    Column("slug", String(120), primary_key=True),
    Column("display_name", String(255), nullable=False),
    Column("email", String(320), nullable=False, unique=True),
    Column("tier", String(64), nullable=False),
    Column("created_at", String(64), nullable=False),
    Column("password_hash", String(512)),
    Column("is_active", Boolean, nullable=False, default=True, server_default=text("true")),
    Column("is_demo_user", Boolean, nullable=False, default=False, server_default=text("false")),
)

billing_customers_table = Table(
    "billing_customers",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_slug", String(120), ForeignKey("users.slug", ondelete="CASCADE"), nullable=False),
    Column("provider", String(32), nullable=False),
    Column("provider_customer_id", String(255), nullable=False, unique=True),
    Column("email", String(320)),
    Column("created_at", String(64), nullable=False),
    Column("updated_at", String(64), nullable=False),
    UniqueConstraint("user_slug", "provider", name="uq_billing_customers_user_provider"),
)

billing_subscriptions_table = Table(
    "billing_subscriptions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_slug", String(120), ForeignKey("users.slug", ondelete="CASCADE"), nullable=False),
    Column("provider", String(32), nullable=False),
    Column("provider_customer_id", String(255)),
    Column("provider_subscription_id", String(255), unique=True),
    Column("provider_checkout_session_id", String(255)),
    Column("status", String(64), nullable=False),
    Column("plan_key", String(32)),
    Column("price_id", String(255)),
    Column("current_period_end", String(64)),
    Column("cancel_at_period_end", Boolean, nullable=False, default=False, server_default=text("false")),
    Column("last_event_id", String(255)),
    Column("last_event_type", String(255)),
    Column("created_at", String(64), nullable=False),
    Column("updated_at", String(64), nullable=False),
    UniqueConstraint("user_slug", "provider", name="uq_billing_subscriptions_user_provider"),
)

billing_events_table = Table(
    "billing_events",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("provider", String(32), nullable=False),
    Column("provider_event_id", String(255), nullable=False, unique=True),
    Column("event_type", String(255), nullable=False),
    Column("user_slug", String(120), ForeignKey("users.slug", ondelete="SET NULL")),
    Column("provider_customer_id", String(255)),
    Column("provider_subscription_id", String(255)),
    Column("status", String(32), nullable=False),
    Column("payload_json", Text, nullable=False),
    Column("received_at", String(64), nullable=False),
    Column("processed_at", String(64)),
)

user_sessions_table = Table(
    "user_sessions",
    metadata,
    Column("token_hash", String(128), primary_key=True),
    Column("user_slug", String(120), ForeignKey("users.slug", ondelete="CASCADE"), nullable=False),
    Column("created_at", String(64), nullable=False),
    Column("expires_at", String(64), nullable=False),
    Column("last_seen_at", String(64), nullable=False),
)

user_follows_table = Table(
    "user_follows",
    metadata,
    Column("user_slug", String(120), ForeignKey("users.slug", ondelete="CASCADE"), nullable=False),
    Column("bot_slug", String(120), ForeignKey("bots.slug", ondelete="CASCADE"), nullable=False),
    Column("created_at", String(64), nullable=False),
    UniqueConstraint("user_slug", "bot_slug", name="uq_user_follows_user_bot"),
)

social_traders_table = Table(
    "social_traders",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("slug", String(160), nullable=False, unique=True),
    Column("display_name", String(255), nullable=False),
    Column("handle", String(255), nullable=False),
    Column("platform", String(32), nullable=False),
    Column("source_url", Text, nullable=False),
    Column("avatar_seed", String(255), nullable=False),
    Column("avatar_url", Text),
    Column("description", Text, nullable=False),
    Column("primary_assets_json", Text, nullable=False),
    Column("style_tags_json", Text, nullable=False),
    Column("signal_count", Integer, nullable=False, default=0, server_default="0"),
    Column("tracked_years", Float, nullable=False, default=0.0, server_default="0"),
    Column("win_rate", Float, nullable=False, default=0.0, server_default="0"),
    Column("average_roi", Float, nullable=False, default=0.0, server_default="0"),
    Column("roi_if_followed", Float, nullable=False, default=0.0, server_default="0"),
    Column("max_drawdown", Float, nullable=False, default=0.0, server_default="0"),
    Column("sharpe_like", Float, nullable=False, default=0.0, server_default="0"),
    Column("consistency_score", Float, nullable=False, default=0.0, server_default="0"),
    Column("influence_score", Float, nullable=False, default=0.0, server_default="0"),
    Column("recency_score", Float, nullable=False, default=0.0, server_default="0"),
    Column("composite_score", Float, nullable=False, default=0.0, server_default="0"),
    Column("last_signal_at", String(64)),
    Column("state", String(32), nullable=False, default="discovered", server_default="discovered"),
    Column("created_at", String(64), nullable=False),
    Column("updated_at", String(64), nullable=False),
)

social_trader_events_table = Table(
    "social_trader_events",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("trader_id", Integer, ForeignKey("social_traders.id", ondelete="CASCADE"), nullable=False),
    Column("external_id", String(255), nullable=False, unique=True),
    Column("platform", String(32), nullable=False),
    Column("title", String(255), nullable=False),
    Column("summary", Text, nullable=False),
    Column("url", Text, nullable=False),
    Column("asset", String(32), nullable=False),
    Column("direction", String(16), nullable=False),
    Column("confidence", Float, nullable=False),
    Column("engagement_score", Float, nullable=False),
    Column("observed_at", String(64), nullable=False),
    Column("derived_return", Float, nullable=False, default=0.0, server_default="0"),
    Column("created_at", String(64), nullable=False),
)

social_trader_allocations_table = Table(
    "social_trader_allocations",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_slug", String(120), ForeignKey("users.slug", ondelete="CASCADE"), nullable=False),
    Column("trader_id", Integer, ForeignKey("social_traders.id", ondelete="CASCADE"), nullable=False),
    Column("mode", String(32), nullable=False),
    Column("allocation_limit_usd", Float, nullable=False),
    Column("max_position_pct", Float, nullable=False),
    Column("auto_rebalance", Boolean, nullable=False, default=True, server_default=text("true")),
    Column("is_active", Boolean, nullable=False, default=True, server_default=text("true")),
    Column("created_at", String(64), nullable=False),
    Column("updated_at", String(64), nullable=False),
    UniqueConstraint("user_slug", "trader_id", name="uq_social_trader_allocations_user_trader"),
)

social_discovery_runs_table = Table(
    "social_discovery_runs",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("provider", String(120), nullable=False),
    Column("status", String(32), nullable=False),
    Column("youtube_configured", Boolean, nullable=False, default=False, server_default=text("false")),
    Column("discovered_count", Integer, nullable=False, default=0, server_default="0"),
    Column("updated_count", Integer, nullable=False, default=0, server_default="0"),
    Column("evidence_count", Integer, nullable=False, default=0, server_default="0"),
    Column("warnings_json", Text, nullable=False, default="[]", server_default="[]"),
    Column("started_at", String(64), nullable=False),
    Column("completed_at", String(64), nullable=False),
)

watchlist_items_table = Table(
    "watchlist_items",
    metadata,
    Column("user_slug", String(120), ForeignKey("users.slug", ondelete="CASCADE"), nullable=False),
    Column("asset", String(16), nullable=False),
    Column("created_at", String(64), nullable=False),
    UniqueConstraint("user_slug", "asset", name="uq_watchlist_items_user_asset"),
)

alert_rules_table = Table(
    "alert_rules",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_slug", String(120), ForeignKey("users.slug", ondelete="CASCADE"), nullable=False),
    Column("bot_slug", String(120), ForeignKey("bots.slug", ondelete="CASCADE")),
    Column("asset", String(16)),
    Column("min_confidence", Float, nullable=False),
    Column("is_active", Boolean, nullable=False, default=True, server_default=text("true")),
    Column("created_at", String(64), nullable=False),
)

notification_channels_table = Table(
    "notification_channels",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_slug", String(120), ForeignKey("users.slug", ondelete="CASCADE"), nullable=False),
    Column("channel_type", String(32), nullable=False),
    Column("target", Text, nullable=False),
    Column("secret", String(255)),
    Column("is_active", Boolean, nullable=False, default=True, server_default=text("true")),
    Column("created_at", String(64), nullable=False),
    Column("last_delivered_at", String(64)),
    Column("last_error", Text),
    UniqueConstraint("user_slug", "channel_type", "target", name="uq_notification_channels_user_type_target"),
)

alert_delivery_events_table = Table(
    "alert_delivery_events",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_slug", String(120), ForeignKey("users.slug", ondelete="CASCADE"), nullable=False),
    Column("rule_id", Integer, ForeignKey("alert_rules.id", ondelete="SET NULL")),
    Column("notification_channel_id", Integer, ForeignKey("notification_channels.id", ondelete="SET NULL")),
    Column("prediction_id", Integer, ForeignKey("predictions.id", ondelete="CASCADE"), nullable=False),
    Column("bot_slug", String(120), ForeignKey("bots.slug", ondelete="CASCADE"), nullable=False),
    Column("asset", String(16), nullable=False),
    Column("direction", String(16), nullable=False),
    Column("confidence", Float, nullable=False),
    Column("title", String(255), nullable=False),
    Column("message", Text, nullable=False),
    Column("channel", String(32), nullable=False),
    Column("channel_target", Text, nullable=False),
    Column("delivery_status", String(32), nullable=False),
    Column("attempt_count", Integer, nullable=False, default=1, server_default="1"),
    Column("last_attempt_at", String(64)),
    Column("next_attempt_at", String(64)),
    Column("error_detail", Text),
    Column("created_at", String(64), nullable=False),
    Column("read_at", String(64)),
    UniqueConstraint(
        "user_slug",
        "rule_id",
        "prediction_id",
        "channel",
        name="uq_alert_delivery_event_scope",
    ),
)

audit_logs_table = Table(
    "audit_logs",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("actor_user_slug", String(120), ForeignKey("users.slug", ondelete="SET NULL")),
    Column("action", String(120), nullable=False),
    Column("resource_type", String(120), nullable=False),
    Column("resource_id", String(255)),
    Column("ip_address", String(64)),
    Column("user_agent", Text),
    Column("before_state_json", Text),
    Column("after_state_json", Text),
    Column("created_at", String(64), nullable=False),
)

strategies_table = Table(
    "strategies",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_slug", String(120), ForeignKey("users.slug", ondelete="CASCADE"), nullable=False),
    Column("name", String(160), nullable=False),
    Column("description", Text),
    Column("config_json", Text, nullable=False),
    Column("is_active", Boolean, nullable=False, default=True, server_default=text("true")),
    Column("created_at", String(64), nullable=False),
    Column("updated_at", String(64), nullable=False),
)

backtest_runs_table = Table(
    "backtest_runs",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("strategy_id", Integer, ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False),
    Column("user_slug", String(120), ForeignKey("users.slug", ondelete="CASCADE"), nullable=False),
    Column("asset", String(16), nullable=False),
    Column("strategy_key", String(64), nullable=False),
    Column("lookback_years", Integer, nullable=False),
    Column("status", String(32), nullable=False, default="complete", server_default="complete"),
    Column("started_at", String(64), nullable=False),
    Column("completed_at", String(64)),
    Column("summary_json", Text, nullable=False),
    Column("result_json", Text),
    Column("error_message", Text),
)

Index("idx_market_snapshots_asset_as_of", market_snapshots_table.c.asset, market_snapshots_table.c.as_of.desc())
Index("idx_macro_snapshots_series_date", macro_snapshots_table.c.series_id, macro_snapshots_table.c.observation_date.desc())
Index("idx_signals_source_type_observed_at", signals_table.c.source_type, signals_table.c.observed_at.desc())
Index("idx_signals_observed_at", signals_table.c.observed_at.desc())
Index("idx_predictions_published_at", predictions_table.c.published_at.desc())
Index("idx_predictions_status", predictions_table.c.status, predictions_table.c.published_at.desc())
Index("idx_paper_positions_user_status_opened", paper_positions_table.c.user_slug, paper_positions_table.c.status, paper_positions_table.c.opened_at.desc())
Index("idx_orders_user_submitted", orders_table.c.user_slug, orders_table.c.submitted_at.desc())
Index("idx_orders_status_submitted", orders_table.c.status, orders_table.c.submitted_at.desc())
Index("idx_orders_asset_submitted", orders_table.c.asset, orders_table.c.submitted_at.desc())
Index("idx_social_traders_platform_score", social_traders_table.c.platform, social_traders_table.c.composite_score.desc())
Index("idx_social_traders_score", social_traders_table.c.composite_score.desc())
Index("idx_social_discovery_runs_started", social_discovery_runs_table.c.started_at.desc())
Index("idx_social_trader_events_trader_observed", social_trader_events_table.c.trader_id, social_trader_events_table.c.observed_at.desc())
Index("idx_social_trader_allocations_user", social_trader_allocations_table.c.user_slug, social_trader_allocations_table.c.updated_at.desc())
Index("idx_pipeline_runs_started_at", pipeline_runs_table.c.started_at.desc())
Index("idx_billing_customers_user_provider", billing_customers_table.c.user_slug, billing_customers_table.c.provider)
Index(
    "idx_billing_subscriptions_user_provider",
    billing_subscriptions_table.c.user_slug,
    billing_subscriptions_table.c.provider,
)
Index(
    "idx_billing_events_provider_status_received",
    billing_events_table.c.provider,
    billing_events_table.c.status,
    billing_events_table.c.received_at.desc(),
)
Index("idx_alert_rules_user", alert_rules_table.c.user_slug, alert_rules_table.c.created_at.desc())
Index("idx_notification_channels_user", notification_channels_table.c.user_slug, notification_channels_table.c.created_at.desc())
Index("idx_alert_delivery_events_user", alert_delivery_events_table.c.user_slug, alert_delivery_events_table.c.created_at.desc())
Index(
    "idx_alert_delivery_events_retry",
    alert_delivery_events_table.c.delivery_status,
    alert_delivery_events_table.c.next_attempt_at,
)
Index(
    "idx_alert_delivery_events_unread",
    alert_delivery_events_table.c.user_slug,
    alert_delivery_events_table.c.read_at,
    alert_delivery_events_table.c.created_at.desc(),
)
Index("idx_audit_logs_actor_created", audit_logs_table.c.actor_user_slug, audit_logs_table.c.created_at.desc())
Index("idx_audit_logs_resource_created", audit_logs_table.c.resource_type, audit_logs_table.c.resource_id, audit_logs_table.c.created_at.desc())
Index("idx_audit_logs_action_created", audit_logs_table.c.action, audit_logs_table.c.created_at.desc())
Index("idx_strategies_user_updated", strategies_table.c.user_slug, strategies_table.c.updated_at.desc())
Index("idx_backtest_runs_user_completed", backtest_runs_table.c.user_slug, backtest_runs_table.c.completed_at.desc())
Index("idx_backtest_runs_strategy_completed", backtest_runs_table.c.strategy_id, backtest_runs_table.c.completed_at.desc())


def _sqlite_url_for_path(path: Path) -> str:
    return f"sqlite:///{path.resolve().as_posix()}"


def normalize_database_url(url: str | None) -> str | None:
    """Prefer the installed psycopg v3 driver when users paste generic Postgres URLs."""
    if not url:
        return None
    normalized = url.strip()
    if normalized.startswith("postgresql://"):
        return "postgresql+psycopg://" + normalized.removeprefix("postgresql://")
    return normalized


def engine_options_for_url(url: str) -> dict[str, object]:
    options: dict[str, object] = {"future": True}
    if not url.startswith("sqlite:"):
        options.update(
            pool_pre_ping=True,
            pool_recycle=300,
            pool_timeout=20,
        )
    return options


class Database:
    def __init__(self, path: Path | None = None, url: str | None = None) -> None:
        self.path = path
        self.url = normalize_database_url(url) or _sqlite_url_for_path(path or Path("api/data/bot_society_markets.db"))
        if self.url.startswith("sqlite:///"):
            sqlite_path = path or Path(self.url.removeprefix("sqlite:///"))
            sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine: Engine = create_engine(self.url, **engine_options_for_url(self.url))

    @property
    def dialect_name(self) -> str:
        return self.engine.dialect.name

    @contextmanager
    def connect(self) -> Iterator[Connection]:
        with self.engine.begin() as connection:
            if self.dialect_name == "sqlite":
                connection.exec_driver_sql("PRAGMA foreign_keys = ON")
            yield connection

    def initialize(self) -> None:
        metadata.create_all(self.engine)
        self._migrate_existing_schema()
        metadata.create_all(self.engine)
        self._ensure_performance_indexes()
        self.sync_postgres_sequences()

    def dispose(self) -> None:
        self.engine.dispose()

    def upsert_insert(self, table: Table):
        if self.dialect_name == "postgresql":
            return postgresql_insert(table)
        return sqlite_insert(table)

    def sync_postgres_sequences(self) -> None:
        if self.dialect_name != "postgresql":
            return

        preparer = self.engine.dialect.identifier_preparer
        with self.connect() as connection:
            for table in metadata.sorted_tables:
                for column in table.primary_key.columns:
                    if not isinstance(column.type, Integer) or column.autoincrement is False:
                        continue

                    sequence_name = connection.execute(
                        text("SELECT pg_get_serial_sequence(:table_name, :column_name)"),
                        {"table_name": table.name, "column_name": column.name},
                    ).scalar()
                    if not sequence_name:
                        continue

                    quoted_table = preparer.quote(table.name)
                    quoted_column = preparer.quote(column.name)
                    next_value = int(
                        connection.exec_driver_sql(
                            f"SELECT COALESCE(MAX({quoted_column}), 0) + 1 FROM {quoted_table}"
                        ).scalar_one()
                    )
                    connection.execute(
                        text("SELECT setval(CAST(:sequence_name AS regclass), :next_value, false)"),
                        {"sequence_name": sequence_name, "next_value": next_value},
                    )

    def _migrate_existing_schema(self) -> None:
        inspector = inspect(self.engine)
        existing_tables = set(inspector.get_table_names())
        if not existing_tables:
            return

        true_literal = "TRUE" if self.dialect_name == "postgresql" else "1"
        false_literal = "FALSE" if self.dialect_name == "postgresql" else "0"

        column_statements = {
            "users": {
                "password_hash": "ALTER TABLE users ADD COLUMN password_hash TEXT",
                "is_active": f"ALTER TABLE users ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT {true_literal}",
                "is_demo_user": f"ALTER TABLE users ADD COLUMN is_demo_user BOOLEAN NOT NULL DEFAULT {false_literal}",
            },
            "signals": {
                "provider_name": "ALTER TABLE signals ADD COLUMN provider_name TEXT NOT NULL DEFAULT 'seed-provider'",
                "source_type": "ALTER TABLE signals ADD COLUMN source_type TEXT NOT NULL DEFAULT 'news'",
                "author_handle": "ALTER TABLE signals ADD COLUMN author_handle TEXT",
                "engagement_score": "ALTER TABLE signals ADD COLUMN engagement_score FLOAT",
                "provider_trust_score": "ALTER TABLE signals ADD COLUMN provider_trust_score FLOAT NOT NULL DEFAULT 0.7",
                "freshness_score": "ALTER TABLE signals ADD COLUMN freshness_score FLOAT NOT NULL DEFAULT 0.7",
                "source_quality_score": "ALTER TABLE signals ADD COLUMN source_quality_score FLOAT NOT NULL DEFAULT 0.7",
            },
            "alert_delivery_events": {
                "notification_channel_id": "ALTER TABLE alert_delivery_events ADD COLUMN notification_channel_id INTEGER",
                "channel_target": "ALTER TABLE alert_delivery_events ADD COLUMN channel_target TEXT NOT NULL DEFAULT 'in_app'",
                "attempt_count": "ALTER TABLE alert_delivery_events ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 1",
                "last_attempt_at": "ALTER TABLE alert_delivery_events ADD COLUMN last_attempt_at TEXT",
                "next_attempt_at": "ALTER TABLE alert_delivery_events ADD COLUMN next_attempt_at TEXT",
                "error_detail": "ALTER TABLE alert_delivery_events ADD COLUMN error_detail TEXT",
            },
        }

        with self.connect() as connection:
            for table_name, statements in column_statements.items():
                if table_name not in existing_tables:
                    continue
                existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
                for column_name, statement in statements.items():
                    if column_name not in existing_columns:
                        connection.exec_driver_sql(statement)

    def _ensure_performance_indexes(self) -> None:
        """Create indexes that may be absent on long-lived production databases."""
        statements = [
            "CREATE INDEX IF NOT EXISTS idx_market_snapshots_asset_as_of ON market_snapshots (asset, as_of DESC, id DESC)",
            "CREATE INDEX IF NOT EXISTS idx_macro_snapshots_series_date ON macro_snapshots (series_id, observation_date DESC, id DESC)",
            "CREATE INDEX IF NOT EXISTS idx_signals_observed_quality_id ON signals (observed_at DESC, source_quality_score DESC, id DESC)",
            "CREATE INDEX IF NOT EXISTS idx_signals_asset_observed_id ON signals (asset, observed_at DESC, id DESC)",
            "CREATE INDEX IF NOT EXISTS idx_predictions_published_id ON predictions (published_at DESC, id DESC)",
            "CREATE INDEX IF NOT EXISTS idx_predictions_status_published_id ON predictions (status, published_at DESC, id DESC)",
            "CREATE INDEX IF NOT EXISTS idx_paper_positions_user_opened_id ON paper_positions (user_slug, opened_at DESC, id DESC)",
            "CREATE INDEX IF NOT EXISTS idx_social_trader_events_trader_observed_id ON social_trader_events (trader_id, observed_at DESC, id DESC)",
            "CREATE INDEX IF NOT EXISTS idx_social_trader_allocations_user_updated ON social_trader_allocations (user_slug, is_active DESC, updated_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_alert_delivery_events_user_created_id ON alert_delivery_events (user_slug, created_at DESC, id DESC)",
            "CREATE INDEX IF NOT EXISTS idx_alert_delivery_events_user_read_created ON alert_delivery_events (user_slug, read_at, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_alert_delivery_events_user_status_created ON alert_delivery_events (user_slug, delivery_status, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_alert_delivery_events_user_channel_status ON alert_delivery_events (user_slug, notification_channel_id, delivery_status)",
        ]
        existing_tables = set(inspect(self.engine).get_table_names())
        with self.connect() as connection:
            for statement in statements:
                table_name = statement.split(" ON ", 1)[1].split(" ", 1)[0]
                if table_name in existing_tables:
                    connection.exec_driver_sql(statement)
