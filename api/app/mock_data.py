from __future__ import annotations

from .models import Alert, Bot, Prediction, Summary

BOTS: list[Bot] = [
    Bot(
        slug="macro-narrative",
        name="Macro Narrative Bot",
        archetype="Macro and flows",
        focus="BTC, ETH",
        horizon="3 to 30 days",
        thesis="Translates macro releases, policy signals, and ETF flows into medium-term market calls.",
        score=81.4,
        hit_rate=0.67,
        calibration=0.89,
        predictions=146,
    ),
    Bot(
        slug="social-momentum",
        name="Social Momentum Bot",
        archetype="Sentiment acceleration",
        focus="BTC, ETH, SOL",
        horizon="1 to 3 days",
        thesis="Finds liquid assets where public attention, engagement velocity, and price momentum align.",
        score=78.9,
        hit_rate=0.64,
        calibration=0.84,
        predictions=211,
    ),
    Bot(
        slug="breakout",
        name="Breakout Bot",
        archetype="Technical structure",
        focus="Liquid majors",
        horizon="Intraday to 3 days",
        thesis="Publishes when price structure, volume, and volatility confirm breakout conditions.",
        score=74.2,
        hit_rate=0.61,
        calibration=0.82,
        predictions=198,
    ),
    Bot(
        slug="contrarian",
        name="Contrarian Bot",
        archetype="Mean reversion",
        focus="Crowded narratives",
        horizon="1 to 7 days",
        thesis="Targets sentiment exhaustion and overextended positioning after fast narrative-driven moves.",
        score=72.6,
        hit_rate=0.58,
        calibration=0.87,
        predictions=171,
    ),
    Bot(
        slug="risk-sentinel",
        name="Risk Sentinel",
        archetype="Cross-market risk",
        focus="Cross-market risk",
        horizon="1 to 14 days",
        thesis="Flags fragility, volatility expansion, and deteriorating asymmetry before it spreads across the roster.",
        score=71.1,
        hit_rate=0.56,
        calibration=0.91,
        predictions=132,
    ),
    Bot(
        slug="news-reaction",
        name="News Reaction Bot",
        archetype="Event response",
        focus="BTC, ETH, top news-sensitive assets",
        horizon="Intraday to 1 day",
        thesis="Measures how quickly the market reprices after new headlines and differentiates signal from narrative lag.",
        score=69.8,
        hit_rate=0.55,
        calibration=0.8,
        predictions=184,
    ),
]

PREDICTIONS: list[Prediction] = [
    Prediction(
        bot_slug="social-momentum",
        asset="ETH",
        direction="bullish",
        confidence=0.74,
        horizon="3 days",
        thesis="Social engagement accelerated while spot structure remained constructive after a low-volatility pullback.",
        invalidation="Breakdown below the prior demand zone on expanding sell volume.",
        published_at="2026-04-08T07:30:00Z",
    ),
    Prediction(
        bot_slug="breakout",
        asset="SOL",
        direction="bullish",
        confidence=0.71,
        horizon="1 day",
        thesis="A clean range break appeared with confirming volume and intraday continuation behavior.",
        invalidation="Failed hold above breakout level within the first high-volume retest.",
        published_at="2026-04-08T08:10:00Z",
    ),
    Prediction(
        bot_slug="macro-narrative",
        asset="BTC",
        direction="bullish",
        confidence=0.68,
        horizon="7 days",
        thesis="Macro liquidity tone improved while ETF flows stabilized after a weak sentiment cycle.",
        invalidation="Daily close back under the prior range low with ETF outflows reaccelerating.",
        published_at="2026-04-08T09:15:00Z",
    ),
]

ALERTS: list[Alert] = [
    Alert(asset="ETH", bot_name="Social Momentum Bot", direction="bullish", confidence=0.74),
    Alert(asset="SOL", bot_name="Breakout Bot", direction="bullish", confidence=0.71),
    Alert(asset="BTC", bot_name="Macro Narrative Bot", direction="bullish", confidence=0.68),
]

SUMMARY = Summary(
    active_bots=len(BOTS),
    scored_predictions=1184,
    median_calibration=0.84,
    alert_ctr=0.187,
)
