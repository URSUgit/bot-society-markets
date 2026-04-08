from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .database import Database


class BotSocietyRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def is_seeded(self) -> bool:
        with self.database.connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM bots").fetchone()
        return bool(row["count"])

    def upsert_bots(self, bots: Iterable[dict[str, Any]]) -> None:
        query = """
        INSERT INTO bots (
            slug, name, archetype, focus, horizon_label, thesis, risk_style, asset_universe, created_at
        ) VALUES (
            :slug, :name, :archetype, :focus, :horizon_label, :thesis, :risk_style, :asset_universe, :created_at
        )
        ON CONFLICT(slug) DO UPDATE SET
            name = excluded.name,
            archetype = excluded.archetype,
            focus = excluded.focus,
            horizon_label = excluded.horizon_label,
            thesis = excluded.thesis,
            risk_style = excluded.risk_style,
            asset_universe = excluded.asset_universe
        """
        with self.database.connect() as connection:
            connection.executemany(query, list(bots))

    def upsert_market_snapshots(self, snapshots: Iterable[dict[str, Any]]) -> None:
        query = """
        INSERT INTO market_snapshots (
            asset, as_of, price, change_24h, volume_24h, volatility, trend_score, signal_bias, source
        ) VALUES (
            :asset, :as_of, :price, :change_24h, :volume_24h, :volatility, :trend_score, :signal_bias, :source
        )
        ON CONFLICT(asset, as_of) DO UPDATE SET
            price = excluded.price,
            change_24h = excluded.change_24h,
            volume_24h = excluded.volume_24h,
            volatility = excluded.volatility,
            trend_score = excluded.trend_score,
            signal_bias = excluded.signal_bias,
            source = excluded.source
        """
        with self.database.connect() as connection:
            connection.executemany(query, list(snapshots))

    def upsert_signals(self, signals: Iterable[dict[str, Any]]) -> int:
        query = """
        INSERT INTO signals (
            external_id, asset, source, channel, title, summary, sentiment, relevance, url, observed_at, ingest_batch_id
        ) VALUES (
            :external_id, :asset, :source, :channel, :title, :summary, :sentiment, :relevance, :url, :observed_at, :ingest_batch_id
        )
        ON CONFLICT(external_id) DO NOTHING
        """
        signal_list = list(signals)
        if not signal_list:
            return 0
        with self.database.connect() as connection:
            before = connection.total_changes
            connection.executemany(query, signal_list)
            return connection.total_changes - before

    def insert_predictions(self, predictions: Iterable[dict[str, Any]]) -> int:
        query = """
        INSERT INTO predictions (
            bot_slug, asset, direction, confidence, horizon_days, horizon_label, thesis,
            trigger_conditions, invalidation, source_signal_ids, published_at, status, start_price
        ) VALUES (
            :bot_slug, :asset, :direction, :confidence, :horizon_days, :horizon_label, :thesis,
            :trigger_conditions, :invalidation, :source_signal_ids, :published_at, :status, :start_price
        )
        """
        prediction_list = list(predictions)
        if not prediction_list:
            return 0
        with self.database.connect() as connection:
            before = connection.total_changes
            connection.executemany(query, prediction_list)
            return connection.total_changes - before

    def list_bots(self) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute("SELECT * FROM bots WHERE is_active = 1 ORDER BY name").fetchall()
        return [dict(row) for row in rows]

    def get_bot(self, slug: str) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM bots WHERE slug = ?", (slug,)).fetchone()
        return dict(row) if row else None

    def list_latest_market_snapshots(self) -> list[dict[str, Any]]:
        query = """
        SELECT ms.*
        FROM market_snapshots ms
        JOIN (
            SELECT asset, MAX(as_of) AS max_as_of
            FROM market_snapshots
            GROUP BY asset
        ) latest
            ON latest.asset = ms.asset AND latest.max_as_of = ms.as_of
        ORDER BY ms.asset
        """
        with self.database.connect() as connection:
            rows = connection.execute(query).fetchall()
        return [dict(row) for row in rows]

    def list_market_history(self, asset: str) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM market_snapshots WHERE asset = ? ORDER BY as_of",
                (asset,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_assets(self) -> list[str]:
        with self.database.connect() as connection:
            rows = connection.execute("SELECT DISTINCT asset FROM market_snapshots ORDER BY asset").fetchall()
        return [row["asset"] for row in rows]

    def list_recent_signals(self, limit: int = 12, asset: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM signals"
        params: list[Any] = []
        if asset:
            query += " WHERE asset = ?"
            params.append(asset)
        query += " ORDER BY observed_at DESC LIMIT ?"
        params.append(limit)
        with self.database.connect() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def count_signals_since(self, observed_at: str) -> int:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM signals WHERE observed_at >= ?",
                (observed_at,),
            ).fetchone()
        return int(row["count"])

    def list_predictions(
        self,
        *,
        status: str | None = None,
        bot_slug: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        query = """
        SELECT predictions.*, bots.name AS bot_name
        FROM predictions
        JOIN bots ON bots.slug = predictions.bot_slug
        """
        conditions: list[str] = []
        params: list[Any] = []
        if status:
            conditions.append("predictions.status = ?")
            params.append(status)
        if bot_slug:
            conditions.append("predictions.bot_slug = ?")
            params.append(bot_slug)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY predictions.published_at DESC, predictions.id DESC LIMIT ?"
        params.append(limit)
        with self.database.connect() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def list_predictions_by_published_at(self, published_at: str, limit: int = 50) -> list[dict[str, Any]]:
        query = """
        SELECT predictions.*, bots.name AS bot_name
        FROM predictions
        JOIN bots ON bots.slug = predictions.bot_slug
        WHERE predictions.published_at = ?
        ORDER BY predictions.confidence DESC, predictions.id DESC
        LIMIT ?
        """
        with self.database.connect() as connection:
            rows = connection.execute(query, (published_at, limit)).fetchall()
        return [dict(row) for row in rows]

    def list_prediction_rows_for_scoring(self) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM predictions WHERE status = 'pending' ORDER BY published_at, id"
            ).fetchall()
        return [dict(row) for row in rows]

    def latest_prediction_for_bot(self, bot_slug: str) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM predictions WHERE bot_slug = ? ORDER BY published_at DESC, id DESC LIMIT 1",
                (bot_slug,),
            ).fetchone()
        return dict(row) if row else None

    def bot_has_pending_prediction(self, bot_slug: str) -> bool:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM predictions WHERE bot_slug = ? AND status = 'pending'",
                (bot_slug,),
            ).fetchone()
        return bool(row["count"])

    def update_prediction_score(self, prediction_id: int, payload: dict[str, Any]) -> None:
        payload = {**payload, "id": prediction_id}
        query = """
        UPDATE predictions
        SET status = :status,
            start_price = :start_price,
            end_price = :end_price,
            market_return = :market_return,
            strategy_return = :strategy_return,
            max_adverse_excursion = :max_adverse_excursion,
            score = :score,
            calibration_score = :calibration_score,
            directional_success = :directional_success,
            scoring_version = :scoring_version
        WHERE id = :id
        """
        with self.database.connect() as connection:
            connection.execute(query, payload)

    def insert_pipeline_run(self, payload: dict[str, Any]) -> int:
        query = """
        INSERT INTO pipeline_runs (
            cycle_type, status, started_at, completed_at,
            ingested_signals, generated_predictions, scored_predictions, message
        ) VALUES (
            :cycle_type, :status, :started_at, :completed_at,
            :ingested_signals, :generated_predictions, :scored_predictions, :message
        )
        """
        with self.database.connect() as connection:
            cursor = connection.execute(query, payload)
            return int(cursor.lastrowid)

    def get_latest_pipeline_run(self) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM pipeline_runs ORDER BY started_at DESC, id DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row else None

    def count_pipeline_runs(self, cycle_type: str | None = None) -> int:
        with self.database.connect() as connection:
            if cycle_type:
                row = connection.execute(
                    "SELECT COUNT(*) AS count FROM pipeline_runs WHERE cycle_type = ?",
                    (cycle_type,),
                ).fetchone()
            else:
                row = connection.execute("SELECT COUNT(*) AS count FROM pipeline_runs").fetchone()
        return int(row["count"])

    def upsert_users(self, users: Iterable[dict[str, Any]]) -> None:
        query = """
        INSERT INTO users (slug, display_name, email, tier, created_at)
        VALUES (:slug, :display_name, :email, :tier, :created_at)
        ON CONFLICT(slug) DO UPDATE SET
            display_name = excluded.display_name,
            email = excluded.email,
            tier = excluded.tier
        """
        with self.database.connect() as connection:
            connection.executemany(query, list(users))

    def upsert_user_follows(self, follows: Iterable[dict[str, Any]]) -> None:
        query = """
        INSERT INTO user_follows (user_slug, bot_slug, created_at)
        VALUES (:user_slug, :bot_slug, :created_at)
        ON CONFLICT(user_slug, bot_slug) DO NOTHING
        """
        with self.database.connect() as connection:
            connection.executemany(query, list(follows))

    def upsert_watchlist_items(self, items: Iterable[dict[str, Any]]) -> None:
        query = """
        INSERT INTO watchlist_items (user_slug, asset, created_at)
        VALUES (:user_slug, :asset, :created_at)
        ON CONFLICT(user_slug, asset) DO NOTHING
        """
        with self.database.connect() as connection:
            connection.executemany(query, list(items))

    def upsert_alert_rules(self, rules: Iterable[dict[str, Any]]) -> None:
        query = """
        INSERT INTO alert_rules (user_slug, bot_slug, asset, min_confidence, is_active, created_at)
        VALUES (:user_slug, :bot_slug, :asset, :min_confidence, :is_active, :created_at)
        """
        with self.database.connect() as connection:
            connection.executemany(query, list(rules))

    def upsert_alert_delivery_events(self, events: Iterable[dict[str, Any]]) -> int:
        query = """
        INSERT INTO alert_delivery_events (
            user_slug, rule_id, prediction_id, bot_slug, asset, direction, confidence,
            title, message, channel, delivery_status, created_at, read_at
        ) VALUES (
            :user_slug, :rule_id, :prediction_id, :bot_slug, :asset, :direction, :confidence,
            :title, :message, :channel, :delivery_status, :created_at, :read_at
        )
        ON CONFLICT(user_slug, rule_id, prediction_id, channel) DO NOTHING
        """
        event_list = list(events)
        if not event_list:
            return 0
        with self.database.connect() as connection:
            before = connection.total_changes
            connection.executemany(query, event_list)
            return connection.total_changes - before

    def get_user(self, slug: str) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM users WHERE slug = ?", (slug,)).fetchone()
        return dict(row) if row else None

    def list_user_follows(self, user_slug: str) -> list[dict[str, Any]]:
        query = """
        SELECT user_follows.user_slug, user_follows.bot_slug, user_follows.created_at, bots.name, bots.slug, bots.focus
        FROM user_follows
        JOIN bots ON bots.slug = user_follows.bot_slug
        WHERE user_follows.user_slug = ?
        ORDER BY user_follows.created_at ASC
        """
        with self.database.connect() as connection:
            rows = connection.execute(query, (user_slug,)).fetchall()
        return [dict(row) for row in rows]

    def list_watchlist_items(self, user_slug: str) -> list[dict[str, Any]]:
        query = """
        SELECT watchlist_items.user_slug, watchlist_items.asset, watchlist_items.created_at,
               market_snapshots.price AS latest_price, market_snapshots.change_24h
        FROM watchlist_items
        LEFT JOIN (
            SELECT ms.*
            FROM market_snapshots ms
            JOIN (
                SELECT asset, MAX(as_of) AS max_as_of
                FROM market_snapshots
                GROUP BY asset
            ) latest
                ON latest.asset = ms.asset AND latest.max_as_of = ms.as_of
        ) market_snapshots ON market_snapshots.asset = watchlist_items.asset
        WHERE watchlist_items.user_slug = ?
        ORDER BY watchlist_items.created_at ASC
        """
        with self.database.connect() as connection:
            rows = connection.execute(query, (user_slug,)).fetchall()
        return [dict(row) for row in rows]

    def list_alert_rules(self, user_slug: str) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM alert_rules WHERE user_slug = ? ORDER BY created_at ASC",
                (user_slug,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_active_alert_rules(self, user_slug: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM alert_rules WHERE is_active = 1"
        params: list[Any] = []
        if user_slug:
            query += " AND user_slug = ?"
            params.append(user_slug)
        query += " ORDER BY created_at ASC"
        with self.database.connect() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def list_alert_deliveries(self, user_slug: str, limit: int = 10, unread_only: bool = False) -> list[dict[str, Any]]:
        query = "SELECT * FROM alert_delivery_events WHERE user_slug = ?"
        params: list[Any] = [user_slug]
        if unread_only:
            query += " AND read_at IS NULL"
        query += " ORDER BY created_at DESC, id DESC LIMIT ?"
        params.append(limit)
        with self.database.connect() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def count_unread_alert_deliveries(self, user_slug: str) -> int:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM alert_delivery_events WHERE user_slug = ? AND read_at IS NULL",
                (user_slug,),
            ).fetchone()
        return int(row["count"])

    def create_follow(self, user_slug: str, bot_slug: str, created_at: str) -> None:
        with self.database.connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO user_follows (user_slug, bot_slug, created_at) VALUES (?, ?, ?)",
                (user_slug, bot_slug, created_at),
            )

    def delete_follow(self, user_slug: str, bot_slug: str) -> None:
        with self.database.connect() as connection:
            connection.execute(
                "DELETE FROM user_follows WHERE user_slug = ? AND bot_slug = ?",
                (user_slug, bot_slug),
            )

    def create_watchlist_item(self, user_slug: str, asset: str, created_at: str) -> None:
        with self.database.connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO watchlist_items (user_slug, asset, created_at) VALUES (?, ?, ?)",
                (user_slug, asset, created_at),
            )

    def delete_watchlist_item(self, user_slug: str, asset: str) -> None:
        with self.database.connect() as connection:
            connection.execute(
                "DELETE FROM watchlist_items WHERE user_slug = ? AND asset = ?",
                (user_slug, asset),
            )

    def create_alert_rule(self, payload: dict[str, Any]) -> int:
        query = """
        INSERT INTO alert_rules (user_slug, bot_slug, asset, min_confidence, is_active, created_at)
        VALUES (:user_slug, :bot_slug, :asset, :min_confidence, :is_active, :created_at)
        """
        with self.database.connect() as connection:
            cursor = connection.execute(query, payload)
            return int(cursor.lastrowid)

    def delete_alert_rule(self, user_slug: str, rule_id: int) -> None:
        with self.database.connect() as connection:
            connection.execute(
                "DELETE FROM alert_rules WHERE user_slug = ? AND id = ?",
                (user_slug, rule_id),
            )

    def mark_alert_delivery_read(self, user_slug: str, alert_id: int, read_at: str) -> None:
        with self.database.connect() as connection:
            connection.execute(
                "UPDATE alert_delivery_events SET read_at = COALESCE(read_at, ?) WHERE user_slug = ? AND id = ?",
                (read_at, user_slug, alert_id),
            )

    def mark_all_alert_deliveries_read(self, user_slug: str, read_at: str) -> int:
        with self.database.connect() as connection:
            before = connection.total_changes
            connection.execute(
                "UPDATE alert_delivery_events SET read_at = ? WHERE user_slug = ? AND read_at IS NULL",
                (read_at, user_slug),
            )
            return connection.total_changes - before
