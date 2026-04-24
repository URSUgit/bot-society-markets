from __future__ import annotations

from contextlib import contextmanager
import hashlib
import hmac
from io import BytesIO
import json
from pathlib import Path
import sqlite3
import shutil
from tempfile import TemporaryDirectory
import tempfile
import time
from unittest.mock import patch
import zipfile

from fastapi.testclient import TestClient

from api.app.config import Settings
from api.app.database import Database
from api.app.db_ops import backup_sqlite_database, copy_database
from api.app.main import create_app


@contextmanager
def build_client(settings: Settings | None = None):
    with TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        database_path = temp_root / "bot-society-markets-test.db"
        active_settings = settings or Settings(database_path=database_path)
        if active_settings.database_url is None:
            active_settings.database_path = database_path
        active_settings.export_artifacts_dir = temp_root / "exports"
        app = create_app(active_settings)
        with TestClient(app) as client:
            yield client


def stripe_signature(secret: str, payload: dict[str, object], *, timestamp: int | None = None) -> tuple[str, bytes]:
    active_timestamp = timestamp or int(time.time())
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    signed_payload = f"{active_timestamp}.{payload_bytes.decode('utf-8')}".encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    return f"t={active_timestamp},v1={digest}", payload_bytes


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
        assert payload["provider_status"]["wallet_provider_mode"] == "demo"
        assert payload["provider_status"]["environment_name"] == "development"
        assert payload["provider_status"]["deployment_target"] == "local"
        assert payload["provider_status"]["database_backend"] == "sqlite"
        assert payload["user_profile"]["is_demo_user"] is True
        assert payload["system_pulse"]["live_provider_count"] >= 0
        assert payload["system_pulse"]["total_recent_signals"] >= 1
        assert payload["system_pulse"]["signal_mix"]
        assert payload["macro_snapshot"]["series"]
        assert payload["wallet_intelligence"]["wallets"]
        assert abs(payload["wallet_intelligence"]["aggregate_bias"]) <= 1
        assert payload["edge_snapshot"]["opportunities"]
        assert "paper_trading" in payload
        assert payload["paper_trading"]["summary"]["starting_balance"] == 10000
        assert payload["paper_venues"]["venues"]
        assert payload["paper_venues"]["recommended_venue_id"] == "polysandbox"
        assert payload["launch_readiness"]["tracks"]
        assert any(track["key"] == "fiat_onboarding" for track in payload["launch_readiness"]["tracks"])
        assert payload["connector_control"]["connectors"]
        assert payload["infrastructure_readiness"]["tasks"]
        assert payload["production_cutover"]["steps"]
        assert payload["business_model"]["products"]
        assert any(product["key"] == "retail_autopilot" for product in payload["business_model"]["products"])
        assert "billing" in payload["user_profile"]
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


def test_connector_and_infrastructure_system_endpoints() -> None:
    with build_client() as client:
        connectors_response = client.get("/api/system/connectors")
        assert connectors_response.status_code == 200
        connectors_payload = connectors_response.json()["connector_control"]
        connector_ids = {item["id"] for item in connectors_payload["connectors"]}
        assert "coingecko-market-data" in connector_ids
        assert "polymarket-intel" in connector_ids

        infrastructure_response = client.get("/api/system/infrastructure")
        assert infrastructure_response.status_code == 200
        infrastructure_payload = infrastructure_response.json()["infrastructure_readiness"]
        assert infrastructure_payload["production_posture"] == "attention"
        assert any(task["key"] == "managed_database" for task in infrastructure_payload["tasks"])

        cutover_response = client.get("/api/system/production-cutover")
        assert cutover_response.status_code == 200
        cutover_payload = cutover_response.json()["production_cutover"]
        assert cutover_payload["current_backend"] == "sqlite"
        assert cutover_payload["target_backend"] == "postgresql"
        assert any(step["key"] == "generate_manifest" for step in cutover_payload["steps"])
        assert cutover_payload["verification_urls"]


