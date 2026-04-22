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
3. Create the `production` environment first, then provide prompted secret values for CoinGecko, Reddit, and SMTP if you want live external delivery.
4. Create the `staging` environment with its own secrets and RSS feeds.
5. Once each environment finishes the initial sync, open the assigned `onrender.com` URL for the corresponding web service.

## Current Render Blueprint Settings

- project: `bot-society-markets`
- environments: `production` and `staging`
- each environment provisions:
  - one Python web service
  - one Python worker service
  - one managed Render Postgres database
- web and worker both run `python -m api.app.jobs db-upgrade` before starting
- provider secrets are defined with `sync: false` on the web service and mirrored to the worker with service-to-service env references
- environment networking isolation and protection are enabled

## Important Runtime Note

The current hosted setup no longer depends on ephemeral SQLite. The Render blueprint is designed around managed Postgres and explicit environment separation.

That said, deploying both `staging` and `production` provisions two full stacks, so it will cost materially more than the old single demo web service. If you want to start leaner, deploy `staging` first and add `production` after the live provider flow is validated.

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

The current Render blueprint already wires `BSM_DATABASE_URL` from the managed Postgres instance through `fromDatabase`.

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

The dashboard and `provider-status` CLI now surface:

- environment name
- deployment target
- database backend and target
- whether each provider is configured
- whether each provider is live-capable
- whether fallback mode is active

For deeper verification on any environment:

```powershell
python -m api.app.jobs provider-status --probe-live
```

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

## Akash Path

The repository now also includes Akash deployment assets for teams that want decentralized hosting:

- [Akash Bundle README](C:\Users\ionut\OneDrive\Documents\New project\deploy\akash\README.md)
- [Recommended Akash Manifest](C:\Users\ionut\OneDrive\Documents\New project\deploy\akash\web-external-postgres.yaml)
- [Web + Worker Akash Manifest](C:\Users\ionut\OneDrive\Documents\New project\deploy\akash\web-worker-external-postgres.yaml)
- [Experimental Full Stack Manifest](C:\Users\ionut\OneDrive\Documents\New project\deploy\akash\full-stack-postgres.yaml)
- [GHCR Publish Workflow](C:\Users\ionut\OneDrive\Documents\New project\.github\workflows\container-image.yml)

Recommended Akash flow:

1. publish the Docker image to GHCR via GitHub Actions
2. use Akash Console SDL deployment
3. start with the external-Postgres manifest
4. point `BSM_DATABASE_URL` at Neon, Supabase, Railway, or Render Postgres
5. attach `app.bitprivat.com` as the custom domain

This is the safer production option because Akash persistent storage remains tied to lease lifetime.

## Official References

The current Render configuration in this repo aligns with the official support for:

- `fromDatabase` connection wiring
- `sync: false` secret prompts
- service-to-service environment references
- project environments with protection and network isolation

Sources:

- [Render Blueprint YAML Reference](https://render.com/docs/blueprint-spec)
- [Render Projects and Environments](https://render.com/docs/projects)
