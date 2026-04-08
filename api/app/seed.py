from __future__ import annotations

from .repository import BotSocietyRepository
from .seed_data import (
    ALERT_RULE_SEEDS,
    BOT_SEEDS,
    FOLLOW_SEEDS,
    MARKET_SNAPSHOT_SEEDS,
    PREDICTION_SEEDS,
    SIGNAL_SEEDS,
    USER_SEEDS,
    WATCHLIST_SEEDS,
)



def ensure_demo_user_state(repository: BotSocietyRepository) -> None:
    repository.upsert_users(USER_SEEDS)
    repository.upsert_user_follows(FOLLOW_SEEDS)
    repository.upsert_watchlist_items(WATCHLIST_SEEDS)
    if not repository.list_alert_rules("demo-operator"):
        repository.upsert_alert_rules(ALERT_RULE_SEEDS)



def seed_demo_dataset(repository: BotSocietyRepository) -> bool:
    if repository.is_seeded():
        return False

    repository.upsert_bots(BOT_SEEDS)
    ensure_demo_user_state(repository)
    repository.upsert_market_snapshots(MARKET_SNAPSHOT_SEEDS)
    repository.upsert_signals(SIGNAL_SEEDS)

    seeded_predictions = [{**prediction, "start_price": None} for prediction in PREDICTION_SEEDS]
    repository.insert_predictions(seeded_predictions)
    return True
