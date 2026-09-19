from __future__ import annotations

from unittest.mock import patch

import pytest

from api.app.config import Settings
from api.app.repository import BotSocietyRepository
from api.app.strategy_bot_controls import strategy_bot_control_updates
from api.tests.test_api import build_client


@pytest.fixture
def operator():
    with build_client(Settings(simulation_live_history=False)) as client:
        registered = client.post(
            "/api/v1/auth/register",
            json={"display_name": "Safety Operator", "email": "safety@example.com", "password": "SuperSecure123"},
        )
        assert registered.status_code == 200
        created = client.post(
            "/api/v1/strategies",
            json={"name": "Safety Test", "config": {"asset": "BTC", "history_source_mode": "local", "lookback_years": 1}},
        )
        assert created.status_code == 200
        yield client, registered.json()["user"]["slug"], created.json()["id"]


@pytest.mark.parametrize("cause", ["live_gate", "live_gate_no_order", "backtest"])
def test_blocked_bot_cannot_resume_directly_or_through_pause(operator, cause):
    client, _, strategy_id = operator
    service = client.app.state.bot_society_service
    request = {"max_notional_usd": 100, "min_backtest_win_rate": 0}
    if cause.startswith("live_gate"):
        request.update(execution_mode="live", venue="interactivebrokers", place_initial_order=cause == "live_gate")
    else:
        request.update(execution_mode="paper", place_initial_order=False, min_backtest_win_rate=1)
        run_backtest = service.run_strategy_backtest

        def losing_backtest(*args, **kwargs):
            result = run_backtest(*args, **kwargs)
            return result.model_copy(update={"summary": {**result.summary, "win_rate": 0}})

        service.run_strategy_backtest = losing_backtest

    deployed = client.post(f"/api/v1/strategies/{strategy_id}/deploy", json=request)
    assert deployed.status_code == 200
    assert deployed.json()["status"] == "blocked"
    deployment_id = deployed.json()["deployment_id"]
    original = client.get(f"/api/v1/trading/bots/{deployment_id}").json()
    orders = client.get("/api/v1/trading/orders").json()

    with patch.object(service, "place_trading_order") as place_order:
        for action in ("resume", "pause", "resume"):
            response = client.post(f"/api/v1/trading/bots/{deployment_id}/{action}", json={})
            assert response.status_code == 400
            assert "deploy the strategy again" in response.json()["detail"].lower()
            assert client.get(f"/api/v1/trading/bots/{deployment_id}").json() == original
        place_order.assert_not_called()
    assert client.get("/api/v1/trading/orders").json() == orders

    # A fresh deployment repeats validations; a still-closed gate remains blocked.
    repeated = client.post(f"/api/v1/strategies/{strategy_id}/deploy", json=request)
    assert repeated.json()["status"] == "blocked"
    assert repeated.json()["deployment_id"] != deployment_id
    if cause == "backtest":
        request["min_backtest_win_rate"] = 0
        revalidated = client.post(f"/api/v1/strategies/{strategy_id}/deploy", json=request)
        assert revalidated.json()["status"] == "active"
        assert client.get(f"/api/v1/trading/bots/{deployment_id}").json() == original


@pytest.mark.parametrize("action", ["pause", "resume"])
@pytest.mark.parametrize(
    "status,kill_switch",
    [("blocked", True), ("blocked", False), ("killed", True), ("paused", True), ("active", True), ("unknown", False)],
)
def test_operator_controls_cannot_clear_safety_blocks(action, status, kill_switch):
    with pytest.raises(ValueError):
        strategy_bot_control_updates(
            current_status=status, kill_switch_active=kill_switch, action=action, reason="review", now="now"
        )


def test_live_deploy_without_initial_order_validates_without_submitting(operator):
    client, _, strategy_id = operator
    service = client.app.state.bot_society_service
    service.settings.ibkr_connection_mode = "client_portal"
    service.settings.ibkr_account_id = "DU1234567"
    service.settings.ibkr_live_trading_enabled = True
    service.settings.ibkr_read_only = False
    with patch.object(service, "place_trading_order") as place_order:
        response = client.post(
            f"/api/v1/strategies/{strategy_id}/deploy",
            json={
                "execution_mode": "live", "venue": "interactivebrokers",
                "place_initial_order": False, "max_notional_usd": 100, "min_backtest_win_rate": 0,
            },
        )
        assert response.status_code == 200
        assert response.json()["status"] == "active"
        assert response.json()["paper_order"] is None
        place_order.assert_not_called()


@pytest.mark.parametrize("outer_action,inner_action,expected_code", [("resume", "kill", 400), ("kill", "resume", 200)])
def test_concurrent_kill_wins_over_resume(operator, outer_action, inner_action, expected_code):
    client, user_slug, strategy_id = operator
    deployed = client.post(
        f"/api/v1/strategies/{strategy_id}/deploy",
        json={"place_initial_order": False, "min_backtest_win_rate": 0},
    )
    assert deployed.status_code == 200
    deployment_id = deployed.json()["deployment_id"]
    assert client.post(f"/api/v1/trading/bots/{deployment_id}/pause", json={}).status_code == 200
    service = client.app.state.bot_society_service
    update_deployment = BotSocietyRepository.update_strategy_deployment
    intervened = False

    def intervene_before_write(repository, *args, **kwargs):
        nonlocal intervened
        if not intervened:
            intervened = True
            service.control_strategy_bot(user_slug, deployment_id, inner_action)
        return update_deployment(repository, *args, **kwargs)

    with patch.object(BotSocietyRepository, "update_strategy_deployment", intervene_before_write):
        response = client.post(f"/api/v1/trading/bots/{deployment_id}/{outer_action}", json={})
    assert response.status_code == expected_code
    if outer_action == "resume":
        assert "state changed" in response.json()["detail"]
    current = client.get(f"/api/v1/trading/bots/{deployment_id}").json()
    assert current["status"] == "killed"
    assert current["kill_switch_active"] is True
    if outer_action == "resume":
        assert all(event["event_type"] != "control.resume" for event in current["recent_events"])
