from __future__ import annotations

from .repository import BotSocietyRepository
from .seed_data import BOT_SEEDS, MARKET_SNAPSHOT_SEEDS, PREDICTION_SEEDS, SIGNAL_SEEDS



def seed_demo_dataset(repository: BotSocietyRepository) -> bool:
    if repository.is_seeded():
        return False

    repository.upsert_bots(BOT_SEEDS)
    repository.upsert_market_snapshots(MARKET_SNAPSHOT_SEEDS)
    repository.upsert_signals(SIGNAL_SEEDS)

    seeded_predictions = []
    for prediction in PREDICTION_SEEDS:
        seeded_predictions.append({**prediction, "start_price": None})
    repository.insert_predictions(seeded_predictions)
    return True
