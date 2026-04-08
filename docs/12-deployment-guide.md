# Deployment Guide

## Local One-Click Launch

Use the Windows launcher when you want the fastest local Python experience:

- `launch-dashboard.bat`
- `launch-dashboard.ps1`

The launcher will create `.venv`, install dependencies from `requirements.txt`, start the API server, wait for `/health`, and open `/dashboard` in your browser.

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
3. add delivery retries and notification observability
4. add provider provenance and source-quality controls
