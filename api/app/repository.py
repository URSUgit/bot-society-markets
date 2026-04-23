from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy import and_, delete, desc, func, select, update
from sqlalchemy.exc import IntegrityError

from .database import (
    Database,
    alert_delivery_events_table,
    alert_rules_table,
    billing_customers_table,
    billing_events_table,
    billing_subscriptions_table,
    bots_table,
    macro_snapshots_table,
    market_snapshots_table,
    notification_channels_table,
    paper_positions_table,
    pipeline_runs_table,
    predictions_table,
    signals_table,
    user_follows_table,
    user_sessions_table,
    users_table,
    watchlist_items_table,
)
from .providers import derive_signal_quality


class BotSocietyRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    @staticmethod
    def _rows(result) -> list[dict[str, Any]]:
        return [dict(row) for row in result.mappings().all()]

    @staticmethod
    def _row(result) -> dict[str, Any] | None:
        row = result.mappings().first()
        return dict(row) if row else None

    def is_seeded(self) -> bool:
        with self.database.connect() as connection:
            count = connection.execute(select(func.count()).select_from(bots_table)).scalar_one()
        return bool(count)

    def upsert_bots(self, bots: Iterable[dict[str, Any]]) -> None:
        bot_list = list(bots)
        if not bot_list:
            return
        stmt = self.database.upsert_insert(bots_table).values(bot_list)
        stmt = stmt.on_conflict_do_update(
            index_elements=[bots_table.c.slug],
            set_={
                "name": stmt.excluded.name,
                "archetype": stmt.excluded.archetype,
                "focus": stmt.excluded.focus,
                "horizon_label": stmt.excluded.horizon_label,
                "thesis": stmt.excluded.thesis,
                "risk_style": stmt.excluded.risk_style,
                "asset_universe": stmt.excluded.asset_universe,
                "is_active": stmt.excluded.is_active,
            },
        )
        with self.database.connect() as connection:
            connection.execute(stmt)

    def upsert_market_snapshots(self, snapshots: Iterable[dict[str, Any]]) -> None:
        snapshot_list = list(snapshots)
        if not snapshot_list:
            return
        stmt = self.database.upsert_insert(market_snapshots_table).values(snapshot_list)
        stmt = stmt.on_conflict_do_update(
            index_elements=[market_snapshots_table.c.asset, market_snapshots_table.c.as_of],
            set_={
                "price": stmt.excluded.price,
                "change_24h": stmt.excluded.change_24h,
                "volume_24h": stmt.excluded.volume_24h,
                "volatility": stmt.excluded.volatility,
                "trend_score": stmt.excluded.trend_score,
                "signal_bias": stmt.excluded.signal_bias,
                "source": stmt.excluded.source,
            },
        )
        with self.database.connect() as connection:
            connection.execute(stmt)

    def upsert_signals(self, signals: Iterable[dict[str, Any]]) -> int:
        signal_list = []
        for signal in signals:
            row = self._normalize_signal_row(signal)
            for key, value in derive_signal_quality(row).items():
                row.setdefault(key, value)
            signal_list.append(row)
        if not signal_list:
            return 0
        stmt = self.database.upsert_insert(signals_table).values(signal_list)
        stmt = stmt.on_conflict_do_nothing(index_elements=[signals_table.c.external_id])
        with self.database.connect() as connection:
            result = connection.execute(stmt)
            return max(0, result.rowcount or 0)

    def refresh_signal_quality_scores(self) -> int:
        stmt = select(signals_table)
        refreshed = 0
        with self.database.connect() as connection:
            rows = self._rows(connection.execute(stmt))
            for row in rows:
                normalized = self._normalize_signal_row(row)
                derived = derive_signal_quality(normalized)
                updates = {
                    **{
                        field: normalized[field]
                        for field in ("provider_name", "source_type")
                        if normalized.get(field) != row.get(field)
                    },
                    **{
                        key: value
                        for key, value in derived.items()
                        if abs(float(row.get(key) or 0.0) - value) >= 1e-9
                    },
                }
                if not updates:
                    continue
                connection.execute(
                    update(signals_table)
                    .where(signals_table.c.id == row["id"])
                    .values(**updates)
                )
                refreshed += 1
        return refreshed

    @staticmethod
    def _normalize_signal_row(signal: dict[str, Any]) -> dict[str, Any]:
        row = dict(signal)
        row.setdefault("provider_name", "seed-provider")
        channel = str(row.get("channel") or "news")
        source_type = str(row.get("source_type") or channel)
        if channel in {"social", "news", "macro"} and source_type != channel:
            source_type = channel
        row["source_type"] = source_type
        return row

    def insert_predictions(self, predictions: Iterable[dict[str, Any]]) -> int:
        prediction_list = list(predictions)
        if not prediction_list:
            return 0
        with self.database.connect() as connection:
            result = connection.execute(predictions_table.insert(), prediction_list)
            return max(0, result.rowcount or len(prediction_list))

    def list_bots(self) -> list[dict[str, Any]]:
        stmt = select(bots_table).where(bots_table.c.is_active.is_(True)).order_by(bots_table.c.name)
        with self.database.connect() as connection:
            return self._rows(connection.execute(stmt))

    def get_bot(self, slug: str) -> dict[str, Any] | None:
        stmt = select(bots_table).where(bots_table.c.slug == slug)
        with self.database.connect() as connection:
            return self._row(connection.execute(stmt))

    def list_latest_market_snapshots(self) -> list[dict[str, Any]]:
        latest = (
            select(
                market_snapshots_table.c.asset,
                func.max(market_snapshots_table.c.as_of).label("max_as_of"),
            )
            .group_by(market_snapshots_table.c.asset)
            .subquery()
        )
        stmt = (
            select(market_snapshots_table)
            .join(
                latest,
                and_(
                    latest.c.asset == market_snapshots_table.c.asset,
                    latest.c.max_as_of == market_snapshots_table.c.as_of,
                ),
            )
            .order_by(market_snapshots_table.c.asset)
        )
        with self.database.connect() as connection:
            return self._rows(connection.execute(stmt))

    def list_market_history(self, asset: str) -> list[dict[str, Any]]:
        stmt = select(market_snapshots_table).where(market_snapshots_table.c.asset == asset).order_by(market_snapshots_table.c.as_of)
        with self.database.connect() as connection:
            return self._rows(connection.execute(stmt))

    def upsert_macro_snapshots(self, snapshots: Iterable[dict[str, Any]]) -> None:
        snapshot_list = list(snapshots)
        if not snapshot_list:
            return
        stmt = self.database.upsert_insert(macro_snapshots_table).values(snapshot_list)
        stmt = stmt.on_conflict_do_update(
            index_elements=[macro_snapshots_table.c.series_id, macro_snapshots_table.c.observation_date],
            set_={
                "label": stmt.excluded.label,
                "unit": stmt.excluded.unit,
                "value": stmt.excluded.value,
                "change_percent": stmt.excluded.change_percent,
                "signal_bias": stmt.excluded.signal_bias,
                "regime_label": stmt.excluded.regime_label,
                "source": stmt.excluded.source,
            },
        )
        with self.database.connect() as connection:
            connection.execute(stmt)

    def list_latest_macro_snapshots(self) -> list[dict[str, Any]]:
        latest = (
            select(
                macro_snapshots_table.c.series_id,
                func.max(macro_snapshots_table.c.observation_date).label("max_observation_date"),
            )
            .group_by(macro_snapshots_table.c.series_id)
            .subquery()
        )
        stmt = (
            select(macro_snapshots_table)
            .join(
                latest,
                and_(
                    latest.c.series_id == macro_snapshots_table.c.series_id,
                    latest.c.max_observation_date == macro_snapshots_table.c.observation_date,
                ),
            )
            .order_by(macro_snapshots_table.c.series_id)
        )
        with self.database.connect() as connection:
            return self._rows(connection.execute(stmt))

    def list_macro_history(self, series_id: str) -> list[dict[str, Any]]:
        stmt = (
            select(macro_snapshots_table)
            .where(macro_snapshots_table.c.series_id == series_id)
            .order_by(macro_snapshots_table.c.observation_date)
        )
        with self.database.connect() as connection:
            return self._rows(connection.execute(stmt))

    def list_assets(self) -> list[str]:
        stmt = select(market_snapshots_table.c.asset).distinct().order_by(market_snapshots_table.c.asset)
        with self.database.connect() as connection:
            return list(connection.execute(stmt).scalars().all())

    def list_recent_signals(self, limit: int = 12, asset: str | None = None) -> list[dict[str, Any]]:
        stmt = select(signals_table)
        if asset:
            stmt = stmt.where(signals_table.c.asset == asset)
        stmt = stmt.order_by(
            desc(signals_table.c.observed_at),
            desc(signals_table.c.source_quality_score),
            desc(signals_table.c.id),
        ).limit(limit)
        with self.database.connect() as connection:
            return self._rows(connection.execute(stmt))

    def list_signals_by_ids(self, signal_ids: Iterable[int]) -> list[dict[str, Any]]:
        normalized_ids = [int(signal_id) for signal_id in signal_ids]
        if not normalized_ids:
            return []
        stmt = select(signals_table).where(signals_table.c.id.in_(normalized_ids)).order_by(desc(signals_table.c.observed_at))
        with self.database.connect() as connection:
            return self._rows(connection.execute(stmt))

    def count_signals_since(self, observed_at: str) -> int:
        stmt = select(func.count()).select_from(signals_table).where(signals_table.c.observed_at >= observed_at)
        with self.database.connect() as connection:
            return int(connection.execute(stmt).scalar_one())

    def list_predictions(
        self,
        *,
        status: str | None = None,
        bot_slug: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        stmt = (
            select(predictions_table, bots_table.c.name.label("bot_name"))
            .join(bots_table, bots_table.c.slug == predictions_table.c.bot_slug)
        )
        if status:
            stmt = stmt.where(predictions_table.c.status == status)
        if bot_slug:
            stmt = stmt.where(predictions_table.c.bot_slug == bot_slug)
        stmt = stmt.order_by(desc(predictions_table.c.published_at), desc(predictions_table.c.id)).limit(limit)
        with self.database.connect() as connection:
            return self._rows(connection.execute(stmt))

    def list_predictions_by_published_at(self, published_at: str, limit: int = 50) -> list[dict[str, Any]]:
        stmt = (
            select(predictions_table, bots_table.c.name.label("bot_name"))
            .join(bots_table, bots_table.c.slug == predictions_table.c.bot_slug)
            .where(predictions_table.c.published_at == published_at)
            .order_by(desc(predictions_table.c.confidence), desc(predictions_table.c.id))
            .limit(limit)
        )
        with self.database.connect() as connection:
            return self._rows(connection.execute(stmt))

    def list_prediction_rows_for_scoring(self) -> list[dict[str, Any]]:
        stmt = (
            select(predictions_table)
            .where(predictions_table.c.status == "pending")
            .order_by(predictions_table.c.published_at, predictions_table.c.id)
        )
        with self.database.connect() as connection:
            return self._rows(connection.execute(stmt))

    def latest_prediction_for_bot(self, bot_slug: str) -> dict[str, Any] | None:
        stmt = (
            select(predictions_table)
            .where(predictions_table.c.bot_slug == bot_slug)
            .order_by(desc(predictions_table.c.published_at), desc(predictions_table.c.id))
            .limit(1)
        )
        with self.database.connect() as connection:
            return self._row(connection.execute(stmt))

    def get_prediction(self, prediction_id: int) -> dict[str, Any] | None:
        stmt = (
            select(predictions_table, bots_table.c.name.label("bot_name"))
            .join(bots_table, bots_table.c.slug == predictions_table.c.bot_slug)
            .where(predictions_table.c.id == prediction_id)
        )
        with self.database.connect() as connection:
            return self._row(connection.execute(stmt))

    def bot_has_pending_prediction(self, bot_slug: str) -> bool:
        stmt = select(func.count()).select_from(predictions_table).where(
            and_(predictions_table.c.bot_slug == bot_slug, predictions_table.c.status == "pending")
        )
        with self.database.connect() as connection:
            return bool(connection.execute(stmt).scalar_one())

    def update_prediction_score(self, prediction_id: int, payload: dict[str, Any]) -> None:
        stmt = (
            update(predictions_table)
            .where(predictions_table.c.id == prediction_id)
            .values(**payload)
        )
        with self.database.connect() as connection:
            connection.execute(stmt)

    def insert_pipeline_run(self, payload: dict[str, Any]) -> int:
        stmt = pipeline_runs_table.insert().values(**payload)
        with self.database.connect() as connection:
            result = connection.execute(stmt)
            inserted = result.inserted_primary_key[0] if result.inserted_primary_key else None
            return int(inserted or 0)

    def create_paper_position(self, payload: dict[str, Any]) -> int:
        stmt = self.database.upsert_insert(paper_positions_table).values(**payload)
        stmt = stmt.on_conflict_do_nothing(index_elements=[paper_positions_table.c.user_slug, paper_positions_table.c.prediction_id])
        with self.database.connect() as connection:
            result = connection.execute(stmt)
            inserted = result.inserted_primary_key[0] if result.inserted_primary_key else None
            return int(inserted or 0)

    def list_paper_positions(self, user_slug: str, status: str | None = None) -> list[dict[str, Any]]:
        stmt = (
            select(paper_positions_table, bots_table.c.name.label("bot_name"))
            .join(bots_table, bots_table.c.slug == paper_positions_table.c.bot_slug)
            .where(paper_positions_table.c.user_slug == user_slug)
        )
        if status:
            stmt = stmt.where(paper_positions_table.c.status == status)
        stmt = stmt.order_by(desc(paper_positions_table.c.opened_at), desc(paper_positions_table.c.id))
        with self.database.connect() as connection:
            return self._rows(connection.execute(stmt))

    def get_paper_position_for_prediction(self, user_slug: str, prediction_id: int) -> dict[str, Any] | None:
        stmt = (
            select(paper_positions_table)
            .where(and_(paper_positions_table.c.user_slug == user_slug, paper_positions_table.c.prediction_id == prediction_id))
            .limit(1)
        )
        with self.database.connect() as connection:
            return self._row(connection.execute(stmt))

    def update_paper_position(self, position_id: int, payload: dict[str, Any]) -> None:
        stmt = update(paper_positions_table).where(paper_positions_table.c.id == position_id).values(**payload)
        with self.database.connect() as connection:
            connection.execute(stmt)

    def get_latest_pipeline_run(self) -> dict[str, Any] | None:
        stmt = select(pipeline_runs_table).order_by(desc(pipeline_runs_table.c.started_at), desc(pipeline_runs_table.c.id)).limit(1)
        with self.database.connect() as connection:
            return self._row(connection.execute(stmt))

    def count_pipeline_runs(self, cycle_type: str | None = None) -> int:
        stmt = select(func.count()).select_from(pipeline_runs_table)
        if cycle_type:
            stmt = stmt.where(pipeline_runs_table.c.cycle_type == cycle_type)
        with self.database.connect() as connection:
            return int(connection.execute(stmt).scalar_one())

    def upsert_users(self, users: Iterable[dict[str, Any]]) -> None:
        user_list = list(users)
        if not user_list:
            return
        stmt = self.database.upsert_insert(users_table).values(user_list)
        stmt = stmt.on_conflict_do_update(
            index_elements=[users_table.c.slug],
            set_={
                "display_name": stmt.excluded.display_name,
                "email": stmt.excluded.email,
                "tier": stmt.excluded.tier,
                "password_hash": stmt.excluded.password_hash,
                "is_active": stmt.excluded.is_active,
                "is_demo_user": stmt.excluded.is_demo_user,
            },
        )
        with self.database.connect() as connection:
            connection.execute(stmt)

    def create_user(self, payload: dict[str, Any]) -> None:
        with self.database.connect() as connection:
            connection.execute(users_table.insert().values(**payload))

    def get_user(self, slug: str) -> dict[str, Any] | None:
        stmt = select(users_table).where(users_table.c.slug == slug)
        with self.database.connect() as connection:
            return self._row(connection.execute(stmt))

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        stmt = select(users_table).where(func.lower(users_table.c.email) == email.lower())
        with self.database.connect() as connection:
            return self._row(connection.execute(stmt))

    def update_user(self, user_slug: str, payload: dict[str, Any]) -> None:
        stmt = update(users_table).where(users_table.c.slug == user_slug).values(**payload)
        with self.database.connect() as connection:
            connection.execute(stmt)

    def get_billing_customer(self, user_slug: str, provider: str = "stripe") -> dict[str, Any] | None:
        stmt = select(billing_customers_table).where(
            and_(
                billing_customers_table.c.user_slug == user_slug,
                billing_customers_table.c.provider == provider,
            )
        )
        with self.database.connect() as connection:
            return self._row(connection.execute(stmt))

    def get_billing_customer_by_provider_customer_id(
        self,
        provider_customer_id: str,
        provider: str = "stripe",
    ) -> dict[str, Any] | None:
        stmt = select(billing_customers_table).where(
            and_(
                billing_customers_table.c.provider == provider,
                billing_customers_table.c.provider_customer_id == provider_customer_id,
            )
        )
        with self.database.connect() as connection:
            return self._row(connection.execute(stmt))

    def upsert_billing_customer(self, payload: dict[str, Any]) -> None:
        stmt = self.database.upsert_insert(billing_customers_table).values(**payload)
        stmt = stmt.on_conflict_do_update(
            index_elements=[billing_customers_table.c.user_slug, billing_customers_table.c.provider],
            set_={
                "provider_customer_id": stmt.excluded.provider_customer_id,
                "email": stmt.excluded.email,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        with self.database.connect() as connection:
            connection.execute(stmt)

    def get_billing_subscription(self, user_slug: str, provider: str = "stripe") -> dict[str, Any] | None:
        stmt = select(billing_subscriptions_table).where(
            and_(
                billing_subscriptions_table.c.user_slug == user_slug,
                billing_subscriptions_table.c.provider == provider,
            )
        )
        with self.database.connect() as connection:
            return self._row(connection.execute(stmt))

    def get_billing_subscription_by_provider_customer_id(
        self,
        provider_customer_id: str,
        provider: str = "stripe",
    ) -> dict[str, Any] | None:
        stmt = select(billing_subscriptions_table).where(
            and_(
                billing_subscriptions_table.c.provider == provider,
                billing_subscriptions_table.c.provider_customer_id == provider_customer_id,
            )
        )
        with self.database.connect() as connection:
            return self._row(connection.execute(stmt))

    def get_billing_subscription_by_provider_subscription_id(
        self,
        provider_subscription_id: str,
        provider: str = "stripe",
    ) -> dict[str, Any] | None:
        stmt = select(billing_subscriptions_table).where(
            and_(
                billing_subscriptions_table.c.provider == provider,
                billing_subscriptions_table.c.provider_subscription_id == provider_subscription_id,
            )
        )
        with self.database.connect() as connection:
            return self._row(connection.execute(stmt))

    def upsert_billing_subscription(self, payload: dict[str, Any]) -> None:
        stmt = self.database.upsert_insert(billing_subscriptions_table).values(**payload)
        stmt = stmt.on_conflict_do_update(
            index_elements=[billing_subscriptions_table.c.user_slug, billing_subscriptions_table.c.provider],
            set_={
                "provider_customer_id": stmt.excluded.provider_customer_id,
                "provider_subscription_id": stmt.excluded.provider_subscription_id,
                "provider_checkout_session_id": stmt.excluded.provider_checkout_session_id,
                "status": stmt.excluded.status,
                "plan_key": stmt.excluded.plan_key,
                "price_id": stmt.excluded.price_id,
                "current_period_end": stmt.excluded.current_period_end,
                "cancel_at_period_end": stmt.excluded.cancel_at_period_end,
                "last_event_id": stmt.excluded.last_event_id,
                "last_event_type": stmt.excluded.last_event_type,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        with self.database.connect() as connection:
            connection.execute(stmt)

    def create_billing_event(self, payload: dict[str, Any]) -> bool:
        stmt = self.database.upsert_insert(billing_events_table).values(**payload)
        stmt = stmt.on_conflict_do_nothing(index_elements=[billing_events_table.c.provider_event_id])
        with self.database.connect() as connection:
            result = connection.execute(stmt)
            return bool(result.rowcount)

    def update_billing_event(self, provider_event_id: str, payload: dict[str, Any]) -> None:
        stmt = update(billing_events_table).where(
            billing_events_table.c.provider_event_id == provider_event_id
        ).values(**payload)
        with self.database.connect() as connection:
            connection.execute(stmt)

    def upsert_user_follows(self, follows: Iterable[dict[str, Any]]) -> None:
        follow_list = list(follows)
        if not follow_list:
            return
        stmt = self.database.upsert_insert(user_follows_table).values(follow_list)
        stmt = stmt.on_conflict_do_nothing(index_elements=[user_follows_table.c.user_slug, user_follows_table.c.bot_slug])
        with self.database.connect() as connection:
            connection.execute(stmt)

    def upsert_watchlist_items(self, items: Iterable[dict[str, Any]]) -> None:
        item_list = list(items)
        if not item_list:
            return
        stmt = self.database.upsert_insert(watchlist_items_table).values(item_list)
        stmt = stmt.on_conflict_do_nothing(index_elements=[watchlist_items_table.c.user_slug, watchlist_items_table.c.asset])
        with self.database.connect() as connection:
            connection.execute(stmt)

    def upsert_alert_rules(self, rules: Iterable[dict[str, Any]]) -> None:
        rule_list = list(rules)
        if not rule_list:
            return
        with self.database.connect() as connection:
            connection.execute(alert_rules_table.insert(), rule_list)

    def upsert_notification_channels(self, channels: Iterable[dict[str, Any]]) -> None:
        channel_list = list(channels)
        if not channel_list:
            return
        stmt = self.database.upsert_insert(notification_channels_table).values(channel_list)
        stmt = stmt.on_conflict_do_update(
            index_elements=[notification_channels_table.c.user_slug, notification_channels_table.c.channel_type, notification_channels_table.c.target],
            set_={
                "secret": stmt.excluded.secret,
                "is_active": stmt.excluded.is_active,
                "last_delivered_at": stmt.excluded.last_delivered_at,
                "last_error": stmt.excluded.last_error,
            },
        )
        with self.database.connect() as connection:
            connection.execute(stmt)

    def upsert_alert_delivery_events(self, events: Iterable[dict[str, Any]]) -> int:
        event_list = list(events)
        if not event_list:
            return 0
        stmt = self.database.upsert_insert(alert_delivery_events_table).values(event_list)
        stmt = stmt.on_conflict_do_nothing(
            index_elements=[
                alert_delivery_events_table.c.user_slug,
                alert_delivery_events_table.c.rule_id,
                alert_delivery_events_table.c.prediction_id,
                alert_delivery_events_table.c.channel,
            ]
        )
        with self.database.connect() as connection:
            result = connection.execute(stmt)
            return max(0, result.rowcount or 0)

    def list_user_follows(self, user_slug: str) -> list[dict[str, Any]]:
        stmt = (
            select(
                user_follows_table.c.user_slug,
                user_follows_table.c.bot_slug,
                user_follows_table.c.created_at,
                bots_table.c.name,
                bots_table.c.focus,
            )
            .join(bots_table, bots_table.c.slug == user_follows_table.c.bot_slug)
            .where(user_follows_table.c.user_slug == user_slug)
            .order_by(user_follows_table.c.created_at.asc())
        )
        with self.database.connect() as connection:
            return self._rows(connection.execute(stmt))

    def list_watchlist_items(self, user_slug: str) -> list[dict[str, Any]]:
        latest = (
            select(
                market_snapshots_table.c.asset,
                func.max(market_snapshots_table.c.as_of).label("max_as_of"),
            )
            .group_by(market_snapshots_table.c.asset)
            .subquery()
        )
        latest_snapshots = (
            select(market_snapshots_table)
            .join(
                latest,
                and_(
                    latest.c.asset == market_snapshots_table.c.asset,
                    latest.c.max_as_of == market_snapshots_table.c.as_of,
                ),
            )
            .subquery()
        )
        stmt = (
            select(
                watchlist_items_table.c.user_slug,
                watchlist_items_table.c.asset,
                watchlist_items_table.c.created_at,
                latest_snapshots.c.price.label("latest_price"),
                latest_snapshots.c.change_24h,
            )
            .outerjoin(latest_snapshots, latest_snapshots.c.asset == watchlist_items_table.c.asset)
            .where(watchlist_items_table.c.user_slug == user_slug)
            .order_by(watchlist_items_table.c.created_at.asc())
        )
        with self.database.connect() as connection:
            return self._rows(connection.execute(stmt))

    def list_alert_rules(self, user_slug: str) -> list[dict[str, Any]]:
        stmt = select(alert_rules_table).where(alert_rules_table.c.user_slug == user_slug).order_by(alert_rules_table.c.created_at.asc())
        with self.database.connect() as connection:
            return self._rows(connection.execute(stmt))

    def list_active_alert_rules(self, user_slug: str | None = None) -> list[dict[str, Any]]:
        stmt = select(alert_rules_table).where(alert_rules_table.c.is_active.is_(True))
        if user_slug:
            stmt = stmt.where(alert_rules_table.c.user_slug == user_slug)
        stmt = stmt.order_by(alert_rules_table.c.created_at.asc())
        with self.database.connect() as connection:
            return self._rows(connection.execute(stmt))

    def list_notification_channels(self, user_slug: str) -> list[dict[str, Any]]:
        stmt = (
            select(notification_channels_table)
            .where(notification_channels_table.c.user_slug == user_slug)
            .order_by(notification_channels_table.c.created_at.asc(), notification_channels_table.c.id.asc())
        )
        with self.database.connect() as connection:
            return self._rows(connection.execute(stmt))

    def list_active_notification_channels(self, user_slug: str) -> list[dict[str, Any]]:
        stmt = (
            select(notification_channels_table)
            .where(
                and_(
                    notification_channels_table.c.user_slug == user_slug,
                    notification_channels_table.c.is_active.is_(True),
                )
            )
            .order_by(notification_channels_table.c.created_at.asc(), notification_channels_table.c.id.asc())
        )
        with self.database.connect() as connection:
            return self._rows(connection.execute(stmt))

    def get_notification_channel(self, user_slug: str, channel_id: int) -> dict[str, Any] | None:
        stmt = select(notification_channels_table).where(
            and_(notification_channels_table.c.user_slug == user_slug, notification_channels_table.c.id == channel_id)
        )
        with self.database.connect() as connection:
            return self._row(connection.execute(stmt))

    def list_alert_deliveries(
        self,
        user_slug: str,
        limit: int | None = 10,
        unread_only: bool = False,
    ) -> list[dict[str, Any]]:
        stmt = select(alert_delivery_events_table).where(alert_delivery_events_table.c.user_slug == user_slug)
        if unread_only:
            stmt = stmt.where(alert_delivery_events_table.c.read_at.is_(None))
        stmt = stmt.order_by(desc(alert_delivery_events_table.c.created_at), desc(alert_delivery_events_table.c.id))
        if limit is not None:
            stmt = stmt.limit(limit)
        with self.database.connect() as connection:
            return self._rows(connection.execute(stmt))

    def count_unread_alert_deliveries(self, user_slug: str) -> int:
        stmt = select(func.count()).select_from(alert_delivery_events_table).where(
            and_(alert_delivery_events_table.c.user_slug == user_slug, alert_delivery_events_table.c.read_at.is_(None))
        )
        with self.database.connect() as connection:
            return int(connection.execute(stmt).scalar_one())

    def create_follow(self, user_slug: str, bot_slug: str, created_at: str) -> None:
        stmt = self.database.upsert_insert(user_follows_table).values(
            user_slug=user_slug,
            bot_slug=bot_slug,
            created_at=created_at,
        )
        stmt = stmt.on_conflict_do_nothing(index_elements=[user_follows_table.c.user_slug, user_follows_table.c.bot_slug])
        with self.database.connect() as connection:
            connection.execute(stmt)

    def delete_follow(self, user_slug: str, bot_slug: str) -> None:
        stmt = delete(user_follows_table).where(and_(user_follows_table.c.user_slug == user_slug, user_follows_table.c.bot_slug == bot_slug))
        with self.database.connect() as connection:
            connection.execute(stmt)

    def create_watchlist_item(self, user_slug: str, asset: str, created_at: str) -> None:
        stmt = self.database.upsert_insert(watchlist_items_table).values(user_slug=user_slug, asset=asset, created_at=created_at)
        stmt = stmt.on_conflict_do_nothing(index_elements=[watchlist_items_table.c.user_slug, watchlist_items_table.c.asset])
        with self.database.connect() as connection:
            connection.execute(stmt)

    def delete_watchlist_item(self, user_slug: str, asset: str) -> None:
        stmt = delete(watchlist_items_table).where(and_(watchlist_items_table.c.user_slug == user_slug, watchlist_items_table.c.asset == asset))
        with self.database.connect() as connection:
            connection.execute(stmt)

    def create_alert_rule(self, payload: dict[str, Any]) -> int:
        stmt = alert_rules_table.insert().values(**payload)
        with self.database.connect() as connection:
            result = connection.execute(stmt)
            inserted = result.inserted_primary_key[0] if result.inserted_primary_key else None
            return int(inserted or 0)

    def delete_alert_rule(self, user_slug: str, rule_id: int) -> None:
        stmt = delete(alert_rules_table).where(and_(alert_rules_table.c.user_slug == user_slug, alert_rules_table.c.id == rule_id))
        with self.database.connect() as connection:
            connection.execute(stmt)

    def create_notification_channel(self, payload: dict[str, Any]) -> int:
        stmt = notification_channels_table.insert().values(**payload)
        with self.database.connect() as connection:
            result = connection.execute(stmt)
            inserted = result.inserted_primary_key[0] if result.inserted_primary_key else None
            return int(inserted or 0)

    def delete_notification_channel(self, user_slug: str, channel_id: int) -> None:
        stmt = delete(notification_channels_table).where(
            and_(notification_channels_table.c.user_slug == user_slug, notification_channels_table.c.id == channel_id)
        )
        with self.database.connect() as connection:
            connection.execute(stmt)

    def update_notification_channel_delivery(
        self,
        user_slug: str,
        channel_id: int,
        *,
        delivered_at: str | None = None,
        error: str | None = None,
    ) -> None:
        values: dict[str, Any] = {"last_error": error}
        if delivered_at:
            values["last_delivered_at"] = delivered_at
        stmt = (
            update(notification_channels_table)
            .where(and_(notification_channels_table.c.user_slug == user_slug, notification_channels_table.c.id == channel_id))
            .values(**values)
        )
        with self.database.connect() as connection:
            connection.execute(stmt)

    def list_retryable_alert_deliveries(self, now: str, *, limit: int = 25) -> list[dict[str, Any]]:
        stmt = (
            select(
                alert_delivery_events_table,
                notification_channels_table.c.channel_type.label("notification_channel_type"),
                notification_channels_table.c.target.label("notification_channel_target"),
                notification_channels_table.c.secret.label("notification_channel_secret"),
                notification_channels_table.c.is_active.label("notification_channel_is_active"),
            )
            .join(
                notification_channels_table,
                notification_channels_table.c.id == alert_delivery_events_table.c.notification_channel_id,
            )
            .where(
                and_(
                    alert_delivery_events_table.c.notification_channel_id.is_not(None),
                    alert_delivery_events_table.c.delivery_status.in_(("retry_scheduled", "failed")),
                    alert_delivery_events_table.c.next_attempt_at.is_not(None),
                    alert_delivery_events_table.c.next_attempt_at <= now,
                    notification_channels_table.c.is_active.is_(True),
                )
            )
            .order_by(alert_delivery_events_table.c.next_attempt_at.asc(), alert_delivery_events_table.c.id.asc())
            .limit(limit)
        )
        with self.database.connect() as connection:
            return self._rows(connection.execute(stmt))

    def update_alert_delivery_event(self, alert_id: int, payload: dict[str, Any]) -> None:
        stmt = update(alert_delivery_events_table).where(alert_delivery_events_table.c.id == alert_id).values(**payload)
        with self.database.connect() as connection:
            connection.execute(stmt)

    def mark_alert_delivery_read(self, user_slug: str, alert_id: int, read_at: str) -> None:
        stmt = (
            update(alert_delivery_events_table)
            .where(and_(alert_delivery_events_table.c.user_slug == user_slug, alert_delivery_events_table.c.id == alert_id))
            .values(read_at=func.coalesce(alert_delivery_events_table.c.read_at, read_at))
        )
        with self.database.connect() as connection:
            connection.execute(stmt)

    def mark_all_alert_deliveries_read(self, user_slug: str, read_at: str) -> int:
        stmt = (
            update(alert_delivery_events_table)
            .where(and_(alert_delivery_events_table.c.user_slug == user_slug, alert_delivery_events_table.c.read_at.is_(None)))
            .values(read_at=read_at)
        )
        with self.database.connect() as connection:
            result = connection.execute(stmt)
            return max(0, result.rowcount or 0)

    def create_session(self, payload: dict[str, Any]) -> None:
        stmt = self.database.upsert_insert(user_sessions_table).values(**payload)
        stmt = stmt.on_conflict_do_update(
            index_elements=[user_sessions_table.c.token_hash],
            set_={
                "user_slug": stmt.excluded.user_slug,
                "created_at": stmt.excluded.created_at,
                "expires_at": stmt.excluded.expires_at,
                "last_seen_at": stmt.excluded.last_seen_at,
            },
        )
        with self.database.connect() as connection:
            connection.execute(stmt)

    def get_session(self, token_hash: str) -> dict[str, Any] | None:
        stmt = (
            select(
                user_sessions_table.c.token_hash,
                user_sessions_table.c.user_slug,
                user_sessions_table.c.created_at,
                user_sessions_table.c.expires_at,
                user_sessions_table.c.last_seen_at,
                users_table.c.display_name,
                users_table.c.email,
                users_table.c.tier,
                users_table.c.is_active,
                users_table.c.is_demo_user,
            )
            .join(users_table, users_table.c.slug == user_sessions_table.c.user_slug)
            .where(user_sessions_table.c.token_hash == token_hash)
        )
        with self.database.connect() as connection:
            return self._row(connection.execute(stmt))

    def touch_session(self, token_hash: str, *, last_seen_at: str, expires_at: str) -> None:
        stmt = (
            update(user_sessions_table)
            .where(user_sessions_table.c.token_hash == token_hash)
            .values(last_seen_at=last_seen_at, expires_at=expires_at)
        )
        with self.database.connect() as connection:
            connection.execute(stmt)

    def delete_session(self, token_hash: str) -> None:
        stmt = delete(user_sessions_table).where(user_sessions_table.c.token_hash == token_hash)
        with self.database.connect() as connection:
            connection.execute(stmt)

    def delete_expired_sessions(self, now: str) -> int:
        stmt = delete(user_sessions_table).where(user_sessions_table.c.expires_at < now)
        with self.database.connect() as connection:
            result = connection.execute(stmt)
            return max(0, result.rowcount or 0)