def test_business_model_strategy_endpoint_maps_investor_deck() -> None:
    with build_client() as client:
        response = client.get("/api/business-model")
        assert response.status_code == 200
        payload = response.json()["business_model"]
        product_keys = {product["key"] for product in payload["products"]}
        revenue_keys = {stream["key"] for stream in payload["revenue_streams"]}
        strategy_keys = {family["key"] for family in payload["strategy_families"]}

        assert payload["source_deck"] == "BITprivat_Investor_SaaS_Clean_v2.pptx"
        assert {"retail_autopilot", "enterprise_os"}.issubset(product_keys)
        assert {"retail_subscription", "enterprise_arr", "api_usage"}.issubset(revenue_keys)
        assert {"event_dislocation_scanner", "advisor_follow_meta", "template_rotation"}.issubset(strategy_keys)
        assert any(step["key"] == "dynatune_retune" for step in payload["moat_loop"])
        assert payload["seed_raise"] == "$1.5M-2.0M seed for roughly 18 months of runway."
        assert any("Do not promise guaranteed returns" in item for item in payload["compliance_guardrails"])


def test_public_legal_pages_are_served() -> None:
    with build_client() as client:
        portfolio_response = client.get("/portfolio")
        assert portfolio_response.status_code == 200
        assert "autonomous market intelligence" in portfolio_response.text.lower()
        assert "business model strategy" in portfolio_response.text.lower()

        terms_response = client.get("/terms")
        assert terms_response.status_code == 200
        assert "research, analytics, simulations, and monitoring only" in terms_response.text.lower()

        privacy_response = client.get("/privacy")
        assert privacy_response.status_code == 200
        assert "collect the minimum data needed" in privacy_response.text.lower()

        risk_response = client.get("/risk")
        assert risk_response.status_code == 200
        assert "market, model, and platform risk all remain real" in risk_response.text.lower()


def test_professional_console_pages_are_served() -> None:
    with build_client() as client:
        dashboard_response = client.get("/dashboard")
        assert dashboard_response.status_code == 200
        assert 'id="market-console-section"' in dashboard_response.text
        assert 'id="market-console-decisions"' in dashboard_response.text

        simulation_response = client.get("/simulation")
        assert simulation_response.status_code == 200
        assert 'id="simulation-optimization-panel"' in simulation_response.text
        assert 'id="simulation-optimization-list"' in simulation_response.text


def test_sqlite_backup_helper_creates_portable_copy() -> None:
    temp_root = Path(tempfile.mkdtemp())
    try:
        source_path = temp_root / "source.db"
        with sqlite3.connect(source_path) as connection:
            connection.execute("create table sample (id integer primary key, label text)")
            connection.execute("insert into sample (label) values (?)", ("bot-society",))
            connection.commit()

        summary = backup_sqlite_database(source_path, backup_dir=temp_root / "backups")
        assert summary.backup_path.exists()
        assert summary.size_bytes > 0

        with sqlite3.connect(summary.backup_path) as backup_connection:
            row = backup_connection.execute("select label from sample limit 1").fetchone()
        assert row[0] == "bot-society"
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def test_database_copy_tolerates_older_source_schema() -> None:
    temp_root = Path(tempfile.mkdtemp())
    try:
        source_path = temp_root / "legacy.db"
        target_path = temp_root / "target.db"
        with sqlite3.connect(source_path) as connection:
            connection.execute("create table users (slug text primary key, display_name text, email text, tier text, created_at text, password_hash text, is_active integer, is_demo_user integer)")
            connection.execute("insert into users values (?, ?, ?, ?, ?, ?, ?, ?)", ("legacy-user", "Legacy User", "legacy@example.com", "starter", "2026-04-23T00:00:00Z", "", 1, 0))
            connection.execute("create table alembic_version (version_num text not null)")
            connection.execute("insert into alembic_version values (?)", ("legacy",))
            connection.commit()

        summary = copy_database(Database(path=source_path), Database(path=target_path))
        assert summary.copied_rows["users"] == 1
        assert "billing_customers" in summary.copied_rows
        assert summary.copied_rows["billing_customers"] == 0
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


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


