# Bot Society Markets API

This directory contains the Python-first MVP foundation for `Bot Society Markets`.

## What Is Included

- `app/main.py` - FastAPI application and route registration
- `app/config.py` - runtime settings, provider modes, and worker configuration
- `app/database.py` - SQLite schema and connection management
- `app/repository.py` - persistence layer for bots, market data, signals, predictions, pipeline runs, user state, and alert deliveries
- `app/providers.py` - demo providers, optional CoinGecko market adapter, and optional RSS signal ingestion
- `app/orchestration.py` - bot prediction generation logic
- `app/scoring.py` - prediction scoring engine
- `app/services.py` - application service layer, inbox delivery, and dashboard aggregation
- `app/worker.py` - scheduled pipeline worker loop
- `app/jobs.py` - operational CLI entrypoints
- `app/static/` - landing page and dashboard served by the backend
- `tests/` - API verification tests
- `../Dockerfile` - container image definition for deployment
- `../.github/workflows/ci.yml` - continuous integration workflow

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
- `GET /api/me/alerts`
- `POST /api/me/alerts/{alert_id}/read`
- `POST /api/me/alerts/read-all`
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
- persisted demo user state for follows, watchlist items, alert rules, and in-app alert deliveries
- a repeatable pipeline cycle that ingests fresh batches, creates new pending predictions, and delivers alert events
- optional live market data through CoinGecko configuration with demo fallback behavior
- optional RSS-backed news ingestion with demo fallback behavior
- a worker loop for scheduled cycle execution

## Run Locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn api.app.main:app --reload
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Job Commands

```powershell
python -m api.app.jobs bootstrap
python -m api.app.jobs provider-status
python -m api.app.jobs run-cycle
python -m api.app.jobs worker --cycles 1 --interval-seconds 300
```

## Windows Launcher

The repository includes a one-click launcher:

- [launch-dashboard.bat](C:\Users\ionut\OneDrive\Documents\New project\launch-dashboard.bat)
- [launch-dashboard.ps1](C:\Users\ionut\OneDrive\Documents\New project\launch-dashboard.ps1)

It will provision the virtual environment if needed, install dependencies, start the API, and open the dashboard automatically.

## Environment Variables

```powershell
$env:BSM_MARKET_PROVIDER = "demo"
$env:BSM_SIGNAL_PROVIDER = "demo"
$env:BSM_TRACKED_COIN_IDS = "bitcoin,ethereum,solana"
$env:BSM_WORKER_INTERVAL_SECONDS = "900"
$env:BSM_WORKER_MAX_CYCLES = "0"
$env:BSM_ALERT_INBOX_LIMIT = "10"
```

Optional live provider setup:

```powershell
$env:BSM_MARKET_PROVIDER = "coingecko"
$env:BSM_COINGECKO_PLAN = "demo"
$env:BSM_COINGECKO_API_KEY = "your-key-here"

$env:BSM_SIGNAL_PROVIDER = "rss"
$env:BSM_RSS_FEED_URLS = "https://your-feed-1.example/rss,https://your-feed-2.example/rss"
```

## Verification

```powershell
python -m pytest api/tests/test_api.py
```

## Container Run

```powershell
docker build -t bot-society-markets .
docker run --rm -p 8000:8000 bot-society-markets
```

## Next Targets

- add authenticated user accounts and notification channels
- move from SQLite to managed Postgres when multi-user workflows begin
- add provider-level provenance scoring and source quality controls
