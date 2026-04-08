from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS bots (
    slug TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    archetype TEXT NOT NULL,
    focus TEXT NOT NULL,
    horizon_label TEXT NOT NULL,
    thesis TEXT NOT NULL,
    risk_style TEXT NOT NULL,
    asset_universe TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS market_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset TEXT NOT NULL,
    as_of TEXT NOT NULL,
    price REAL NOT NULL,
    change_24h REAL NOT NULL,
    volume_24h REAL NOT NULL,
    volatility REAL NOT NULL,
    trend_score REAL NOT NULL,
    signal_bias REAL NOT NULL,
    source TEXT NOT NULL,
    UNIQUE(asset, as_of)
);

CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id TEXT NOT NULL UNIQUE,
    asset TEXT NOT NULL,
    source TEXT NOT NULL,
    channel TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    sentiment REAL NOT NULL,
    relevance REAL NOT NULL,
    url TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    ingest_batch_id TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_slug TEXT NOT NULL,
    asset TEXT NOT NULL,
    direction TEXT NOT NULL,
    confidence REAL NOT NULL,
    horizon_days INTEGER NOT NULL,
    horizon_label TEXT NOT NULL,
    thesis TEXT NOT NULL,
    trigger_conditions TEXT NOT NULL,
    invalidation TEXT NOT NULL,
    source_signal_ids TEXT NOT NULL,
    published_at TEXT NOT NULL,
    status TEXT NOT NULL,
    start_price REAL,
    end_price REAL,
    market_return REAL,
    strategy_return REAL,
    max_adverse_excursion REAL,
    score REAL,
    calibration_score REAL,
    directional_success INTEGER,
    scoring_version TEXT,
    FOREIGN KEY(bot_slug) REFERENCES bots(slug)
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_type TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    ingested_signals INTEGER NOT NULL DEFAULT 0,
    generated_predictions INTEGER NOT NULL DEFAULT 0,
    scored_predictions INTEGER NOT NULL DEFAULT 0,
    message TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    slug TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    email TEXT,
    tier TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_follows (
    user_slug TEXT NOT NULL,
    bot_slug TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(user_slug, bot_slug),
    FOREIGN KEY(user_slug) REFERENCES users(slug) ON DELETE CASCADE,
    FOREIGN KEY(bot_slug) REFERENCES bots(slug) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS watchlist_items (
    user_slug TEXT NOT NULL,
    asset TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(user_slug, asset),
    FOREIGN KEY(user_slug) REFERENCES users(slug) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS alert_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_slug TEXT NOT NULL,
    bot_slug TEXT,
    asset TEXT,
    min_confidence REAL NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    FOREIGN KEY(user_slug) REFERENCES users(slug) ON DELETE CASCADE,
    FOREIGN KEY(bot_slug) REFERENCES bots(slug) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS alert_delivery_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_slug TEXT NOT NULL,
    rule_id INTEGER,
    prediction_id INTEGER NOT NULL,
    bot_slug TEXT NOT NULL,
    asset TEXT NOT NULL,
    direction TEXT NOT NULL,
    confidence REAL NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    channel TEXT NOT NULL,
    delivery_status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    read_at TEXT,
    FOREIGN KEY(user_slug) REFERENCES users(slug) ON DELETE CASCADE,
    FOREIGN KEY(rule_id) REFERENCES alert_rules(id) ON DELETE SET NULL,
    FOREIGN KEY(prediction_id) REFERENCES predictions(id) ON DELETE CASCADE,
    FOREIGN KEY(bot_slug) REFERENCES bots(slug) ON DELETE CASCADE,
    UNIQUE(user_slug, rule_id, prediction_id, channel)
);

CREATE INDEX IF NOT EXISTS idx_market_snapshots_asset_as_of ON market_snapshots(asset, as_of DESC);
CREATE INDEX IF NOT EXISTS idx_signals_observed_at ON signals(observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_predictions_published_at ON predictions(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_predictions_status ON predictions(status, published_at DESC);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started_at ON pipeline_runs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_alert_rules_user ON alert_rules(user_slug, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_alert_delivery_events_user ON alert_delivery_events(user_slug, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_alert_delivery_events_unread ON alert_delivery_events(user_slug, read_at, created_at DESC);
"""


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA_SQL)
