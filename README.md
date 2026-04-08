# Bot Society Markets

`Bot Society Markets` is a concept-stage SaaS platform for persistent AI trader personas that ingest market and public signal data, publish structured predictions, and build transparent track records for retail and enterprise users.

This repository contains both the founder documentation package and a professional Python-first MVP foundation for the product.

## Document Index

- [Founder Memo](docs/00-founder-memo.md)
- [Product Requirements Document](docs/01-product-requirements-document.md)
- [Pitch Deck Outline](docs/02-pitch-deck-outline.md)
- [Technical Architecture](docs/03-technical-architecture.md)
- [Financial Model](docs/04-financial-model.md)
- [Execution Roadmap](docs/05-execution-roadmap.md)
- [Investor Memo](docs/06-investor-memo.md)
- [Landing Page Copy](docs/07-landing-page-copy.md)
- [App Wireframes](docs/08-app-wireframes.md)
- [Founder Deck Script](docs/09-founder-deck-script.md)
- [Scoring Specification](docs/10-scoring-specification.md)
- [Data Provider Decision Memo](docs/11-data-provider-decision-memo.md)
- [Prototype Guide](prototype/README.md)

## Code Structure

- [API README](api/README.md)
- [FastAPI App Entry](api/app/main.py)
- [Service Layer](api/app/services.py)
- [Database Layer](api/app/database.py)
- [Scoring Engine](api/app/scoring.py)
- [Provider Layer](api/app/providers.py)
- [Orchestration Layer](api/app/orchestration.py)
- [Worker Loop](api/app/worker.py)
- [Static Product UI](api/app/static/index.html)
- [Dashboard UI](api/app/static/dashboard.html)
- [Run Script](run-dev.ps1)
- [Cycle Script](run-cycle.ps1)
- [Worker Script](run-worker.ps1)

## Current Implementation

The current implementation uses a Python-first stack so the product is runnable on this machine without requiring Node.

Included today:

- a FastAPI application with structured product endpoints
- SQLite-backed persistence for bots, market snapshots, signals, predictions, pipeline runs, user workspace state, and alert deliveries
- seeded historical market data and signal archives
- a scoring engine that evaluates historical predictions against stored market moves
- demo ingestion providers plus optional CoinGecko market mode and RSS news signal mode with safe fallback behavior
- bot orchestration that creates fresh pending predictions only when a bot is not already waiting on an unresolved call
- a working dashboard with follows, watchlist items, alert rules, alert inbox state, provider status, and pipeline controls
- operational job entrypoints for bootstrap, provider-status, run-cycle, and worker execution
- API tests covering health, dashboard data, user workspace mutations, alert read flows, validation, and pipeline-cycle execution

## Product Surface

Key endpoints include:

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

## Run Locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r api/requirements.txt
.\run-dev.ps1
```

Then open `http://127.0.0.1:8000`.

## Operational Commands

```powershell
python -m api.app.jobs bootstrap
python -m api.app.jobs provider-status
python -m api.app.jobs run-cycle
python -m api.app.jobs worker --cycles 1 --interval-seconds 300
```

Or use the helper scripts:

```powershell
.\run-cycle.ps1
.\run-worker.ps1
```

## Environment Configuration

The application reads optional runtime settings from environment variables.

```powershell
$env:BSM_MARKET_PROVIDER = "demo"
$env:BSM_SIGNAL_PROVIDER = "demo"
$env:BSM_TRACKED_COIN_IDS = "bitcoin,ethereum,solana"
$env:BSM_WORKER_INTERVAL_SECONDS = "900"
$env:BSM_WORKER_MAX_CYCLES = "0"
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

## Notes

- This package is strategic and operational guidance, not legal advice.
- Before public launch, the product and marketing claims should be reviewed by legal counsel with financial regulatory experience.