def test_v1_routes_and_audit_log_capture_mutations() -> None:
    with build_client() as client:
        register_response = client.post(
            "/api/v1/auth/register",
            json={
                "display_name": "V1 Audit User",
                "email": "v1-audit@example.com",
                "password": "SuperSecure123",
            },
        )
        assert register_response.status_code == 200
        user_slug = register_response.json()["user"]["slug"]

        dashboard_response = client.get("/api/v1/dashboard/summary")
        assert dashboard_response.status_code == 200
        assert dashboard_response.json()["summary"]["active_bots"] == 6

        signals_response = client.get("/api/v1/signals", params={"limit": 3})
        assert signals_response.status_code == 200
        assert len(signals_response.json()) == 3

        watchlist_response = client.post("/api/v1/me/watchlist", json={"asset": "SOL"})
        assert watchlist_response.status_code == 200
        assert any(item["asset"] == "SOL" for item in watchlist_response.json()["watchlist"])

        audit_response = client.get("/api/v1/system/audit", params={"actor_user_slug": user_slug})
        assert audit_response.status_code == 200
        audit_payload = audit_response.json()["audit_logs"]
        actions = {entry["action"] for entry in audit_payload}
        assert {"auth.register", "workspace.watchlist_add"}.issubset(actions)
        watchlist_audit = next(entry for entry in audit_payload if entry["action"] == "workspace.watchlist_add")
        assert watchlist_audit["resource_type"] == "watchlist_item"
        assert watchlist_audit["resource_id"] == "SOL"
        assert watchlist_audit["after_state"]["asset"] == "SOL"


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


def test_stripe_billing_snapshot_checkout_and_portal_flow() -> None:
    settings = Settings(
        fiat_billing_provider="stripe",
        stripe_publishable_key="pk_test_123",
        stripe_secret_key="sk_test_123",
        stripe_basic_price_id="price_basic_123",
        stripe_customer_portal_enabled=True,
    )
    with build_client(settings) as client:
        register_response = client.post(
            "/api/auth/register",
            json={
                "display_name": "Billing User",
                "email": "billing@example.com",
                "password": "SuperSecure123",
            },
        )
        assert register_response.status_code == 200

        billing_response = client.get("/api/me/billing")
        assert billing_response.status_code == 200
        billing_payload = billing_response.json()
        assert billing_payload["provider"] == "stripe"
        assert billing_payload["checkout_ready"] is True
        assert any(plan["key"] == "basic" and plan["configured"] for plan in billing_payload["available_plans"])

        with patch(
            "api.app.services.StripeClient.create_checkout_session",
            return_value={
                "id": "cs_test_123",
                "url": "https://checkout.stripe.com/c/pay/cs_test_123",
                "customer": "cus_test_123",
                "subscription": "sub_test_123",
            },
        ):
            checkout_response = client.post("/api/me/billing/checkout-session", json={"plan_key": "basic"})
        assert checkout_response.status_code == 200
        checkout_payload = checkout_response.json()
        assert checkout_payload["url"].startswith("https://checkout.stripe.com/")
        assert checkout_payload["plan_key"] == "basic"

        billing_after_checkout = client.get("/api/me/billing")
        assert billing_after_checkout.status_code == 200
        billing_after_payload = billing_after_checkout.json()
        assert billing_after_payload["customer_state"] == "linked"
        assert billing_after_payload["subscription_status"] == "checkout_created"
        assert billing_after_payload["portal_ready"] is True

        with patch(
            "api.app.services.StripeClient.create_customer_portal_session",
            return_value={
                "id": "bps_test_123",
                "url": "https://billing.stripe.com/p/session/test_123",
            },
        ):
            portal_response = client.post("/api/me/billing/portal-session", json={"return_path": "/dashboard"})
        assert portal_response.status_code == 200
        assert portal_response.json()["url"].startswith("https://billing.stripe.com/")


def test_stripe_webhook_upgrades_workspace_and_deduplicates_events() -> None:
    settings = Settings(
        fiat_billing_provider="stripe",
        stripe_publishable_key="pk_test_123",
        stripe_secret_key="sk_test_123",
        stripe_webhook_secret="whsec_test_123",
        stripe_basic_price_id="price_basic_123",
        stripe_pro_price_id="price_pro_123",
        stripe_customer_portal_enabled=True,
    )
    with build_client(settings) as client:
        register_response = client.post(
            "/api/auth/register",
            json={
                "display_name": "Webhook User",
                "email": "webhook@example.com",
                "password": "SuperSecure123",
            },
        )
        assert register_response.status_code == 200
        user_slug = register_response.json()["user"]["slug"]

        event = {
            "id": "evt_test_subscription_updated",
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_test_pro",
                    "customer": "cus_test_pro",
                    "status": "active",
                    "cancel_at_period_end": False,
                    "current_period_end": int(time.time()) + 86400,
                    "metadata": {
                        "user_slug": user_slug,
                        "plan_key": "pro",
                    },
                    "items": {
                        "data": [
                            {
                                "price": {
                                    "id": "price_pro_123",
                                }
                            }
                        ]
                    },
                }
            },
        }
        signature, body = stripe_signature(settings.stripe_webhook_secret or "", event)
        webhook_response = client.post(
            "/api/webhooks/stripe",
            content=body,
            headers={"stripe-signature": signature},
        )
        assert webhook_response.status_code == 200
        assert webhook_response.json()["event_type"] == "customer.subscription.updated"
        assert webhook_response.json()["duplicate"] is False

        duplicate_response = client.post(
            "/api/webhooks/stripe",
            content=body,
            headers={"stripe-signature": signature},
        )
        assert duplicate_response.status_code == 200
        assert duplicate_response.json()["duplicate"] is True

        me_response = client.get("/api/me")
        assert me_response.status_code == 200
        me_payload = me_response.json()
        assert me_payload["tier"] == "pro"
        assert me_payload["billing"]["plan_key"] == "pro"
        assert me_payload["billing"]["has_active_subscription"] is True


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


