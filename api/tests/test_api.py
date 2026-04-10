from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app.config import Settings
from api.app.main import create_app


@contextmanager
def build_client(settings: Settings | None = None):
    with TemporaryDirectory() as temp_dir:
        database_path = Path(temp_dir) / "bot-society-markets-test.db"
        active_settings = settings or Settings(database_path=database_path)
        if active_settings.database_url is None:
            active_settings.database_path = database_path
        app = create_app(active_settings)
        with TestClient(app) as client:
            yield client


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
        assert payload["auth_session"]["authenticated"] is False
        assert payload["user_profile"]["follows"]
        assert payload["user_profile"]["recent_alerts"]
        assert payload["user_profile"]["unread_alert_count"] >= 1
        assert "notification_health" in payload
        assert payload["provider_status"]["market_provider_source"]
        assert payload["provider_status"]["signal_provider_mode"] == "demo"
        assert payload["provider_status"]["macro_provider_mode"] == "demo"
        assert payload["provider_status"]["environment_name"] == "development"
        assert payload["provider_status"]["deployment_target"] == "local"
        assert payload["provider_status"]["database_backend"] == "sqlite"
        assert payload["user_profile"]["is_demo_user"] is True
        assert payload["system_pulse"]["live_provider_count"] >= 0
        assert payload["system_pulse"]["total_recent_signals"] >= 1
        assert payload["system_pulse"]["signal_mix"]
        assert payload["macro_snapshot"]["series"]
        assert "paper_trading" in payload
        assert payload["paper_trading"]["summary"]["starting_balance"] == 10000
        assert payload["recent_signals"][0]["source_quality_score"] >= 0
        assert payload["recent_signals"][0]["provider_trust_score"] >= 0
        assert payload["recent_signals"][0]["freshness_score"] >= 0
        assert payload["leaderboard"][0]["provenance_score"] >= 0


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
        assert "alert_inbox" in cycle_payload
        assert cycle_payload["alert_inbox"]["alerts"]

        pending_response = client.get("/api/predictions", params={"status": "pending", "limit": 20})
        assert pending_response.status_code == 200
        pending_payload = pending_response.json()
        assert len(pending_payload) >= 6


def test_user_workspace_mutations() -> None:
    with build_client() as client:
        register_response = client.post(
            "/api/auth/register",
            json={
                "display_name": "Workspace User",
                "email": "workspace@example.com",
                "password": "SuperSecure123",
            },
        )
        assert register_response.status_code == 200

        me_response = client.get("/api/me")
        assert me_response.status_code == 200
        initial_profile = me_response.json()
        assert initial_profile["is_demo_user"] is False

        follow_response = client.post("/api/me/follows", json={"bot_slug": "social-momentum"})
        assert follow_response.status_code == 200
        assert any(item["bot_slug"] == "social-momentum" for item in follow_response.json()["follows"])

        unfollow_response = client.delete("/api/me/follows/social-momentum")
        assert unfollow_response.status_code == 200
        assert all(item["bot_slug"] != "social-momentum" for item in unfollow_response.json()["follows"])

        watchlist_response = client.post("/api/me/watchlist", json={"asset": "SOL"})
        assert watchlist_response.status_code == 200
        assert any(item["asset"] == "SOL" for item in watchlist_response.json()["watchlist"])

        alert_response = client.post("/api/me/alert-rules", json={"asset": "BTC", "min_confidence": 0.7})
        assert alert_response.status_code == 200
        assert any(rule["asset"] == "BTC" for rule in alert_response.json()["alert_rules"])


