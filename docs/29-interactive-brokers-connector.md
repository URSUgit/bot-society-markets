# BITprivat Interactive Brokers Connector

> Status: paper-first connector control plane. Live order routing remains disabled until risk, legal, and production safeguards are complete.

## Recommended Path

For your personal account, start with **TWS API / IB Gateway** in the IBKR paper account.

For a future multi-user SaaS product, plan a separate **IBKR Web API / OAuth** track. That path is better for third-party authorization and customer account access, but it needs formal provider onboarding, compliance review, and stronger tenant isolation.

## Why TWS / IB Gateway First

- It works with an account you already control.
- It does not require BITprivat to store your IBKR password.
- It can run against your paper account before any live-money work.
- It keeps the first milestone realistic: account visibility, positions, balances, order diagnostics, then paper order tests.

Official IBKR references:

- TWS API documentation: https://ibkrcampus.com/campus/ibkr-api-page/twsapi-doc/
- Web API documentation: https://ibkrcampus.com/campus/ibkr-api-page/webapi-doc/
- Client Portal Web API v1 docs: https://ibkrcampus.com/campus/ibkr-api-page/cpapi-v1/
- IB Gateway download: https://www.interactivebrokers.com/en/trading/ibgateway-stable.php

## Connector Modes

### `tws_gateway`

Use this for the first production-quality integration.

Default ports from IBKR documentation:

| Runtime | Default Port |
|---|---:|
| TWS live | 7496 |
| TWS paper | 7497 |
| IB Gateway live | 4001 |
| IB Gateway paper | 4002 |

Recommended first configuration:

```env
BSM_IBKR_CONNECTION_MODE=tws_gateway
BSM_IBKR_ACCOUNT_ID=DU1234567
BSM_IBKR_TWS_HOST=127.0.0.1
BSM_IBKR_TWS_PORT=7497
BSM_IBKR_CLIENT_ID=0
BSM_IBKR_READ_ONLY=true
BSM_IBKR_LIVE_TRADING_ENABLED=false
BSM_IBKR_MARKET_DATA_SUBSCRIBED=false
```

### `client_portal`

Use this later if we choose the local Client Portal Gateway REST path.

IBKR's Client Portal Gateway base URL is:

```env
BSM_IBKR_CONNECTION_MODE=client_portal
BSM_IBKR_CLIENT_PORTAL_BASE_URL=https://localhost:5000/v1/api
BSM_IBKR_ACCOUNT_ID=DU1234567
BSM_IBKR_READ_ONLY=true
BSM_IBKR_LIVE_TRADING_ENABLED=false
```

The local gateway requires browser login and two-factor authentication. The platform must not store IBKR credentials.

## Setup Steps

1. Log in to the IBKR paper account in Trader Workstation or IB Gateway.
2. If using TWS, enable API socket clients inside the TWS API settings.
3. Keep paper mode first: TWS paper usually uses port `7497`; IB Gateway paper usually uses `4002`.
4. Set `BSM_IBKR_ACCOUNT_ID` to the paper account ID shown by IBKR, usually starting with `DU`.
5. Keep `BSM_IBKR_READ_ONLY=true` while building diagnostics.
6. Confirm the BITprivat connector diagnostics show endpoint and account configuration as passing.
7. Only after read-only checks pass, test paper order submission with strict position limits.
8. Do not enable live trading until counsel-approved disclosures, audit logs, kill switch, per-account limits, and manual approvals are in place.

## Implementation Phases

### Phase 1: Connector Visibility

Shipped in this track:

- `ibkr_gateway` appears in `/api/paper-venues`.
- `ibkr-brokerage-gateway` appears in `/api/system/connectors`.
- Diagnostics check connection mode, account ID, read-only state, live gate, and market-data entitlement flag.
- Environment variables are documented in `.env.example`.

### Phase 2: Read-Only Account Probe

Next engineering task:

- Add an adapter module that can connect to TWS / IB Gateway.
- Fetch managed accounts.
- Fetch account summary.
- Fetch current positions.
- Store only normalized portfolio snapshots, never credentials.
- Add a dashboard card for "IBKR paper account visible".

### Phase 3: Paper Order Smoke Test

Only after Phase 2:

- Add per-account max notional, max daily loss, allowed symbols, and order-type allowlist.
- Submit one paper limit order with a tiny notional.
- Record order request, broker response, and reconciliation result in audit logs.
- Keep live trading disabled.

### Phase 4: Live Readiness Review

Live order routing must wait for:

- legal review for investment-advice, broker API, and customer-discretion boundaries;
- updated Terms, Risk Disclosure, and live execution consent flow;
- account-level kill switch and global kill switch;
- immutable audit log for every trading action;
- monitoring and alerting for failed order reconciliation;
- explicit user opt-in for each account and strategy.

## Security Rules

- Never put an IBKR username or password in `.env`, GitHub secrets, Akash, or chat.
- Never automate 2FA bypass.
- Use IBKR-operated login windows only.
- Keep paper and live account configuration separate.
- Do not redistribute IBKR market data to users without the proper rights and subscriptions.
- Treat market data subscriptions and regulatory snapshots as potentially billable.

## User-Facing Product Copy

**Interactive Brokers Gateway**

Connect an IBKR paper account to verify positions, balances, and broker execution readiness. BITprivat starts in read-only mode and does not store your IBKR password. Paper execution and live execution are separate gates with explicit risk controls.