def test_wallet_and_edge_endpoints_expose_research_context() -> None:
    with build_client() as client:
        wallet_response = client.get("/api/wallet-intelligence")
        assert wallet_response.status_code == 200
        wallet_payload = wallet_response.json()
        assert wallet_payload["wallets"]
        assert wallet_payload["wallets"][0]["smart_money_score"] >= 0

        edge_response = client.get("/api/edge")
        assert edge_response.status_code == 200
        edge_payload = edge_response.json()
        assert edge_payload["opportunities"]
        assert edge_payload["opportunities"][0]["asset"] in {"BTC", "ETH", "SOL"}
        assert edge_payload["opportunities"][0]["supporting_signals"]


def test_strategy_lab_advanced_export_packages_context() -> None:
    settings = Settings(simulation_live_history=False)
    with build_client(settings) as client:
        export_response = client.post(
            "/api/simulation/advanced-export",
            json={
                "asset": "BTC",
                "lookback_years": 1,
                "strategy_id": "trend_follow",
                "starting_capital": 10000,
                "fee_bps": 10,
                "fast_window": 2,
                "slow_window": 4,
                "mean_window": 3,
                "breakout_window": 3,
            },
        )
        assert export_response.status_code == 200
        export_payload = export_response.json()
        assert export_payload["engine_target"] == "prediction-market-backtesting"
        assert export_payload["asset"] == "BTC"
        assert export_payload["filename"].endswith(".json")
        assert export_payload["saved_to_disk"] is True
        assert export_payload["download_url"].endswith(export_payload["filename"])
        assert Path(export_payload["filesystem_path"]).exists()
        assert export_payload["package_filename"].endswith(".zip")
        assert export_payload["package_download_url"].endswith(export_payload["package_filename"])
        assert Path(export_payload["package_filesystem_path"]).exists()
        assert export_payload["payload"]["metadata"]["asset"] == "BTC"
        assert export_payload["payload"]["simulation_result"]["selected_result"]["strategy_id"] == "trend_follow"
        assert "wallet_context" in export_payload["payload"]
        assert "macro_context" in export_payload["payload"]
        assert "prediction_market_adapter" in export_payload["payload"]


