# BITprivat V1 Migration Roadmap

Version 1.0 - April 2026 - Confidential

## Purpose

This roadmap converts the current FastAPI MVP into the target BITprivat V1 architecture described in [BITprivat V1 Technical Architecture](25-bitprivat-v1-technical-architecture.md).

The goal is not to rewrite everything at once. The safest professional path is to keep the working product live, preserve current routes, and extract services only when the domain pressure justifies it.

## Guiding Rules

- Preserve the current product URLs during migration.
- Keep paper trading ahead of live execution until compliance, risk, exchange, and custody constraints are handled.
- Do not add private-key custody.
- Do not move latency-sensitive execution through analytics or scraping code.
- Every state-changing action needs an audit event before live trading activation.
- Every provider integration needs provenance, fallback behavior, and health reporting.

## Phase 0 - Stabilize Current MVP

Status: in progress.

Objectives:

- Keep the current FastAPI app running on Akash with custom domain support.
- Keep the dashboard professional and functional.
- Use real public data where possible: CoinGecko, Polymarket, Kalshi.
- Keep simulation and paper trading as the primary product value.
- Remove secrets from generated manifests and move them to deployment-level secret management.

Deliverables:

- Current dashboard and public website.
- Provider health checks.
- Strategy Lab with editable algorithm settings.
- Paper trading ledgers.
- Production cutover guide.
- Legal pages and commercial readiness surfaces.

## Phase 1 - Contracts and Versioned API

Status: first implementation shipped.

Objective: introduce a stable V1 API without breaking the existing UI.

Work:

- Add `/api/v1/*` routes beside current `/api/*` routes. Done for the current auth, landing, dashboard, assets, signals, leaderboard, simulation, system, billing, workspace, paper-trading, and admin surfaces.
- Generate OpenAPI client contracts.
- Add route mapping from current endpoints to target endpoints.
- Add structured error envelopes.
- Add pagination standards for signals, orders, traders, and backtests.
- Add request IDs to every response.

Exit criteria:

- Current UI can call either legacy `/api/*` or versioned `/api/v1/*`.
- API tests cover both old and new routes.
- External users can receive stable API documentation.

## Phase 2 - Data Hardening

Status: started, with audit logging plus Strategy Lab persistence now implemented in the monolith.

Objective: prepare the database for real users, real paper trades, and later live trading.

Work:

- Add normalized `orders`, `positions`, `strategies`, `backtest_runs`, `wallets`, `traders`, and `audit_log` tables. `audit_logs`, `strategies`, and `backtest_runs` are implemented in the current MVP schema.
- Keep existing MVP tables until migrated.
- Add Alembic migrations for each new table.
- Add append-only audit records for auth, settings, paper orders, alert rules, provider changes, and Strategy Lab actions. Started with authentication, workspace mutations, billing session launches, simulations, saved strategies, saved backtests, paper-trading simulation, admin jobs, and Stripe webhook processing.
- Add retention policy for raw signal text.
- Add database backup and restore verification.

Exit criteria:

- All state-changing app actions write audit events.
- Backtest and paper trading data have durable records.
- Existing dashboard still works.

## Phase 3 - Provider and Signal Service Boundary

Objective: separate signal intelligence from the monolith behind an internal interface.

Work:

- Create a service interface for signal ingestion and ranking.
- Keep the first implementation inside Python/FastAPI.
- Add source-specific provider adapters for X/Twitter, Reddit, Telegram, Polymarket, Kalshi, RSS, and web search.
- Add provider provenance weights and source quality scoring.
- Store raw public social posts separately from normalized signals.
- Add rate-limit tracking and provider backoff.

Exit criteria:

- Dashboard can show provider health by source.
- Signal quality score includes source trust, freshness, and historical accuracy.
- New provider adapters can be added without modifying dashboard code.

## Phase 4 - Analytics and Strategy Lab Scale-Up

Objective: make Strategy Lab a serious product surface.

Work:

- Move long-running backtests to async jobs.
- Store full backtest outputs in object storage.
- Add backtest result history and comparison views. Started with authenticated stored backtest ledgers.
- Add strategy templates and user-saved strategies. User-saved Strategy Lab configurations are implemented.
- Add walk-forward analysis, max drawdown, Sharpe, Sortino, CAGR, exposure, and turnover metrics.
- Add historical data cache with provider source attribution.

Exit criteria:

- Users can save a strategy, run a backtest, return later, and compare runs.
- Backtests do not block the web server.
- Strategy outputs can be exported for external engines.

## Phase 5 - API Gateway and Realtime Layer

Objective: prepare for multiple internal services without changing public URLs.

Work:

- Introduce a Go gateway or lightweight gateway layer.
- Keep FastAPI as the first upstream service.
- Add WebSocket channels for prices, signals, orders, portfolio, and provider health.
- Add Redis-backed rate limits.
- Add API keys with scopes.
- Add OpenTelemetry tracing across gateway and FastAPI.

