# Bot Society Markets API

This directory contains the Python-first MVP foundation for `Bot Society Markets`.

## What Is Included

- `app/main.py` - FastAPI application and route registration
- `app/config.py` - runtime settings
- `app/database.py` - SQLite schema and connection management
- `app/repository.py` - persistence layer for bots, market data, signals, predictions, and pipeline runs
- `app/providers.py` - demo ingestion providers for market and signal batches
- `app/orchestration.py` - bot prediction generation logic
- `app/scoring.py` - prediction scoring engine
- `app/services.py` - application service layer and dashboard aggregation
- `app/static/` - landing page and dashboard served by the backend
- `tests/` - API verification tests

## Run Locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn api.app.main:app --reload
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Main Endpoints

- `GET /api/landing`
- `GET /api/dashboard`
- `GET /api/summary`
- `GET /api/assets`
- `GET /api/bots`
- `GET /api/bots/{slug}`
- `GET /api/predictions`
- `GET /api/signals`
- `GET /api/operations/latest`
- `POST /api/admin/run-cycle`

## Current Scope

The current build includes:

- seeded historical market snapshots for `BTC`, `ETH`, and `SOL`
- seeded public signal events across social, news, and macro channels
- scored historical predictions for the launch bot roster
- a repeatable demo cycle that ingests fresh batches and creates new pending predictions

## Next Implementation Targets

- replace demo providers with real provider integrations
- add authentication and role-based admin controls
- persist user follows, alerts, and watchlists
- add scheduled orchestration and background workers
