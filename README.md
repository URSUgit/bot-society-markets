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
- [Deployment Guide](docs/12-deployment-guide.md)
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
- [Dockerfile](C:\Users\ionut\OneDrive\Documents\New project\Dockerfile)
- [CI Workflow](C:\Users\ionut\OneDrive\Documents\New project\.github\workflows\ci.yml)
- [Run Script](run-dev.ps1)
- [Launcher Script](launch-dashboard.ps1)
- [Launcher Shortcut](launch-dashboard.bat)
- [Cycle Script](run-cycle.ps1)
- [Worker Script](run-worker.ps1)
- [Render Blueprint](render.yaml)

## Current Implementation

The current implementation uses a Python-first stack so the product is runnable on this machine without requiring Node.

Included today:

- a FastAPI application with structured product endpoints
- SQLAlchemy-backed persistence for bots, market snapshots, signals, predictions, pipeline runs, user state, sessions, notification channels, and alert deliveries
- Alembic migration scaffolding plus operational database upgrade and copy commands
- seeded historical market data and signal archives
- a scoring engine that evaluates historical predictions against stored market moves
- demo ingestion providers plus optional CoinGecko market mode and RSS news signal mode with safe fallback behavior
- bot orchestration that creates fresh pending predictions only when a bot is not already waiting on an unresolved call
- a working dashboard with demo-mode access, sign in/register flows, follows, watchlist items, alert rules, notification channels, alert inbox state, provider status, delivery-health visibility, and pipeline controls
- a read-only demo workspace with clearly separated authenticated personal workspaces for saved follows, watchlists, rules, and notification actions
- notification retry scheduling, retry jobs, and per-channel observability for outbound alert delivery
- operational job entrypoints for bootstrap, provider-status, run-cycle, retry-notifications, notification-health, db-upgrade, db-copy, and worker execution
- API tests covering health, dashboard data, auth flows, user workspace mutations, notification channels, alert read flows, validation, and pipeline-cycle execution
- GitHub Actions CI for Python tests and Docker image validation
- Docker assets for reproducible container deployment
- desktop shortcut installation for one-click Windows startup

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
- `GET /api/auth/session`
- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/me`
- `GET /api/me/alerts`
- `GET /api/me/notification-health`
- `POST /api/me/alerts/{alert_id}/read`
- `POST /api/me/alerts/read-all`
- `POST /api/me/follows`
- `POST /api/me/watchlist`
- `POST /api/me/alert-rules`
- `GET /api/system/providers`
- `POST /api/admin/run-cycle`
- `POST /api/admin/retry-notifications`

## Run Locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r api/requirements.txt
.\run-dev.ps1
```

Then open `http://127.0.0.1:8000`.

## One-Click Windows Launcher

Double-click:

- [launch-dashboard.bat](C:\Users\ionut\OneDrive\Documents\New project\launch-dashboard.bat)
- or use the installed desktop shortcut: `Bot Society Markets Dashboard`

Or run:

```powershell
.\launch-dashboard.ps1
```

The launcher will:

- prefer the Docker + Postgres stack on port `8010`
- fall back to the local Python launcher if Docker is unavailable
- open the dashboard in your default browser

To install or refresh the desktop shortcuts:

```powershell
.\install-shortcuts.ps1
```

## Operational Commands

```powershell
python -m api.app.jobs bootstrap
python -m api.app.jobs provider-status
python -m api.app.jobs run-cycle
python -m api.app.jobs retry-notifications
python -m api.app.jobs notification-health
python -m api.app.jobs db-upgrade
python -m api.app.jobs worker --cycles 1 --interval-seconds 300
```

Or use the helper scripts:

```powershell
.\run-cycle.ps1
.\run-worker.ps1
```

## Deploy To Render

This repo now includes a Render blueprint at [render.yaml](C:\Users\ionut\OneDrive\Documents\New project\render.yaml).

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/URSUgit/bot-society-markets)

Fastest path:

- run [deploy-render.bat](C:\Users\ionut\OneDrive\Documents\New project\deploy-render.bat)
- or open [https://render.com/deploy?repo=https://github.com/URSUgit/bot-society-markets](https://render.com/deploy?repo=https://github.com/URSUgit/bot-society-markets)

If the repository stays private, Render's docs indicate you need Render's GitHub App installed on the repository before the deploy flow can read it.

## Environment Configuration

The application reads optional runtime settings from environment variables.

```powershell
$env:BSM_MARKET_PROVIDER = "demo"
$env:BSM_SIGNAL_PROVIDER = "demo"
$env:BSM_TRACKED_COIN_IDS = "bitcoin,ethereum,solana"
$env:BSM_WORKER_INTERVAL_SECONDS = "900"
$env:BSM_WORKER_MAX_CYCLES = "0"
$env:BSM_NOTIFICATION_RETRY_LIMIT = "25"
$env:BSM_NOTIFICATION_MAX_ATTEMPTS = "4"
$env:BSM_NOTIFICATION_RETRY_BASE_SECONDS = "300"
```

Optional live provider setup:

```powershell
$env:BSM_MARKET_PROVIDER = "coingecko"
$env:BSM_COINGECKO_PLAN = "demo"
$env:BSM_COINGECKO_API_KEY = "your-key-here"

$env:BSM_SIGNAL_PROVIDER = "rss"
$env:BSM_RSS_FEED_URLS = "https://your-feed-1.example/rss,https://your-feed-2.example/rss"

$env:BSM_SIGNAL_PROVIDER = "reddit"
$env:BSM_REDDIT_CLIENT_ID = "your-client-id"
$env:BSM_REDDIT_CLIENT_SECRET = "your-client-secret"
$env:BSM_REDDIT_USER_AGENT = "BotSocietyMarkets/0.7"
$env:BSM_REDDIT_SUBREDDITS = "CryptoCurrency,Bitcoin,ethtrader,solana"
$env:BSM_REDDIT_POST_LIMIT = "15"
```

Runtime behavior:

- anonymous visitors land in a seeded shared demo workspace
- demo mode is intentionally read-only
- account creation or sign-in unlocks a private personal workspace for saved follows, watchlists, rules, inbox actions, and notification channels

## Verification

```powershell
python -m pytest api/tests/test_api.py
```

## CI And Containers

This repo now includes:

- [GitHub Actions CI](C:\Users\ionut\OneDrive\Documents\New project\.github\workflows\ci.yml)
- [Dockerfile](C:\Users\ionut\OneDrive\Documents\New project\Dockerfile)
- [.dockerignore](C:\Users\ionut\OneDrive\Documents\New project\.dockerignore)

Local Docker command:

```powershell
docker build -t bot-society-markets .
docker run --rm -p 8000:8000 bot-society-markets
```

## Docker Compose

This repo now includes [docker-compose.yml](C:\Users\ionut\OneDrive\Documents\New project\docker-compose.yml) for a professional local stack with Postgres.

Start API + Postgres on the default Docker port `8010`:

```powershell
.\run-docker.ps1
```

Start API + Postgres + worker:

```powershell
.\run-docker.ps1 -WithWorker
```

Choose a different host port if you want:

```powershell
.\run-docker.ps1 -Port 8020
```

Stop the stack:

```powershell
.\stop-docker.ps1
```

The dashboard will be available at `http://127.0.0.1:8010/dashboard` by default.

## Notes

- This package is strategic and operational guidance, not legal advice.
- Before public launch, the product and marketing claims should be reviewed by legal counsel with financial regulatory experience.