def test_strategy_lab_export_artifact_routes_expose_saved_bundles() -> None:
    settings = Settings(simulation_live_history=False)
    with build_client(settings) as client:
        export_response = client.post(
            "/api/simulation/advanced-export",
            json={
                "asset": "ETH",
                "lookback_years": 2,
                "strategy_id": "mean_reversion",
                "starting_capital": 15000,
                "fee_bps": 12,
                "fast_window": 3,
                "slow_window": 6,
                "mean_window": 5,
                "breakout_window": 8,
            },
        )
        assert export_response.status_code == 200
        export_payload = export_response.json()

        history_response = client.get("/api/simulation/exports")
        assert history_response.status_code == 200
        history_payload = history_response.json()
        assert history_payload
        saved_artifact = next(item for item in history_payload if item["filename"] == export_payload["filename"])
        assert saved_artifact["asset"] == "ETH"
        assert saved_artifact["strategy_id"] == "mean_reversion"
        assert saved_artifact["download_url"] == export_payload["download_url"]
        assert saved_artifact["package_download_url"] == export_payload["package_download_url"]

        download_response = client.get(export_payload["download_url"])
        assert download_response.status_code == 200
        assert "application/json" in download_response.headers["content-type"]
        download_payload = download_response.json()
        assert download_payload["metadata"]["asset"] == "ETH"
        assert download_payload["metadata"]["lookback_years"] == 2
        assert download_payload["simulation_result"]["selected_result"]["strategy_id"] == "mean_reversion"

        package_response = client.get(export_payload["package_download_url"])
        assert package_response.status_code == 200
        assert "application/zip" in package_response.headers["content-type"]
        with zipfile.ZipFile(BytesIO(package_response.content)) as archive:
            names = set(archive.namelist())
            assert any(name.endswith("/README.md") for name in names)
            assert any(name.endswith("/runner_template.py") for name in names)
            assert any(name.endswith("/strategy_config.json") for name in names)
            readme_name = next(name for name in names if name.endswith("/README.md"))
            runner_name = next(name for name in names if name.endswith("/runner_template.py"))
            strategy_config_name = next(name for name in names if name.endswith("/strategy_config.json"))
            assert "asset-level Bot Society Markets simulation" in archive.read(readme_name).decode("utf-8")
            assert "QuoteReplay" in archive.read(runner_name).decode("utf-8")
            assert "QuoteTickMeanReversionStrategy" in archive.read(strategy_config_name).decode("utf-8")


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


def test_paper_venue_endpoint_exposes_activation_map() -> None:
    with build_client() as client:
        response = client.get("/api/paper-venues")
        assert response.status_code == 200
        payload = response.json()
        assert payload["execution_provider_mode"] == "internal"
        assert payload["recommended_venue_id"] == "polysandbox"
        assert payload["ready_venues"] >= 2
        venues = {venue["id"]: venue for venue in payload["venues"]}
        assert venues["internal"]["status"] == "ready"
        assert venues["polysandbox"]["status"] == "needs_credentials"
        assert venues["polysandbox"]["api_base_url"] == "https://api.polysandbox.trade/v1"
        assert venues["kalshi_demo"]["api_base_url"] == "https://demo-api.kalshi.co/trade-api/v2"
        assert venues["hyperliquid_testnet"]["api_base_url"] == "https://api.hyperliquid-testnet.xyz"
        assert payload["activation_sequence"]
        assert payload["safety_rules"]


def test_configured_paper_venues_become_api_ready() -> None:
    settings = Settings(
        paper_execution_provider="polysandbox",
        polysandbox_api_key="paper-key",
        polysandbox_sandbox_id="sandbox-id",
        kalshi_demo_key_id="demo-key-id",
        kalshi_demo_private_key_path="C:/secrets/kalshi-demo.pem",
    )
    with build_client(settings) as client:
        response = client.get("/api/paper-venues")
        assert response.status_code == 200
        payload = response.json()
        assert payload["execution_provider_mode"] == "polysandbox"
        assert payload["recommended_venue_id"] == "polysandbox"
        venues = {venue["id"]: venue for venue in payload["venues"]}
        assert venues["polysandbox"]["status"] == "ready"
        assert venues["polysandbox"]["configured"] is True
        assert venues["kalshi_demo"]["status"] == "ready"
        assert payload["api_ready_venues"] >= 3


def test_trading_order_contract_records_internal_paper_order() -> None:
    with build_client() as client:
        register_response = client.post(
            "/api/v1/auth/register",
            json={
                "display_name": "Paper Order User",
                "email": "paper-order@example.com",
                "password": "SuperSecure123",
            },
        )
        assert register_response.status_code == 200
        user_slug = register_response.json()["user"]["slug"]

        order_response = client.post(
            "/api/v1/trading/orders",
            json={
                "venue": "paper",
                "asset": "BTC",
                "side": "buy",
                "order_type": "market",
                "notional_usd": 500,
                "client_order_id": "test-paper-order-1",
            },
        )
        assert order_response.status_code == 200
        order = order_response.json()
        assert order["user_slug"] == user_slug
        assert order["venue"] == "paper"
        assert order["asset"] == "BTC"
        assert order["status"] == "filled"
        assert order["filled_quantity"] > 0
        assert order["avg_fill_price"] > 0
        assert order["fee"] > 0
        assert order["metadata"]["execution_mode"] == "internal-paper"

        with client.app.state.bot_society_service.database.connect() as connection:
            stored_count = connection.exec_driver_sql(
                "SELECT COUNT(*) FROM orders WHERE user_slug = ? AND id = ?",
                (user_slug, order["id"]),
            ).scalar_one()
        assert stored_count == 1

        list_response = client.get("/api/v1/trading/orders")
        assert list_response.status_code == 200
        assert list_response.json()[0]["id"] == order["id"]

        detail_response = client.get(f"/api/v1/trading/orders/{order['id']}")
        assert detail_response.status_code == 200
        assert detail_response.json()["exchange_order_id"].startswith("paper-")

        live_response = client.post(
            "/api/v1/trading/orders",
            json={
                "venue": "polymarket",
                "asset": "BTC",
                "side": "buy",
                "order_type": "market",
                "notional_usd": 100,
                "is_paper": False,
            },
        )
        assert live_response.status_code == 400
        assert "Live execution is disabled" in live_response.json()["detail"]

        audit_response = client.get("/api/v1/system/audit", params={"actor_user_slug": user_slug})
        assert audit_response.status_code == 200
        actions = {entry["action"] for entry in audit_response.json()["audit_logs"]}
        assert "trading.order_place" in actions


