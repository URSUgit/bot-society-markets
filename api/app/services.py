from __future__ import annotations

from .mock_data import ALERTS, BOTS, PREDICTIONS, SUMMARY
from .models import Alert, Bot, Prediction, Summary


def list_bots() -> list[Bot]:
    return sorted(BOTS, key=lambda bot: bot.score, reverse=True)



def list_predictions() -> list[Prediction]:
    return PREDICTIONS



def list_alerts() -> list[Alert]:
    return ALERTS



def get_summary() -> Summary:
    return SUMMARY
