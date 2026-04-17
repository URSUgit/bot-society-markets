# Paper Trading Venue Activation Plan

## Purpose

Bot Society Markets should never jump from research signals to real execution in one step. The professional path is:

1. Internal ledger simulation.
2. External paper venue with live order-book assumptions.
3. Demo/testnet order router with strict kill switches.
4. Small live pilot only after audit logs, risk limits, and human approvals exist.

This document records the current paper venues we can use and how each one should fit into the product.

Research check date: 2026-04-17.

## Recommended Activation Order

1. **Bot Society Internal Paper Ledger**
   - Status: already implemented.
   - Best for: baseline portfolio accounting tied to bot predictions.
   - Why first: zero external credentials and zero chance of real execution.

2. **Polysandbox**
   - Source: https://www.polysandbox.trade/
   - Docs: https://docs.polysandbox.trade
   - Best for: Polymarket-style automated paper execution.
   - Why second: it is specifically designed around live Polymarket CLOB quotes, REST API testing, FAK/GTC style order flows, and agent workflows.
   - Environment variables:
     - `BSM_PAPER_EXECUTION_PROVIDER=polysandbox`
     - `BSM_POLYSANDBOX_API_URL=https://api.polysandbox.trade/v1`
     - `BSM_POLYSANDBOX_API_KEY=...`
     - `BSM_POLYSANDBOX_SANDBOX_ID=...`
   - Boundary: independent product, not affiliated with Polymarket.

3. **Kalshi Demo**
   - Source: https://docs.kalshi.com/getting_started/demo_env
   - Demo app: https://demo.kalshi.co/
   - API root: `https://demo-api.kalshi.co/trade-api/v2`
   - Best for: regulated event-contract demo workflows and enterprise credibility.
   - Why third: it gives us a real official demo environment, but Bot Society must map signals to concrete Kalshi tickers before order simulation makes sense.
   - Environment variables:
     - `BSM_PAPER_EXECUTION_PROVIDER=kalshi_demo`
     - `BSM_KALSHI_DEMO_API_URL=https://demo-api.kalshi.co/trade-api/v2`
     - `BSM_KALSHI_DEMO_KEY_ID=...`
     - `BSM_KALSHI_DEMO_PRIVATE_KEY_PATH=...`
   - Boundary: demo and production credentials are separate.

4. **Hyperliquid Testnet**
   - Source: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api
   - Testnet app: https://app.hyperliquid-testnet.xyz
   - API root: `https://api.hyperliquid-testnet.xyz`
   - Websocket root: `wss://api.hyperliquid-testnet.xyz/ws`
   - Best for: execution plumbing, websocket health, order-router behavior, crypto hedge testing.
   - Why fourth: it is not a prediction-market venue, but it is valuable for stress-testing execution systems and risk controls.
   - Environment variables:
     - `BSM_PAPER_EXECUTION_PROVIDER=hyperliquid_testnet`
     - `BSM_HYPERLIQUID_TESTNET_API_URL=https://api.hyperliquid-testnet.xyz`
     - `BSM_HYPERLIQUID_TESTNET_WS_URL=wss://api.hyperliquid-testnet.xyz/ws`
     - `BSM_HYPERLIQUID_TESTNET_WALLET_ADDRESS=...`
     - `BSM_HYPERLIQUID_TESTNET_PRIVATE_KEY=...`
   - Boundary: use a testnet-only wallet. Never reuse a wallet with real funds.

5. **Lorem Ipsum Trade**
   - Source: https://www.loremipsumtrade.com/
   - CLOB URL: `https://clob.loremipsumtrade.com`
   - Best for: fast paper loops around short-horizon Polymarket-style crypto binary markets.
   - Why fifth: promising drop-in CLOB-style sandbox, but should be verified manually before becoming a default adapter.
   - Environment variables:
     - `BSM_LOREM_IPSUM_TRADE_ENABLED=true`
     - `BSM_LOREM_IPSUM_TRADE_CLOB_URL=https://clob.loremipsumtrade.com`
     - `BSM_LOREM_IPSUM_TRADE_APP_URL=https://sandbox.loremipsumtrade.com`
   - Boundary: use only empty development wallets if wallet login is required.

6. **PaperMarket**
   - Source: https://papermarket.gitbook.io/papermarket/get-start/overview
   - Best for: manual paper validation of exact Polymarket markets.
   - Why sixth: useful human-in-the-loop terminal, but not the first choice for automated SaaS execution.
   - Boundary: manual validation should feed notes and calibration back into Bot Society, not bypass the ledger.

## Adapter Architecture

The next code layer should use a common paper execution contract:

```python
class PaperExecutionAdapter:
    def list_markets(self, query: str) -> list[PaperMarket]:
        ...

    def quote_order(self, request: PaperOrderRequest) -> PaperOrderQuote:
        ...

    def place_order(self, request: PaperOrderRequest) -> PaperOrderReceipt:
        ...

    def cancel_order(self, order_id: str) -> PaperCancelReceipt:
        ...

    def list_positions(self) -> list[PaperVenuePosition]:
        ...
```

Adapter priorities:

- `InternalPaperAdapter`: wraps the existing local paper ledger.
- `PolysandboxAdapter`: first external API adapter.
- `KalshiDemoAdapter`: official event-contract demo adapter.
- `HyperliquidTestnetAdapter`: execution and hedging testnet adapter.
- `LoremIpsumTradeAdapter`: CLOB-compatible sandbox adapter after verification.

## Product UI Requirements

The dashboard should show:

- venue readiness and credential status
- API capability versus manual-only capability
- live/order-book capability
- replay capability
- recommended next action
- explicit safety note
- activation sequence

The new endpoint is:

```text
GET /api/paper-venues
```

The endpoint is included inside `GET /api/dashboard` as `paper_venues`.

## Safety Rules

- Paper mode only until explicit human approval gates exist.
- Never store seed phrases.
- Use API keys where possible.
- Use testnet-only private keys only for testnet adapters.
- Keep demo, sandbox, testnet, and production credentials separate.
- Do not represent paper PnL as live profitability.
- Do not enable live order routing until there are kill switches, position limits, audit logs, and per-venue spend caps.

## Next Implementation Moves

1. Add adapter interfaces and typed request/receipt models.
2. Implement a dry-run order ticket generator that maps Bot Society predictions into paper venue order intent.
3. Build the Polysandbox adapter behind `BSM_PAPER_EXECUTION_PROVIDER=polysandbox`.
4. Add venue order audit tables for request, quote, receipt, cancel, and reconciliation events.
5. Add a dashboard order blotter separate from the internal paper ledger.
6. Add per-venue risk limits:
   - max order size
   - max open exposure
   - max daily order count
   - max drawdown pause
   - venue kill switch
7. Add CI tests with mocked venue responses before any real API key is used.