def test_strategy_lab_config_and_run_support_local_backtests() -> None:
    settings = Settings(simulation_live_history=False)
    with build_client(settings) as client:
        config_response = client.get("/api/simulation/config")
        assert config_response.status_code == 200
        config_payload = config_response.json()
        assert "BTC" in config_payload["available_assets"]
        assert config_payload["strategy_presets"]
        assert config_payload["default_strategy_id"] == "custom_creator"
        assert any(preset["strategy_id"] == "custom_creator" for preset in config_payload["strategy_presets"])
        assert any(source["mode"] == "auto" for source in config_payload["data_source_options"])
        assert any(source["mode"] == "local" for source in config_payload["data_source_options"])
        assert config_payload["live_history_capable"] is False

        run_response = client.post(
            "/api/simulation/run",
            json={
                "asset": "BTC",
                "history_source_mode": "local",
                "lookback_years": 1,
                "strategy_id": "custom_creator",
                "custom_strategy_name": "Night Builder",
                "starting_capital": 10000,
                "fee_bps": 10,
                "fast_window": 2,
                "slow_window": 4,
                "mean_window": 3,
                "breakout_window": 4,
                "creator_trend_weight": 1.2,
                "creator_mean_reversion_weight": 0.8,
                "creator_breakout_weight": 1.0,
                "creator_entry_score": 0.45,
                "creator_exit_score": 0.25,
                "creator_max_exposure": 0.75,
                "creator_pullback_entry_pct": 0.02,
                "creator_stop_loss_pct": 0.08,
                "creator_take_profit_pct": 0.2,
            },
        )
        assert run_response.status_code == 200
        run_payload = run_response.json()
        assert run_payload["asset"] == "BTC"
        assert run_payload["data_source"] == "local-archive"
        assert run_payload["selected_result"]["strategy_id"] == "custom_creator"
        assert run_payload["selected_result"]["label"] == "Night Builder"
        assert "Night Builder" in run_payload["selected_result"]["summary"]
        assert run_payload["selected_result"]["equity_curve"]
        assert run_payload["benchmark_curve"]
        assert run_payload["leaderboard"]
        assert any(entry["strategy_id"] == "custom_creator" for entry in run_payload["leaderboard"])


