from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from api.app.config import Settings
from api.app.main import create_app



def build_client() -> TestClient:
    temp_dir = TemporaryDirectory()
    database_path = Path(temp_dir.name) / "bot-society-markets-test.db"
    app = create_app(Settings(database_path=database_path))
    client = TestClient(app)
    client._temp_dir = temp_dir  # type: ignore[attr-defined]
    return client



def test_healthcheck() -> None:
    with build_client() as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"



def test_dashboard_snapshot_has_professional_data() -> None:
    with build_client() as client:
        response = client.get("/api/dashboard")
        assert response.status_code == 200
        payload = response.json()
        assert payload["summary"]["active_bots"] == 6
        assert payload["leaderboard"]
        assert payload["assets"]
        assert payload["recent_predictions"]
        assert payload["latest_operation"]["cycle_type"] == "bootstrap"



def test_bot_detail_and_cycle_flow() -> None:
    with build_client() as client:
        detail_response = client.get("/api/bots/macro-narrative")
        assert detail_response.status_code == 200
        detail_payload = detail_response.json()
        assert detail_payload["name"] == "Macro Narrative Bot"
        assert detail_payload["recent_predictions"]

        cycle_response = client.post("/api/admin/run-cycle")
        assert cycle_response.status_code == 200
        cycle_payload = cycle_response.json()
        assert cycle_payload["operation"]["generated_predictions"] == 6

        pending_response = client.get("/api/predictions", params={"status": "pending", "limit": 20})
        assert pending_response.status_code == 200
        pending_payload = pending_response.json()
        assert len(pending_payload) >= 6
