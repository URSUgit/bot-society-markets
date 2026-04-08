from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .models import Alert, Bot, Prediction, Summary
from .services import get_summary, list_alerts, list_bots, list_predictions

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="Bot Society Markets",
    version="0.1.0",
    description="Starter API and static frontend for the Bot Society Markets concept.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok", "service": "bot-society-markets"}


@app.get("/api/summary", response_model=Summary)
def summary() -> Summary:
    return get_summary()


@app.get("/api/bots", response_model=list[Bot])
def bots() -> list[Bot]:
    return list_bots()


@app.get("/api/leaderboard", response_model=list[Bot])
def leaderboard() -> list[Bot]:
    return list_bots()


@app.get("/api/predictions", response_model=list[Prediction])
def predictions() -> list[Prediction]:
    return list_predictions()


@app.get("/api/alerts", response_model=list[Alert])
def alerts() -> list[Alert]:
    return list_alerts()


@app.get("/")
def landing() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/dashboard")
def dashboard() -> FileResponse:
    return FileResponse(STATIC_DIR / "dashboard.html")