def test_alert_inbox_endpoints_support_read_flow() -> None:
    with build_client() as client:
        register_response = client.post(
            "/api/auth/register",
            json={
                "display_name": "Alerts User",
                "email": "alerts@example.com",
                "password": "SuperSecure123",
            },
        )
        assert register_response.status_code == 200

        alert_rule_response = client.post("/api/me/alert-rules", json={"bot_slug": "social-momentum", "min_confidence": 0.55})
        assert alert_rule_response.status_code == 200

        cycle_response = client.post("/api/admin/run-cycle")
        assert cycle_response.status_code == 200

        inbox_response = client.get("/api/me/alerts")
        assert inbox_response.status_code == 200
        inbox = inbox_response.json()
        assert inbox["alerts"]
        assert inbox["unread_count"] >= 1

        unread_only_response = client.get("/api/me/alerts", params={"unread_only": True})
        assert unread_only_response.status_code == 200
        unread_only = unread_only_response.json()
        assert unread_only["alerts"]
        first_alert_id = unread_only["alerts"][0]["id"]

        read_response = client.post(f"/api/me/alerts/{first_alert_id}/read")
        assert read_response.status_code == 200
        read_payload = read_response.json()
        assert read_payload["unread_count"] == inbox["unread_count"] - 1

        read_all_response = client.post("/api/me/alerts/read-all")
        assert read_all_response.status_code == 200
        assert read_all_response.json()["unread_count"] == 0


def test_auth_and_notification_channels_flow() -> None:
    with build_client() as client:
        register_response = client.post(
            "/api/auth/register",
            json={
                "display_name": "Alpha Research",
                "email": "alpha@example.com",
                "password": "SuperSecure123",
            },
        )
        assert register_response.status_code == 200
        register_payload = register_response.json()
        assert register_payload["authenticated"] is True
        assert register_payload["user"]["email"] == "alpha@example.com"

        session_response = client.get("/api/auth/session")
        assert session_response.status_code == 200
        assert session_response.json()["authenticated"] is True

        me_response = client.get("/api/me")
        assert me_response.status_code == 200
        assert me_response.json()["email"] == "alpha@example.com"

        channel_response = client.post(
            "/api/me/notification-channels",
            json={"channel_type": "webhook", "target": "https://example.com/webhook"},
        )
        assert channel_response.status_code == 200
        assert len(channel_response.json()["notification_channels"]) == 1

        logout_response = client.post("/api/auth/logout")
        assert logout_response.status_code == 200
        assert logout_response.json()["authenticated"] is False

        post_logout_session = client.get("/api/auth/session")
        assert post_logout_session.status_code == 200
        assert post_logout_session.json()["authenticated"] is False

        login_response = client.post(
            "/api/auth/login",
            json={"email": "alpha@example.com", "password": "SuperSecure123"},
        )
        assert login_response.status_code == 200
        assert login_response.json()["authenticated"] is True

        notification_health = client.get("/api/me/notification-health")
        assert notification_health.status_code == 200
        assert notification_health.json()["active_channels"] == 1


def test_demo_workspace_is_read_only_for_mutations() -> None:
    with build_client() as client:
        response = client.post("/api/me/watchlist", json={"asset": "BTC"})
        assert response.status_code == 401
        assert "Sign in" in response.json()["detail"]


def test_reddit_provider_readiness_and_fallback() -> None:
    with build_client(Settings(signal_provider_mode="reddit", reddit_subreddits=("CryptoCurrency",))) as client:
        provider_response = client.get("/api/system/providers")
        assert provider_response.status_code == 200
        provider_payload = provider_response.json()["provider_status"]
        assert provider_payload["signal_provider_mode"] == "reddit"
        assert provider_payload["signal_provider_configured"] is False
        assert provider_payload["signal_provider_live_capable"] is False
        assert provider_payload["signal_provider_ready"] is False
        assert "BSM_REDDIT_CLIENT_ID" in provider_payload["signal_provider_warning"]

        cycle_response = client.post("/api/admin/run-cycle")
        assert cycle_response.status_code == 200
        cycle_payload = cycle_response.json()
        assert cycle_payload["provider_status"]["signal_fallback_active"] is True