Exit criteria:

- Browser can subscribe to live dashboard streams.
- Public API traffic goes through the gateway.
- Programmatic access can be scoped and revoked.

## Phase 6 - Paper Trading Engine

Objective: extract order lifecycle logic before live execution.

Work:

- Create a trading engine interface.
- Implement paper order placement, fills, status updates, and cancellations.
- Use the same request/response contract planned for live orders.
- Add order risk checks: notional limits, max exposure, asset allowlists, daily loss limits.
- Publish order events to an internal event log.

Exit criteria:

- Paper orders use the same contract as future live orders.
- All paper orders have audit records.
- Dashboard can show order status updates.

## Phase 7 - Event Bus and Async Processing

Objective: stop coupling user-facing requests to heavy background work.

Work:

- Introduce Kafka or a managed equivalent.
- Publish events for signals, paper orders, strategy runs, portfolio snapshots, and notifications.
- Move notification retries and provider refreshes to event consumers.
- Add replay tooling for analytics rebuilds.

Exit criteria:

- Pipeline runs are replayable.
- Consumer lag is observable.
- Analytics can rebuild state from events where practical.

## Phase 8 - Wallet and Identity Layer

Objective: add non-custodial wallet and identity flows safely.

Work:

- Add wallet connection records.
- Add WalletConnect pairing flow.
- Add balance reads through Alchemy/Helius or equivalent.
- Add KYC provider abstraction.
- Never store private keys.
- Never sign transactions server-side.

Exit criteria:

- Users can connect wallets for read-only portfolio context.
- Identity state can be tracked without storing raw KYC documents.
- Wallet data is isolated from live trading activation.

## Phase 9 - Live Execution Readiness

Objective: prepare live trading only after safety and compliance gates pass.

Work:

- Add venue allowlists per user.
- Add exchange credentials vaulting where legally appropriate.
- Add execution adapter test suites.
- Add sandbox/testnet support first.
- Add global circuit breaker.
- Add manual approval gates for risky automation.
- Add incident response playbooks.

Exit criteria:

- Live execution remains disabled by default.
- All live-capable routes require MFA, KYC if required, and explicit user activation.
- The kill switch is tested.
- Legal review is complete for each venue and jurisdiction.

## Phase 10 - Production Platform

Objective: run BITprivat as a scalable SaaS platform.

Work:

- Move from single-container MVP to managed multi-service deployment.
- Use managed Postgres, Redis, object storage, and observability.
- Add staging and production environments.
- Add blue/green or canary deployments.
- Add uptime and SLO dashboards.
- Add formal backup and disaster recovery drills.

Exit criteria:

- Staging mirrors production enough for integration tests.
- Production deploys are reversible.
- SLOs are visible and alertable.

## Priority Implementation Backlog

1. Add versioned `/api/v1` route aliases.
2. Add append-only audit log.
3. Add normalized strategy and backtest run tables.
4. Add async backtest jobs.
5. Add Redis-backed provider cache and rate limits.
6. Add WebSocket endpoint for dashboard live updates.
7. Add paper order contract and order table.
8. Add wallet read-only connection model.
9. Add API key model with scopes.
10. Move generated deployment secrets out of repo-local manifests.
11. Add Sentry/OpenTelemetry instrumentation.
12. Add provider-specific status cards for CoinGecko, Polymarket, Kalshi, Hyperliquid.
13. Add Strategy Lab comparison mode.
14. Add social trader profile table and scoring migrations.
15. Add KYC provider abstraction, disabled by default.

## Risk Register

| Risk | Severity | Mitigation |
| --- | --- | --- |
| Live trading before controls are ready | Critical | Keep execution disabled by default; paper-first; legal/compliance gate. |
| Provider terms violation | High | Use official APIs first; document terms; respect rate limits. |
| Overbuilding before product-market validation | High | Keep MVP useful; extract services only after clear pressure. |
| Secrets leakage through manifests | High | Move secrets to managed secret store; rotate exposed credentials. |
| Dashboard complexity | Medium | Maintain grouped navigation and role-based feature visibility. |
| Backtest performance | Medium | Async jobs, caching, and object storage outputs. |
| Data correctness | High | Provider provenance, audit log, deterministic simulation exports. |

## Definition of Professional V1

BITprivat V1 is ready when:

- The public website explains the product clearly.
- The dashboard feels calm, fast, and operational.
- Strategy Lab can save, run, compare, and export serious backtests.
- Paper trading has a complete order/position lifecycle.
- Signals have provenance, historical scoring, and transparent accuracy.
- Users can connect wallets read-only without custody.
- Every state-changing action has audit logging.
- Provider health and fallback status are visible.
- Live trading remains locked behind explicit legal, risk, MFA, KYC, and user-consent gates.
