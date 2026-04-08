from fastapi.testclient import TestClient

from api.app.main import app

client = TestClient(app)


def test_healthcheck() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"



def test_leaderboard_shape() -> None:
    response = client.get("/api/leaderboard")
    assert response.status_code == 200
    payload = response.json()
    assert payload
    assert payload[0]["name"] == "Macro Narrative Bot"