def test_strategy_lab_persists_strategies_and_backtest_runs() -> None:
    settings = Settings(simulation_live_history=False)
    strategy_config = {
        "asset": "BTC",
        "history_source_mode": "local",
        "lookback_years": 1,
        "strategy_id": "custom_creator",
        "custom_strategy_name": "Vault Builder",
        "starting_capital": 12000,
        "fee_bps": 8,
        "fast_window": 2,
        "slow_window": 4,
        "mean_window": 3,
        "breakout_window": 4,
        "creator_trend_weight": 1.2,
        "creator_mean_reversion_weight": 0.7,
        "creator_breakout_weight": 1.0,
        "creator_entry_score": 0.45,
        "creator_exit_score": 0.25,
        "creator_max_exposure": 0.75,
        "creator_pullback_entry_pct": 0.02,
        "creator_stop_loss_pct": 0.08,
        "creator_take_profit_pct": 0.2,
    }

    with build_client(settings) as client:
        register_response = client.post(
            "/api/v1/auth/register",
            json={
                "display_name": "Strategy Owner",
                "email": "strategy-owner@example.com",
                "password": "SuperSecure123",
            },
        )
        assert register_response.status_code == 200
        user_slug = register_response.json()["user"]["slug"]

        create_response = client.post(
            "/api/v1/strategies",
            json={
                "name": "Vault Builder",
                "description": "Persisted creator blend candidate.",
                "config": strategy_config,
            },
        )
        assert create_response.status_code == 200
        strategy = create_response.json()
        assert strategy["id"] >= 1
        assert strategy["user_slug"] == user_slug
        assert strategy["config"]["asset"] == "BTC"
        assert strategy["config"]["custom_strategy_name"] == "Vault Builder"

        list_response = client.get("/api/v1/strategies")
        assert list_response.status_code == 200
        assert [item["id"] for item in list_response.json()] == [strategy["id"]]

        update_response = client.put(
            f"/api/v1/strategies/{strategy['id']}",
            json={"name": "Vault Builder Prime"},
        )
        assert update_response.status_code == 200
        assert update_response.json()["name"] == "Vault Builder Prime"

        run_response = client.post(f"/api/v1/strategies/{strategy['id']}/backtest", json={})
        assert run_response.status_code == 200
        run_payload = run_response.json()
        assert run_payload["strategy_id"] == strategy["id"]
        assert run_payload["status"] == "complete"
        assert run_payload["summary"]["strategy_name"] == "Vault Builder Prime"
        assert run_payload["summary"]["asset"] == "BTC"
        assert run_payload["result"]["selected_result"]["strategy_id"] == "custom_creator"

        runs_response = client.get("/api/v1/strategies/backtests")
        assert runs_response.status_code == 200
        assert runs_response.json()[0]["id"] == run_payload["id"]

        run_detail_response = client.get(f"/api/v1/strategies/backtests/{run_payload['id']}")
        assert run_detail_response.status_code == 200
        assert run_detail_response.json()["summary"]["final_equity"] == run_payload["summary"]["final_equity"]

        delete_response = client.delete(f"/api/v1/strategies/{strategy['id']}")
        assert delete_response.status_code == 200
        assert delete_response.json()["is_active"] is False

        post_delete_list_response = client.get("/api/v1/strategies")
        assert post_delete_list_response.status_code == 200
        assert post_delete_list_response.json() == []

        audit_response = client.get("/api/v1/system/audit", params={"actor_user_slug": user_slug})
        assert audit_response.status_code == 200
        actions = {entry["action"] for entry in audit_response.json()["audit_logs"]}
        assert {
            "strategy.create",
            "strategy.update",
            "strategy.backtest_run",
            "strategy.delete",
        }.issubset(actions)


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


def test_wallet_provider_configuration_metadata() -> None:
    settings = Settings(
        wallet_provider_mode="polymarket",
        tracked_wallets=("0x1111111111111111111111111111111111111111",),
    )
    with build_client(settings) as client:
        provider_response = client.get("/api/system/providers")
        assert provider_response.status_code == 200
        provider_payload = provider_response.json()["provider_status"]
        assert provider_payload["wallet_provider_mode"] == "polymarket"
        assert provider_payload["wallet_provider_configured"] is True
        assert provider_payload["wallet_provider_live_capable"] is True
        assert provider_payload["wallet_provider_ready"] is True
        assert provider_payload["tracked_wallets"] == ["0x1111111111111111111111111111111111111111"]


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


