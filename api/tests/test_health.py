from __future__ import annotations

from api.tests.test_api import build_client


def test_healthcheck_exposes_build_revision(monkeypatch) -> None:
    revision = "abc1234" + "0" * 33
    monkeypatch.setenv("BSM_BUILD_REVISION", revision)
    with build_client() as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "bot-society-markets",
        "build_revision": revision,
    }
