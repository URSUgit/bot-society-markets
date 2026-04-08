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
        assert payload["user_profile"]["follows"]
        assert payload["provider_status"]["market_provider_source"]



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



def test_user_workspace_mutations() -> None:
    with build_client() as client:
        me_response = client.get("/api/me")
        assert me_response.status_code == 200
        initial_profile = me_response.json()
        assert initial_profile["follows"]
        assert initial_profile["watchlist"]
        assert initial_profile["alert_rules"]

        unfollow_response = client.delete("/api/me/follows/social-momentum")
        assert unfollow_response.status_code == 200
        assert all(item["bot_slug"] != "social-momentum" for item in unfollow_response.json()["follows"])

        watchlist_response = client.post("/api/me/watchlist", json={"asset": "SOL"})
        assert watchlist_response.status_code == 200
        assert any(item["asset"] == "SOL" for item in watchlist_response.json()["watchlist"])

        alert_response = client.post("/api/me/alert-rules", json={"asset": "BTC", "min_confidence": 0.7})
        assert alert_response.status_code == 200
        assert any(rule["asset"] == "BTC" for rule in alert_response.json()["alert_rules"])



def test_validation_rejects_unknown_assets() -> None:
    with build_client() as client:
        response = client.post("/api/me/watchlist", json={"asset": "DOGE"})
        assert response.status_code == 400
        assert "Unknown asset" in response.json()["detail"]
