from typing import Literal

from pydantic import BaseModel, Field

Direction = Literal["bullish", "bearish", "neutral"]


class Bot(BaseModel):
    slug: str
    name: str
    archetype: str
    focus: str
    horizon: str
    thesis: str
    score: float = Field(ge=0, le=100)
    hit_rate: float = Field(ge=0, le=1)
    calibration: float = Field(ge=0, le=1)
    predictions: int = Field(ge=0)


class Prediction(BaseModel):
    bot_slug: str
    asset: str
    direction: Direction
    confidence: float = Field(ge=0, le=1)
    horizon: str
    thesis: str
    invalidation: str
    published_at: str


class Alert(BaseModel):
    asset: str
    bot_name: str
    direction: Direction
    confidence: float = Field(ge=0, le=1)


class Summary(BaseModel):
    active_bots: int
    scored_predictions: int
    median_calibration: float = Field(ge=0, le=1)
    alert_ctr: float = Field(ge=0, le=1)
