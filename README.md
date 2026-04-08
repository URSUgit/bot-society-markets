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

- [API Starter](api/README.md)
- [FastAPI App Entry](api/app/main.py)
- [Static Product UI](api/app/static/index.html)
- [Dashboard Preview](api/app/static/dashboard.html)
- [Run Script](run-dev.ps1)

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
- SQLite-backed persistence for bots, market snapshots, signals, predictions, and pipeline runs
- seeded historical market data and signal archives
- a scoring engine that evaluates historical predictions against stored market moves
- demo ingestion providers and a bot orchestration pipeline
- a polished landing page and working dashboard served by the backend
- API tests covering health, dashboard data, bot detail, and pipeline-cycle execution

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
- `GET /api/operations/latest`
- `POST /api/admin/run-cycle`

## Recommended First Build

The initial MVP should:

- focus on one asset universe
- run 5 to 10 trader bots
- ingest approved market and public signal data
- generate structured predictions
- score predictions against realized outcomes
- present results through dashboards, leaderboards, and alerts

## Notes

- This package is strategic and operational guidance, not legal advice.
- Before public launch, the product and marketing claims should be reviewed by legal counsel with financial regulatory experience.

## Run Locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r api/requirements.txt
.\run-dev.ps1
```

Then open `http://127.0.0.1:8000`.
