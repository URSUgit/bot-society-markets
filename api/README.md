# Bot Society Markets API

This directory contains the Python-first MVP foundation for `Bot Society Markets`.

## What Is Included

- `app/main.py` - FastAPI application and route registration
- `app/config.py` - runtime settings and provider configuration
- `app/database.py` - SQLite schema and connection management
- `app/repository.py` - persistence layer for bots, market data, signals, predictions, pipeline runs, and user state
- `app/providers.py` - demo providers and optional CoinGecko market adapter
- `app/orchestration.py` - bot prediction generation logic
- `app/scoring.py` - prediction scoring engine
- `app/services.py` - application service layer and dashboard aggregation
- `app/jobs.py` - operational CLI entrypoints
- `app/static/` - landing page and dashboard served by the backend
- `tests/` - API verification tests

## Main Endpoints

- `GET /api/landing`
- `GET /api/dashboard`
- `GET /api/summary`
- `GET /api/assets`
- `GET /api/bots`
- `GET /api/bots/{slug}`
- `GET /api/predictions`
- `GET /api/signals`
- `GET /api/me`
- `POST /api/me/follows`
- `POST /api/me/watchlist`
- `POST /api/me/alert-rules`
- `GET /api/system/providers`
- `POST /api/admin/run-cycle`

## Current Scope

The current build includes:

- seeded historical market snapshots for `BTC`, `ETH`, and `SOL`
- seeded public signal events across social, news, and macro channels
- scored historical predictions for the launch bot roster
- persisted demo user state for follows, watchlist items, and alert rules
- a repeatable pipeline cycle that ingests fresh batches and creates new pending predictions
- optional live market data through CoinGecko configuration with demo fallback behavior

## Run Locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn api.app.main:app --reload
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Job Commands

```powershell
python -m api.app.jobs bootstrap
python -m api.app.jobs provider-status
python -m api.app.jobs run-cycle
```

## Optional CoinGecko Setup

```powershell
$env:BSM_MARKET_PROVIDER = "coingecko"
$env:BSM_COINGECKO_PLAN = "demo"
$env:BSM_COINGECKO_API_KEY = "your-key-here"
```

## Verification

```powershell
python -m pytest api/tests/test_api.py
```

## Next Implementation Targets

- replace demo social/news ingestion with real connector-backed providers
- add authentication and role-based access controls
- persist alert delivery events and notification channels
- move pipeline execution into scheduled/background workers
