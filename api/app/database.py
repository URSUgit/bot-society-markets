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

Index("idx_market_snapshots_asset_as_of", market_snapshots_table.c.asset, market_snapshots_table.c.as_of.desc())
Index("idx_macro_snapshots_series_date", macro_snapshots_table.c.series_id, macro_snapshots_table.c.observation_date.desc())
Index("idx_signals_source_type_observed_at", signals_table.c.source_type, signals_table.c.observed_at.desc())
Index("idx_signals_observed_at", signals_table.c.observed_at.desc())
Index("idx_predictions_published_at", predictions_table.c.published_at.desc())
Index("idx_predictions_status", predictions_table.c.status, predictions_table.c.published_at.desc())
Index("idx_paper_positions_user_status_opened", paper_positions_table.c.user_slug, paper_positions_table.c.status, paper_positions_table.c.opened_at.desc())
Index("idx_pipeline_runs_started_at", pipeline_runs_table.c.started_at.desc())
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


def _sqlite_url_for_path(path: Path) -> str:
    return f"sqlite:///{path.resolve().as_posix()}"


class Database:
    def __init__(self, path: Path | None = None, url: str | None = None) -> None:
        self.path = path
        self.url = url or _sqlite_url_for_path(path or Path("api/data/bot_society_markets.db"))
        if self.url.startswith("sqlite:///"):
            sqlite_path = path or Path(self.url.removeprefix("sqlite:///"))
            sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine: Engine = create_engine(self.url, future=True)

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

    def dispose(self) -> None:
        self.engine.dispose()

    def upsert_insert(self, table: Table):
        if self.dialect_name == "postgresql":
            return postgresql_insert(table)
        return sqlite_insert(table)

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
