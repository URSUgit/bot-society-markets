# Deployment Guide

## Local One-Click Launch

Use the Windows launcher when you want the fastest local Python experience:

- `launch-dashboard.bat`
- `launch-dashboard.ps1`
- `install-shortcuts.ps1`

The launcher now prefers Docker + Postgres on port `8010`, falls back to the local Python runtime if Docker is unavailable, and opens `/dashboard` in your browser. `install-shortcuts.ps1` refreshes the desktop links for the start and stop flows.

## Local Docker Stack

The repository now includes `docker-compose.yml` plus Windows helpers:

- `run-docker.ps1`
- `run-docker.bat`
- `stop-docker.ps1`
- `stop-docker.bat`

Start API + Postgres on host port `8010`:

```powershell
.\run-docker.ps1
```

Start API + Postgres + worker:

```powershell
.\run-docker.ps1 -WithWorker
```

Choose a different host port if needed:

```powershell
.\run-docker.ps1 -Port 8020
```

Stop the stack:

```powershell
.\stop-docker.ps1
```

## Hosted Deployment Choice

The project is now configured for Render using the root `render.yaml` blueprint.

Included deployment assets:

- `render.yaml`
- `.python-version`
- `requirements.txt`
- `Dockerfile`
- `.dockerignore`
- `.github/workflows/ci.yml`
- `deploy-render.ps1`
- `deploy-render.bat`

## Recommended Render Flow

1. Ensure the GitHub repository is accessible to Render.
2. Open the deploy flow:
   - `deploy-render.bat`
   - or `https://render.com/deploy?repo=https://github.com/URSUgit/bot-society-markets`
3. Review the generated web service settings.
4. Create the service.
5. Once the first deploy completes, open the assigned `onrender.com` URL.

## Current Render Blueprint Settings

- runtime: `python`
- plan: `free`
- build command: `pip install -r requirements.txt`
- start command: `python -m uvicorn api.app.main:app --host 0.0.0.0 --port $PORT`
- health check: `/health`
- default database path: `/tmp/bot_society_markets.db`

## Important Runtime Note

The current Render setup is appropriate for demos and previews. It still uses SQLite in ephemeral storage, so data can reset when the instance restarts or is replaced. For a more production-like local environment, use Docker Compose with Postgres.

## Database Operations

Operational commands now include a revision-based Alembic migration flow:

```powershell
python -m api.app.jobs db-upgrade
python -m api.app.jobs db-copy --source-path api/data/bot_society_markets.db --target-url "postgresql+psycopg://..."
```

Recommended workflow for a more durable hosted environment:

1. point `BSM_DATABASE_URL` to Postgres
2. run `python -m api.app.jobs db-upgrade`
3. optionally copy demo data into the target database with `db-copy`
4. deploy the API and worker against the same Postgres instance

## Provider Configuration Notes

Supported signal modes today:

- `demo`
- `rss`
- `reddit`

Example social-ingestion runtime variables:

```powershell
$env:BSM_SIGNAL_PROVIDER = "reddit"
$env:BSM_REDDIT_CLIENT_ID = "your-client-id"
$env:BSM_REDDIT_CLIENT_SECRET = "your-client-secret"
$env:BSM_REDDIT_USER_AGENT = "BotSocietyMarkets/0.7"
$env:BSM_REDDIT_SUBREDDITS = "CryptoCurrency,Bitcoin,ethtrader,solana"
$env:BSM_REDDIT_POST_LIMIT = "15"
```

If Reddit credentials are not present, the application will report provider readiness warnings and safely fall back to demo signal generation during cycle execution.

## Workspace Access Model

- anonymous visitors land in a seeded shared demo workspace
- demo mode is intentionally read-only for follows, watchlists, rules, and alert actions
- signed-in users get a personal workspace with saved state and private notification channels

## Container Path

The repository now includes a Docker image definition for teams that prefer container-first deployment targets.

Build and run locally:

```powershell
docker build -t bot-society-markets .
docker run --rm -p 8000:8000 bot-society-markets
```

This uses the same FastAPI entrypoint as the Render blueprint.

For a durable hosted environment, the next production move should be:

1. move the hosted environment to managed Postgres
2. split API and worker into separate services
3. add provider provenance scoring and source-quality weighting
4. add external secret management for provider and notification credentials
