from __future__ import annotations

import ssl
from typing import Any

from .exchange_connectors import (
    ExchangeBalance,
    ExchangeConnectionError,
    ExchangeConnectionResult,
    ExchangeConnector,
)


def _float_value(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


class InteractiveBrokersClientPortalConnector(ExchangeConnector):
    exchange_id = "interactivebrokers"
    label = "Interactive Brokers"
    docs_url = "https://ibkrcampus.com/campus/ibkr-api-page/webapi-doc/"
    env_keys = (
        "BSM_IBKR_CONNECTION_MODE",
        "BSM_IBKR_ACCOUNT_ID",
        "BSM_IBKR_CLIENT_PORTAL_BASE_URL",
        "BSM_IBKR_READ_ONLY",
        "BSM_IBKR_LIVE_TRADING_ENABLED",
        "BSM_IBKR_MARKET_DATA_SUBSCRIBED",
    )

    def __init__(
        self,
        *,
        connection_mode: str,
        account_id: str | None,
        client_portal_base_url: str,
        read_only: bool,
        live_trading_enabled: bool,
        market_data_subscribed: bool,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.connection_mode = connection_mode.strip().lower()
        self.account_id = (account_id or "").strip()
        self.client_portal_base_url = client_portal_base_url.rstrip("/")
        self.read_only = read_only
        self.live_trading_enabled = live_trading_enabled
        self.market_data_subscribed = market_data_subscribed

    @property
    def configured(self) -> bool:
        return self.connection_mode == "client_portal" and bool(self.account_id and self.client_portal_base_url)

    def _gateway_request(self, path: str) -> Any:
        return self.requester(
            url=f"{self.client_portal_base_url}/{path.lstrip('/')}",
            headers={"Accept": "application/json"},
            timeout_seconds=self.timeout_seconds,
            ssl_context=ssl._create_unverified_context(),
        )

    @staticmethod
    def _summary_metric(summary: Any, asset: str, *keys: str) -> ExchangeBalance | None:
        if not isinstance(summary, dict):
            return None
        normalized = {str(key).lower(): value for key, value in summary.items()}
        for key in keys:
            value = normalized.get(key.lower())
            if isinstance(value, dict):
                amount = _float_value(value.get("amount") or value.get("value"))
                if amount or value.get("isNull") is False:
                    return ExchangeBalance(asset=asset, total=amount, available=amount, locked=0.0)
            elif value not in (None, ""):
                amount = _float_value(value)
                if amount:
                    return ExchangeBalance(asset=asset, total=amount, available=amount, locked=0.0)
        return None

    def _summary_balances(self, summary: Any) -> list[ExchangeBalance]:
        balances = [
            self._summary_metric(summary, "NET_LIQUIDATION", "netliquidation", "netliquidationvalue", "equitywithloanvalue"),
            self._summary_metric(summary, "AVAILABLE_FUNDS", "availablefunds"),
            self._summary_metric(summary, "BUYING_POWER", "buyingpower", "availablebuyingpower"),
            self._summary_metric(summary, "CASH_BALANCE", "cashbalance", "settledcash"),
            self._summary_metric(summary, "EXCESS_LIQUIDITY", "excessliquidity"),
        ]
        return [balance for balance in balances if balance]

    def connection_result(self) -> ExchangeConnectionResult:
        if self.connection_mode != "client_portal":
            raise ExchangeConnectionError(
                "Interactive Brokers account access currently uses the Client Portal Gateway. "
                "Set BSM_IBKR_CONNECTION_MODE=client_portal and point BSM_IBKR_CLIENT_PORTAL_BASE_URL at the gateway."
            )

        status = self._gateway_request("/iserver/auth/status")
        if not (status.get("authenticated") and status.get("connected")):
            raise ExchangeConnectionError(
                "Interactive Brokers Client Portal Gateway is not authenticated. Log into the gateway and retry."
            )

        accounts = self._gateway_request("/portfolio/accounts")
        account_items = accounts if isinstance(accounts, list) else accounts.get("accounts", []) if isinstance(accounts, dict) else []
        selected_account = self.account_id or next(
            (
                str(item.get("accountId") or item.get("id") or "").strip()
                for item in account_items
                if str(item.get("accountId") or item.get("id") or "").strip()
            ),
            "",
        )
        if not selected_account:
            raise ExchangeConnectionError("Interactive Brokers gateway returned no accessible accounts")
        if self.account_id and not any(
            str(item.get("accountId") or item.get("id") or "").strip() == self.account_id for item in account_items
        ):
            raise ExchangeConnectionError(
                f"Interactive Brokers account {self.account_id} was not returned by the gateway session"
            )

        summary = self._gateway_request(f"/portfolio/{selected_account}/summary")
        try:
            positions = self._gateway_request(f"/portfolio/{selected_account}/positions/0")
        except ExchangeConnectionError:
            positions = []

        balances = self._summary_balances(summary)
        if isinstance(positions, list) and positions:
            balances.append(
                ExchangeBalance(
                    asset="POSITIONS",
                    total=float(len(positions)),
                    available=float(len(positions)),
                    locked=0.0,
                )
            )

        warning_bits: list[str] = []
        if not self.read_only:
            warning_bits.append("Read-only mode is disabled in settings, but this connector only reads account data.")
        if self.live_trading_enabled:
            warning_bits.append("Live trading is enabled in settings, but order routing is not implemented yet.")
        if self.market_data_subscribed:
            warning_bits.append("Market data subscription is enabled separately from this account probe.")

        return self._result(
            balances,
            account_mode="client_portal",
            permissions=["read", "accounts.read", "portfolio.read", "positions.read"],
            warning=" ".join(warning_bits) or None,
        )
