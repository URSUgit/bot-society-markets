from __future__ import annotations

import json
import ssl
import time
from typing import Any
from urllib.parse import urlencode

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

    def _gateway_request(
        self,
        path: str,
        *,
        method: str = "GET",
        params: dict[str, Any] | None = None,
        body: Any | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        url = f"{self.client_portal_base_url}/{path.lstrip('/')}"
        if params:
            query = urlencode({key: value for key, value in params.items() if value is not None})
            if query:
                url = f"{url}?{query}"
        request_headers = {"Accept": "application/json"}
        if headers:
            request_headers.update(headers)
        request_body: bytes | None = None
        if body is not None:
            request_headers.setdefault("Content-Type", "application/json")
            if isinstance(body, (bytes, bytearray)):
                request_body = bytes(body)
            elif isinstance(body, str):
                request_body = body.encode("utf-8")
            else:
                request_body = json.dumps(body).encode("utf-8")
        return self.requester(
            url=url,
            method=method,
            headers=request_headers,
            body=request_body,
            timeout_seconds=self.timeout_seconds,
            ssl_context=ssl._create_unverified_context(),
        )

    def _ensure_brokerage_session(self) -> None:
        status = self._gateway_request("/iserver/auth/status")
        if not isinstance(status, dict) or not (status.get("authenticated") and status.get("connected")):
            raise ExchangeConnectionError(
                "Interactive Brokers Client Portal Gateway is not authenticated. Log into the gateway and retry."
            )
        self._gateway_request("/iserver/auth/ssodh/init", method="POST", body={})

    def _selected_account(self, account_id: str | None = None) -> str:
        accounts = self._gateway_request("/iserver/accounts")
        account_items = accounts if isinstance(accounts, list) else accounts.get("accounts", []) if isinstance(accounts, dict) else []
        selected_account = (
            account_id
            or self.account_id
            or next(
                (
                    str(item.get("accountId") or item.get("id") or "").strip()
                    for item in account_items
                    if str(item.get("accountId") or item.get("id") or "").strip()
                ),
                "",
            )
        ).strip()
        if not selected_account:
            raise ExchangeConnectionError("Interactive Brokers gateway returned no accessible accounts")
        if account_id and not any(
            str(item.get("accountId") or item.get("id") or "").strip() == account_id for item in account_items
        ):
            raise ExchangeConnectionError(
                f"Interactive Brokers account {account_id} was not returned by the gateway session"
            )
        return selected_account

    def _lookup_contract(self, symbol: str, *, security_type: str = "STK") -> dict[str, Any]:
        results = self._gateway_request(
            "/iserver/secdef/search",
            params={"symbol": symbol, "secType": security_type},
        )
        candidates = results if isinstance(results, list) else results.get("results", []) if isinstance(results, dict) else []
        if not candidates:
            raise ExchangeConnectionError(f"Interactive Brokers returned no contract for {symbol}")
        normalized_symbol = symbol.strip().upper()
        for candidate in candidates:
            if str(candidate.get("symbol") or "").strip().upper() == normalized_symbol:
                return candidate
        return candidates[0]

    def _confirm_order_reply(self, reply_id: str) -> Any:
        return self._gateway_request(f"/iserver/reply/{reply_id}", method="POST", body={"confirmed": True})

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
            warning_bits.append("Read-only mode is disabled in settings, and live order routing is available.")
        if self.live_trading_enabled:
            warning_bits.append("Live trading is enabled in settings; verify the account is a paper or approved live account.")
        if self.market_data_subscribed:
            warning_bits.append("Market data subscription is enabled separately from this account probe.")

        return self._result(
            balances,
            account_mode="client_portal",
            permissions=["read", "accounts.read", "portfolio.read", "positions.read", "trade.write" if self.live_trading_enabled and not self.read_only else "read"],
            warning=" ".join(warning_bits) or None,
        )

    def place_market_order(
        self,
        *,
        symbol: str,
        side: str,
        quantity: float,
        account_id: str | None = None,
        security_type: str = "STK",
    ) -> dict[str, Any]:
        if self.connection_mode != "client_portal":
            raise ExchangeConnectionError(
                "Interactive Brokers live order routing currently uses the Client Portal Gateway."
            )
        if self.read_only:
            raise ExchangeConnectionError("Interactive Brokers live order routing is disabled by read-only mode")
        if not self.live_trading_enabled:
            raise ExchangeConnectionError("Interactive Brokers live order routing is disabled in settings")

        self._ensure_brokerage_session()
        selected_account = self._selected_account(account_id)
        contract = self._lookup_contract(symbol, security_type=security_type)
        conid = int(contract.get("conid") or 0)
        if conid <= 0:
            raise ExchangeConnectionError(f"Interactive Brokers returned an invalid conid for {symbol}")

        order_ticket = {
            "conid": conid,
            "side": side.upper(),
            "orderType": "MKT",
            "quantity": float(quantity),
            "tif": "DAY",
        }
        submission = self._gateway_request(
            f"/iserver/account/{selected_account}/orders",
            method="POST",
            body=[order_ticket],
        )
        if isinstance(submission, list) and submission:
            first = submission[0] if isinstance(submission[0], dict) else {}
            reply_id = str(first.get("id") or first.get("replyId") or first.get("reply_id") or "").strip()
            if reply_id and not first.get("order_id"):
                submission = self._confirm_order_reply(reply_id)

        order_id: str | None = None
        order_status: str | None = None
        if isinstance(submission, list) and submission:
            first = submission[0] if isinstance(submission[0], dict) else {}
            order_id = str(first.get("order_id") or first.get("orderId") or "").strip() or None
            order_status = str(first.get("order_status") or first.get("status") or "").strip() or None
        status_detail: Any = None
        if order_id:
            try:
                status_detail = self._gateway_request(f"/iserver/account/order/status/{order_id}")
            except ExchangeConnectionError:
                status_detail = None

        return {
            "account_id": selected_account,
            "conid": conid,
            "symbol": symbol.upper(),
            "order_id": order_id,
            "order_status": order_status,
            "submission": submission,
            "status_detail": status_detail,
        }

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
