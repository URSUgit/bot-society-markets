# Deployment Guide

## Local One-Click Launch

Use the Windows launcher when you want the fastest local experience:

- `launch-dashboard.bat`
- `launch-dashboard.ps1`

The launcher will create `.venv`, install dependencies from `requirements.txt`, start the API server, wait for `/health`, and open `/dashboard` in your browser.

## Hosted Deployment Choice

The project is now configured for Render using the root `render.yaml` blueprint.

Included deployment assets:

- `render.yaml`
- `.python-version`
- `requirements.txt`
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

The current hosted setup is appropriate for demos and previews. It uses SQLite in ephemeral storage, so data can reset when the instance restarts or is replaced.

For a durable hosted environment, the next production move should be:

1. move persistence to managed Postgres
2. split API and worker into separate services
3. add email/webhook notification delivery
4. add authenticated user accounts
