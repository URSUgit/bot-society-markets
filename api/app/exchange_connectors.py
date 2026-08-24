from __future__ import annotations

import base64
import hashlib
import hmac
import json
import ssl
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


JsonRequester = Callable[..., Any]


class ExchangeConnectionError(RuntimeError):
    """A sanitized exchange connectivity or authentication failure."""


@dataclass(slots=True)
class ExchangeBalance:
    asset: str
    total: float
    available: float
    locked: float


@dataclass(slots=True)
class ExchangeConnectionResult:
    exchange_id: str
    label: str
    connected: bool
    checked_at: str
    account_mode: str
    read_only: bool = True
    balances: list[ExchangeBalance] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    warning: str | None = None


def _float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _non_zero_balance(asset: str, total: Any, available: Any, locked: Any) -> ExchangeBalance | None:
    parsed_total = _float(total)
    parsed_available = _float(available)
    parsed_locked = _float(locked)
    if max(abs(parsed_total), abs(parsed_available), abs(parsed_locked)) <= 1e-12:
        return None
    return ExchangeBalance(
        asset=str(asset).upper(),
        total=parsed_total,
        available=parsed_available,
        locked=parsed_locked,
    )


def _request_json(
    *,
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    timeout_seconds: int = 10,
    ssl_context: ssl.SSLContext | None = None,
) -> Any:
    request = Request(url, data=body, headers=headers or {}, method=method)
    try:
        with urlopen(request, timeout=timeout_seconds, context=ssl_context) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = ""
        try:
            payload = json.loads(exc.read().decode("utf-8"))
            detail = str(payload.get("msg") or payload.get("message") or payload.get("retMsg") or "")
            if not detail and isinstance(payload.get("error"), list):
                detail = "; ".join(str(item) for item in payload["error"])
        except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
            pass
        suffix = f": {detail[:180]}" if detail else ""
        raise ExchangeConnectionError(f"Exchange returned HTTP {exc.code}{suffix}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise ExchangeConnectionError("Exchange API could not be reached before the timeout") from exc
    except json.JSONDecodeError as exc:
        raise ExchangeConnectionError("Exchange returned an invalid JSON response") from exc


class ExchangeConnector:
    exchange_id = "exchange"
    label = "Exchange"
    docs_url = ""
    env_keys: tuple[str, ...] = ()

    def __init__(self, *, timeout_seconds: int, requester: JsonRequester = _request_json) -> None:
        self.timeout_seconds = timeout_seconds
        self.requester = requester

    @property
    def configured(self) -> bool:
        raise NotImplementedError

    def connection_result(self) -> ExchangeConnectionResult:
        raise NotImplementedError

    def _result(
        self,
        balances: list[ExchangeBalance],
        *,
        account_mode: str,
        permissions: list[str] | None = None,
        warning: str | None = None,
    ) -> ExchangeConnectionResult:
        balances.sort(key=lambda item: (-abs(item.total), item.asset))
        return ExchangeConnectionResult(
            exchange_id=self.exchange_id,
            label=self.label,
            connected=True,
            checked_at=datetime.now(timezone.utc).isoformat(),
            account_mode=account_mode,
            balances=balances,
            permissions=permissions or ["read"],
            warning=warning,
        )


class BinanceAccountConnector(ExchangeConnector):
    exchange_id = "binance"
    label = "Binance"
    docs_url = "https://developers.binance.com/docs/binance-spot-api-docs/rest-api/account-endpoints"
    env_keys = ("BSM_BINANCE_API_KEY", "BSM_BINANCE_API_SECRET")

    def __init__(self, *, api_key: str | None, api_secret: str | None, base_url: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.api_key = api_key or ""
        self.api_secret = api_secret or ""
        self.base_url = base_url.rstrip("/")

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.api_secret)

    def connection_result(self) -> ExchangeConnectionResult:
        timestamp = str(int(time.time() * 1000))
        query = urlencode({"recvWindow": 5000, "timestamp": timestamp})
        signature = hmac.new(self.api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()
        payload = self.requester(
            url=f"{self.base_url}/api/v3/account?{query}&signature={signature}",
            headers={"X-MBX-APIKEY": self.api_key, "Accept": "application/json"},
            timeout_seconds=self.timeout_seconds,
        )
        balances = []
        for item in payload.get("balances", []):
            balance = _non_zero_balance(
                item.get("asset", ""),
                _float(item.get("free")) + _float(item.get("locked")),
                item.get("free"),
                item.get("locked"),
            )
            if balance:
                balances.append(balance)
        permissions = ["read"]
        if payload.get("canTrade"):
            permissions.append("trade-enabled-at-exchange")
        warning = "Disable withdrawal permission on this API key." if payload.get("canWithdraw") else None
        return self._result(balances, account_mode="spot", permissions=permissions, warning=warning)


class CoinbaseExchangeAccountConnector(ExchangeConnector):
    exchange_id = "coinbase"
    label = "Coinbase Exchange"
    docs_url = "https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/accounts/get-all-account-profile"
    env_keys = (
        "BSM_COINBASE_EXCHANGE_API_KEY",
        "BSM_COINBASE_EXCHANGE_API_SECRET",
        "BSM_COINBASE_EXCHANGE_PASSPHRASE",
    )

    def __init__(
        self,
        *,
        api_key: str | None,
        api_secret: str | None,
        passphrase: str | None,
        base_url: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.api_key = api_key or ""
        self.api_secret = api_secret or ""
        self.passphrase = passphrase or ""
        self.base_url = base_url.rstrip("/")

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.api_secret and self.passphrase)

    def connection_result(self) -> ExchangeConnectionResult:
        timestamp = str(time.time())
        path = "/accounts"
        try:
            secret = base64.b64decode(self.api_secret)
        except ValueError as exc:
            raise ExchangeConnectionError("Coinbase Exchange API secret is not valid base64") from exc
        signature = base64.b64encode(
            hmac.new(secret, f"{timestamp}GET{path}".encode(), hashlib.sha256).digest()
        ).decode()
        payload = self.requester(
            url=f"{self.base_url}{path}",
            headers={
                "CB-ACCESS-KEY": self.api_key,
                "CB-ACCESS-SIGN": signature,
                "CB-ACCESS-TIMESTAMP": timestamp,
                "CB-ACCESS-PASSPHRASE": self.passphrase,
                "Accept": "application/json",
            },
            timeout_seconds=self.timeout_seconds,
        )
        balances = []
        for item in payload if isinstance(payload, list) else []:
            balance = _non_zero_balance(
                item.get("currency", ""), item.get("balance"), item.get("available"), item.get("hold")
            )
            if balance:
                balances.append(balance)
        return self._result(balances, account_mode="exchange-profile")



class KrakenAccountConnector(ExchangeConnector):
    exchange_id = "kraken"
    label = "Kraken"
    docs_url = "https://docs.kraken.com/api/docs/rest-api/get-account-balance"
    env_keys = ("BSM_KRAKEN_API_KEY", "BSM_KRAKEN_API_SECRET")

    def __init__(self, *, api_key: str | None, api_secret: str | None, base_url: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.api_key = api_key or ""
        self.api_secret = api_secret or ""
        self.base_url = base_url.rstrip("/")

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.api_secret)

    def connection_result(self) -> ExchangeConnectionResult:
        path = "/0/private/Balance"
        nonce = str(time.time_ns())
        post_data = urlencode({"nonce": nonce})
        try:
            secret = base64.b64decode(self.api_secret)
        except ValueError as exc:
            raise ExchangeConnectionError("Kraken API secret is not valid base64") from exc
        digest = hashlib.sha256((nonce + post_data).encode()).digest()
        signature = base64.b64encode(
            hmac.new(secret, path.encode() + digest, hashlib.sha512).digest()
        ).decode()
        payload = self.requester(
            url=f"{self.base_url}{path}",
            method="POST",
            headers={
                "API-Key": self.api_key,
                "API-Sign": signature,
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            body=post_data.encode(),
            timeout_seconds=self.timeout_seconds,
        )
        errors = payload.get("error", [])
        if errors:
            raise ExchangeConnectionError(f"Kraken rejected the request: {'; '.join(errors)[:180]}")
        balances = []
        for asset, total in payload.get("result", {}).items():
            balance = _non_zero_balance(asset, total, total, 0)
            if balance:
                balances.append(balance)
        return self._result(balances, account_mode="spot")


class OkxAccountConnector(ExchangeConnector):
    exchange_id = "okx"
    label = "OKX"
    docs_url = "https://www.okx.com/docs-v5/en/#trading-account-rest-api-get-balance"
    env_keys = ("BSM_OKX_API_KEY", "BSM_OKX_API_SECRET", "BSM_OKX_PASSPHRASE")

    def __init__(
        self,
        *,
        api_key: str | None,
        api_secret: str | None,
        passphrase: str | None,
        base_url: str,
        simulated: bool,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.api_key = api_key or ""
        self.api_secret = api_secret or ""
        self.passphrase = passphrase or ""
        self.base_url = base_url.rstrip("/")
        self.simulated = simulated

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.api_secret and self.passphrase)

    def connection_result(self) -> ExchangeConnectionResult:
        timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        path = "/api/v5/account/balance"
        signature = base64.b64encode(
            hmac.new(self.api_secret.encode(), f"{timestamp}GET{path}".encode(), hashlib.sha256).digest()
        ).decode()
        headers = {
            "OK-ACCESS-KEY": self.api_key,
            "OK-ACCESS-SIGN": signature,
            "OK-ACCESS-TIMESTAMP": timestamp,
            "OK-ACCESS-PASSPHRASE": self.passphrase,
            "Accept": "application/json",
        }
        if self.simulated:
            headers["x-simulated-trading"] = "1"
        payload = self.requester(
            url=f"{self.base_url}{path}", headers=headers, timeout_seconds=self.timeout_seconds
        )
        if str(payload.get("code", "0")) != "0":
            raise ExchangeConnectionError(f"OKX rejected the request: {str(payload.get('msg') or 'unknown error')[:180]}")
        balances = []
        for account in payload.get("data", []):
            for item in account.get("details", []):
                balance = _non_zero_balance(
                    item.get("ccy", ""),
                    item.get("eq") or item.get("cashBal"),
                    item.get("availBal") or item.get("availEq"),
                    item.get("frozenBal") or item.get("ordFrozen"),
                )
                if balance:
                    balances.append(balance)
        return self._result(balances, account_mode="demo" if self.simulated else "live")


class BybitAccountConnector(ExchangeConnector):
    exchange_id = "bybit"
    label = "Bybit"
    docs_url = "https://bybit-exchange.github.io/docs/v5/account/wallet-balance"
    env_keys = ("BSM_BYBIT_API_KEY", "BSM_BYBIT_API_SECRET")

    def __init__(
        self,
        *,
        api_key: str | None,
        api_secret: str | None,
        base_url: str,
        account_type: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.api_key = api_key or ""
        self.api_secret = api_secret or ""
        self.base_url = base_url.rstrip("/")
        self.account_type = account_type.upper()

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.api_secret)

    def connection_result(self) -> ExchangeConnectionResult:
        timestamp = str(int(time.time() * 1000))
        recv_window = "5000"
        query = urlencode({"accountType": self.account_type})
        signature = hmac.new(
            self.api_secret.encode(),
            f"{timestamp}{self.api_key}{recv_window}{query}".encode(),
            hashlib.sha256,
        ).hexdigest()
        payload = self.requester(
            url=f"{self.base_url}/v5/account/wallet-balance?{query}",
            headers={
                "X-BAPI-API-KEY": self.api_key,
                "X-BAPI-TIMESTAMP": timestamp,
                "X-BAPI-RECV-WINDOW": recv_window,
                "X-BAPI-SIGN": signature,
                "Accept": "application/json",
            },
            timeout_seconds=self.timeout_seconds,
        )
        if int(payload.get("retCode", -1)) != 0:
            raise ExchangeConnectionError(
                f"Bybit rejected the request: {str(payload.get('retMsg') or 'unknown error')[:180]}"
            )
        balances = []
        for account in payload.get("result", {}).get("list", []):
            for item in account.get("coin", []):
                total = item.get("walletBalance") or item.get("equity")
                balance = _non_zero_balance(
                    item.get("coin", ""),
                    total,
                    item.get("availableToWithdraw") or item.get("availableToBorrow") or total,
                    item.get("locked") or 0,
                )
                if balance:
                    balances.append(balance)
        return self._result(balances, account_mode=self.account_type.lower())



def build_exchange_connectors(settings: Any, *, requester: JsonRequester = _request_json) -> list[ExchangeConnector]:
    common = {"timeout_seconds": settings.outbound_timeout_seconds, "requester": requester}
    return [
        BinanceAccountConnector(
            api_key=settings.binance_api_key,
            api_secret=settings.binance_api_secret,
            base_url=settings.binance_api_base_url,
            **common,
        ),
        CoinbaseExchangeAccountConnector(
            api_key=settings.coinbase_exchange_api_key,
            api_secret=settings.coinbase_exchange_api_secret,
            passphrase=settings.coinbase_exchange_passphrase,
            base_url=settings.coinbase_exchange_base_url,
            **common,
        ),
        KrakenAccountConnector(
            api_key=settings.kraken_api_key,
            api_secret=settings.kraken_api_secret,
            base_url=settings.kraken_api_base_url,
            **common,
        ),
        OkxAccountConnector(
            api_key=settings.okx_api_key,
            api_secret=settings.okx_api_secret,
            passphrase=settings.okx_passphrase,
            base_url=settings.okx_api_base_url,
            simulated=settings.okx_simulated_trading,
            **common,
        ),
        BybitAccountConnector(
            api_key=settings.bybit_api_key,
            api_secret=settings.bybit_api_secret,
            base_url=settings.bybit_api_base_url,
            account_type=settings.bybit_account_type,
            **common,
        ),
    ]
