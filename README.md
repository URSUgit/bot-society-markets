# Bot Society Markets

`Bot Society Markets` is a concept-stage SaaS platform for persistent AI trader personas that ingest market and public signal data, publish structured predictions, and build transparent track records for retail and enterprise users.

This repository now contains both the founder documentation package and a professional Python-first MVP foundation for the product.

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
- [Static Product UI](api/app/static/index.html)
- [Dashboard UI](api/app/static/dashboard.html)
- [Run Script](run-dev.ps1)
- [Cycle Script](run-cycle.ps1)

## Project Summary

The long-term `Bot Society` vision is a governed digital economy of autonomous AI agents that create value, develop reputations, and collaborate in structured markets.

The recommended first product is `Bot Society Markets`, a financial analyst network built from persistent AI trader bots. Each bot acts as a repeatable analyst persona with:

- a strategy archetype
- a defined asset universe
- a fixed prediction schema
- a public history
- a measurable score

The first release should be a research and prediction platform, not an automated trading system.

## Current Implementation

The current implementation uses a Python-first stack so the product is runnable on this machine without requiring Node.

Included today:

- a FastAPI application with structured product endpoints
- SQLite-backed persistence for bots, market snapshots, signals, predictions, pipeline runs, and user workspace state
- seeded historical market data and signal archives
- a scoring engine that evaluates historical predictions against stored market moves
- demo ingestion providers plus an optional CoinGecko-backed market provider mode
- bot orchestration that creates fresh pending predictions only when a bot is not already waiting on an unresolved call
- a working dashboard with follows, watchlist items, alert rules, and pipeline controls
- operational job entrypoints for bootstrap, provider-status, and cycle execution
- API tests covering health, dashboard data, user workspace mutations, validation, and pipeline-cycle execution

## API Surface

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
```

## Optional Live Market Provider

The repo can run against the demo provider by default or a live CoinGecko market provider.

Example PowerShell setup:

```powershell
$env:BSM_MARKET_PROVIDER = "coingecko"
$env:BSM_COINGECKO_PLAN = "demo"
$env:BSM_COINGECKO_API_KEY = "your-key-here"
```

Then start the app normally.

## Notes

- This package is strategic and operational guidance, not legal advice.
- Before public launch, the product and marketing claims should be reviewed by legal counsel with financial regulatory experience.