def test_launch_readiness_endpoint_reflects_provider_and_governance_state() -> None:
    settings = Settings(
        fiat_billing_provider="stripe",
        stripe_publishable_key="pk_test_123",
        stripe_secret_key="sk_test_123",
        stripe_webhook_secret="whsec_123",
        stripe_basic_price_id="price_basic_123",
        crypto_onramp_provider="coinbase",
        coinbase_onramp_api_key="coinbase-key",
        coinbase_onramp_app_id="app-123",
        crypto_checkout_provider="coinbase_commerce",
        coinbase_commerce_api_key="commerce-key",
        desktop_app_framework="tauri",
        desktop_bundle_id="com.bitprivat.bot-society-markets",
        apple_developer_team_id="TEAM12345",
        legal_entity_name="BitPrivat Labs SRL",
        legal_primary_jurisdiction="Romania",
        privacy_contact_email="privacy@bitprivat.com",
        terms_url="https://app.bitprivat.com/legal/terms",
        privacy_url="https://app.bitprivat.com/legal/privacy",
        risk_disclosure_url="https://app.bitprivat.com/legal/risk",
        aml_program_owner="Head of Operations",
        market_provider_mode="hyperliquid",
        macro_provider_mode="fred",
        fred_api_key="fred-key",
        wallet_provider_mode="polymarket",
        tracked_wallets=("0x1111111111111111111111111111111111111111",),
        venue_signal_providers=("polymarket", "kalshi"),
    )
    with build_client(settings) as client:
        response = client.get("/api/system/launch-readiness")
        assert response.status_code == 200
        payload = response.json()["launch_readiness"]
        assert payload["level"] in {"building", "ready", "live"}
        track_lookup = {track["key"]: track for track in payload["tracks"]}
        assert track_lookup["fiat_onboarding"]["level"] == "ready"
        assert track_lookup["crypto_onboarding"]["level"] == "ready"
        assert track_lookup["desktop_apps"]["level"] == "ready"
        assert track_lookup["legal_compliance"]["level"] == "ready"
        assert track_lookup["api_connectors"]["level"] in {"ready", "live"}


def test_status_page_route_serves_html() -> None:
    with build_client() as client:
        response = client.get("/status")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Public status" in response.text


def test_home_route_can_open_dashboard_for_custom_domain() -> None:
    with build_client(Settings(site_home_page="dashboard")) as client:
        home_response = client.get("/")
        assert home_response.status_code == 200
        assert "text/html" in home_response.headers["content-type"]
        assert "Command Center" in home_response.text

        landing_response = client.get("/landing")
        assert landing_response.status_code == 200
        assert "Connect real markets, test strategy logic" in landing_response.text


def test_canonical_host_redirects_root_domain_to_https_app_domain() -> None:
    settings = Settings(
        site_home_page="dashboard",
        canonical_host="app.bitprivat.com",
        canonical_redirect_hosts=("bitprivat.com", "www.bitprivat.com"),
        force_https=True,
    )
    with build_client(settings) as client:
        response = client.get(
            "/dashboard?view=live",
            headers={"host": "bitprivat.com", "x-forwarded-proto": "http"},
            follow_redirects=False,
        )
        assert response.status_code == 308
        assert response.headers["location"] == "https://app.bitprivat.com/dashboard?view=live"


def test_production_hosts_support_apex_api_and_status_routes() -> None:
    settings = Settings(
        site_home_page="dashboard",
        canonical_host="bitprivat.com",
        canonical_redirect_hosts=("www.bitprivat.com", "app.bitprivat.com"),
        force_https=True,
    )
    with build_client(settings) as client:
        app_redirect = client.get(
            "/dashboard",
            headers={"host": "app.bitprivat.com", "x-forwarded-proto": "https"},
            follow_redirects=False,
        )
        assert app_redirect.status_code == 308
        assert app_redirect.headers["location"] == "https://bitprivat.com/dashboard"

        status_response = client.get(
            "/",
            headers={"host": "status.bitprivat.com", "x-forwarded-proto": "https"},
        )
        assert status_response.status_code == 200
        assert "Public status and live systems posture" in status_response.text

        api_response = client.get(
            "/api/v1/system/pulse",
            headers={"host": "api.bitprivat.com", "x-forwarded-proto": "https"},
        )
        assert api_response.status_code == 200
        assert "system_pulse" in api_response.json()


def test_force_https_redirects_canonical_host_and_sets_secure_cookie() -> None:
    settings = Settings(
        canonical_host="app.bitprivat.com",
        force_https=True,
    )
    with build_client(settings) as client:
        redirect_response = client.get(
            "/",
            headers={"host": "app.bitprivat.com", "x-forwarded-proto": "http"},
            follow_redirects=False,
        )
        assert redirect_response.status_code == 308
        assert redirect_response.headers["location"] == "https://app.bitprivat.com/"

        register_response = client.post(
            "/api/auth/register",
            headers={"host": "app.bitprivat.com", "x-forwarded-proto": "https"},
            json={
                "display_name": "Secure User",
                "email": "secure@example.com",
                "password": "SuperSecure123",
            },
        )
        assert register_response.status_code == 200
        assert "secure" in register_response.headers["set-cookie"].lower()


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
        assert max(signal["source_quality_score"] for signal in payload) >= 0.6
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