def test_live_provider_configuration_metadata() -> None:
    settings = Settings(
        environment_name="staging",
        deployment_target="render",
        market_provider_mode="coingecko",
        coingecko_plan="pro",
        coingecko_api_key="secret-key",
        signal_provider_mode="reddit",
        reddit_client_id="client-id",
        reddit_client_secret="client-secret",
        reddit_subreddits=("CryptoCurrency", "Bitcoin"),
    )
    with build_client(settings) as client:
        provider_response = client.get("/api/system/providers")
        assert provider_response.status_code == 200
        provider_payload = provider_response.json()["provider_status"]
        assert provider_payload["environment_name"] == "staging"
        assert provider_payload["deployment_target"] == "render"
        assert provider_payload["database_backend"] == "sqlite"
        assert provider_payload["market_provider_configured"] is True
        assert provider_payload["market_provider_live_capable"] is True
        assert provider_payload["signal_provider_configured"] is True
        assert provider_payload["signal_provider_live_capable"] is True


def test_macro_and_asset_history_endpoints_expose_research_data() -> None:
    with build_client() as client:
        history_response = client.get("/api/assets/BTC/history")
        assert history_response.status_code == 200
        history_payload = history_response.json()
        assert history_payload["asset"] == "BTC"
        assert len(history_payload["points"]) >= 2

        macro_response = client.get("/api/macro")
        assert macro_response.status_code == 200
        macro_payload = macro_response.json()
        assert macro_payload["posture"]
        assert macro_payload["summary"]
        assert len(macro_payload["series"]) >= 3
        assert any(series["series_id"] == "FEDFUNDS" for series in macro_payload["series"])

        missing_history_response = client.get("/api/assets/DOGE/history")
        assert missing_history_response.status_code == 400
        assert "Unknown asset" in missing_history_response.json()["detail"]


def test_macro_provider_readiness_and_fallback_metadata() -> None:
    with build_client(Settings(macro_provider_mode="fred")) as client:
        provider_response = client.get("/api/system/providers")
        assert provider_response.status_code == 200
        provider_payload = provider_response.json()["provider_status"]
        assert provider_payload["macro_provider_mode"] == "fred"
        assert provider_payload["macro_provider_configured"] is False
        assert provider_payload["macro_provider_live_capable"] is False
        assert provider_payload["macro_provider_ready"] is False
        assert provider_payload["macro_fallback_active"] is True
        assert provider_payload["macro_provider_source"] == "fredapi-provider-fallback"
        assert "BSM_FRED_API_KEY" in provider_payload["macro_provider_warning"]

        macro_response = client.get("/api/macro")
        assert macro_response.status_code == 200
        assert macro_response.json()["series"]


def test_paper_trading_endpoints_support_simulation_flow() -> None:
    with build_client() as client:
        register_response = client.post(
            "/api/auth/register",
            json={
                "display_name": "Paper Trader",
                "email": "paper@example.com",
                "password": "SuperSecure123",
            },
        )
        assert register_response.status_code == 200

        cycle_response = client.post("/api/admin/run-cycle")
        assert cycle_response.status_code == 200
        assert cycle_response.json()["operation"]["generated_predictions"] >= 1

        snapshot_response = client.get("/api/paper-trading")
        assert snapshot_response.status_code == 200
        snapshot_payload = snapshot_response.json()
        assert snapshot_payload["summary"]["starting_balance"] == 10000

        simulation_response = client.post("/api/me/paper-trading/simulate")
        assert simulation_response.status_code == 200
        simulation_payload = simulation_response.json()
        assert simulation_payload["created_positions"] >= 1
        assert simulation_payload["snapshot"]["summary"]["open_positions"] >= 1
        assert simulation_payload["snapshot"]["positions"]


def test_hyperliquid_and_venue_provider_metadata() -> None:
    settings = Settings(
        market_provider_mode="hyperliquid",
        signal_provider_mode="demo",
        venue_signal_providers=("polymarket", "kalshi"),
        polymarket_tag_id=21,
        kalshi_category="Crypto",
    )
    with build_client(settings) as client:
        provider_response = client.get("/api/system/providers")
        assert provider_response.status_code == 200
        provider_payload = provider_response.json()["provider_status"]
        assert provider_payload["market_provider_mode"] == "hyperliquid"
        assert provider_payload["market_provider_source"] == "hyperliquid-public-provider"
        assert provider_payload["market_provider_configured"] is True
        assert provider_payload["market_provider_live_capable"] is True
        assert provider_payload["signal_provider_mode"] == "demo + polymarket, kalshi"
        assert provider_payload["signal_provider_live_capable"] is True
        assert len(provider_payload["venue_signal_providers"]) == 2
        assert {provider["mode"] for provider in provider_payload["venue_signal_providers"]} == {"polymarket", "kalshi"}


