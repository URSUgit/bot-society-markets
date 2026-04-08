# Bot Society Markets API

This directory contains a Python-first starter implementation for the project.

## What Is Included

- `app/main.py` - FastAPI application and routes
- `app/mock_data.py` - seed data for bots, predictions, alerts, and metrics
- `app/models.py` - typed response models
- `app/static/` - landing page and dashboard served by the API
- `tests/` - initial API smoke tests

## Run Locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn api.app.main:app --reload
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Next Implementation Targets

- replace mock data with provider-backed ingestion
- persist predictions to a real database
- build bot orchestration workflows
- add authentication and alert delivery