def test_landing_snapshot_and_system_pulse_endpoint() -> None:
    settings = Settings(
        market_provider_mode="hyperliquid",
        signal_provider_mode="demo",
        venue_signal_providers=("polymarket", "kalshi"),
    )
    with build_client(settings) as client:
        landing_response = client.get("/api/landing")
        assert landing_response.status_code == 200
        landing_payload = landing_response.json()
        assert landing_payload["system_pulse"]["total_recent_signals"] >= 1
        assert landing_payload["system_pulse"]["signal_mix"]
        assert landing_payload["system_pulse"]["venue_pulse"]

        pulse_response = client.get("/api/system/pulse")
        assert pulse_response.status_code == 200
        pulse_payload = pulse_response.json()["system_pulse"]
        assert pulse_payload["live_provider_count"] >= 1
        assert pulse_payload["average_signal_quality"] >= 0
        assert pulse_payload["venue_pulse"]


def test_status_page_route_serves_html() -> None:
    with build_client() as client:
        response = client.get("/status")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Public status" in response.text


def test_signal_quality_scoring_is_exposed_on_signal_api() -> None:
    with build_client() as client:
        response = client.get("/api/signals", params={"limit": 12})
        assert response.status_code == 200
        payload = response.json()
        assert payload
        first_signal = payload[0]
        assert 0 <= first_signal["provider_trust_score"] <= 1
        assert 0 <= first_signal["freshness_score"] <= 1
        assert 0 <= first_signal["source_quality_score"] <= 1
        assert first_signal["source_quality_score"] >= 0.6
        social_signal = next(signal for signal in payload if signal["channel"] == "social")
        assert social_signal["source_type"] == "social"


def test_notification_retry_flow_and_health() -> None:
    with build_client(Settings(notification_retry_base_seconds=0)) as client:
        register_response = client.post(
            "/api/auth/register",
            json={
                "display_name": "Retry User",
                "email": "retry@example.com",
                "password": "SuperSecure123",
            },
        )
        assert register_response.status_code == 200

        alert_rule_response = client.post("/api/me/alert-rules", json={"bot_slug": "social-momentum", "min_confidence": 0.55})
        assert alert_rule_response.status_code == 200

        channel_response = client.post(
            "/api/me/notification-channels",
            json={"channel_type": "webhook", "target": "https://example.com/webhook"},
        )
        assert channel_response.status_code == 200

        with patch("api.app.notifications.NotificationDispatcher.dispatch", return_value=(False, "Webhook timeout")):
            cycle_response = client.post("/api/admin/run-cycle")
        assert cycle_response.status_code == 200

        health_response = client.get("/api/me/notification-health")
        assert health_response.status_code == 200
        health_payload = health_response.json()
        assert health_payload["retry_queue_depth"] >= 1

        retry_candidates = [
            alert for alert in client.get("/api/me/alerts").json()["alerts"] if alert["delivery_status"] == "retry_scheduled"
        ]
        assert retry_candidates

        with patch("api.app.notifications.NotificationDispatcher.dispatch", return_value=(True, None)):
            retry_response = client.post("/api/admin/retry-notifications")
        assert retry_response.status_code == 200
        retry_payload = retry_response.json()
        assert retry_payload["delivered"] >= 1

        health_after_retry = client.get("/api/me/notification-health")
        assert health_after_retry.status_code == 200
        assert health_after_retry.json()["retry_queue_depth"] == 0


def test_validation_rejects_unknown_assets() -> None:
    with build_client() as client:
        register_response = client.post(
            "/api/auth/register",
            json={
                "display_name": "Validation User",
                "email": "validation@example.com",
                "password": "SuperSecure123",
            },
        )
        assert register_response.status_code == 200

        response = client.post("/api/me/watchlist", json={"asset": "DOGE"})
        assert response.status_code == 400
        assert "Unknown asset" in response.json()["detail"]
