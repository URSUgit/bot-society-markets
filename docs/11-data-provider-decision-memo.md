# Data Provider Decision Memo

## Purpose

This memo recommends an initial data provider strategy for `Bot Society Markets` based on the current product scope: a research-only SaaS platform of persistent AI trader bots.

## Decision Criteria

The initial provider stack should be evaluated on:

- coverage
- reliability
- latency
- developer experience
- cost
- redistribution and commercial usage fit
- ability to support future enterprise products

## Product Reality

The MVP does not need institutional-grade coverage across every market on day one.

It does need:

- dependable price data
- historical access for evaluation and backtesting
- a practical path to live updates
- lawful public-signal ingestion
- a provider mix that will not destroy margins early

## Recommended Strategic Choice

The strongest initial path is:

- start with `crypto` as the first asset universe
- use official social-platform access where possible
- defer expensive broad news contracts until the product proves demand

This gives the company a faster product loop, simpler market-hours handling, and a more practical path to continuous signal generation.

## Recommended MVP Stack

### 1. Primary Crypto Market Data

**Recommended starting option: CoinGecko**

Why it fits:

- broad crypto market coverage
- official API and WebSocket product
- suitable for price, market-cap, and market-overview use cases
- practical for early-stage market intelligence workflows

Official source:
- [CoinGecko API WebSocket Overview](https://www.coingecko.com/en/api/websocket)

### 2. Secondary Or Alternative Market Data

**Recommended evaluation option: Alpaca for market-data experimentation**

Why it is useful:

- official market data API documentation
- support for historical and real-time data workflows
- practical developer onboarding
- useful if the product later expands into equities or broker-adjacent workflows

Official source:
- [Alpaca Market Data Getting Started](https://docs.alpaca.markets/v1.3/docs/getting-started-with-alpaca-market-data)

### 3. Expansion-Grade Market Data

**Recommended future option: Polygon**

Why it matters:

- strong U.S. equity data coverage
- real-time and historical options across REST, WebSocket, and flat files
- useful when the platform expands into equities, options, or more demanding enterprise research products

Official sources:
- [Polygon Stocks Overview](https://polygon.io/docs/stocks/getting-started)
- [Polygon Pricing](https://polygon.io/pricing)

### 4. Social Signal Sources

**Use official platform access, not unsupported scraping, as a design rule**

Recommended sources:

- X official developer access
- Reddit official developer access

Official sources:
- [X Developer Platform Overview](https://docs.x.com/overview)
- [X Developer Agreement](https://developer.x.com/overview/terms/agreement)
- [Reddit Developer Terms](https://redditinc.com/policies/developer-terms)
- [Reddit Data API Terms](https://redditinc.com/policies/data-api-terms)

## Recommendation By Phase

### Phase 1: Narrow MVP

Use:

- CoinGecko for crypto market data
- X official access for market-relevant public posts
- Reddit official access for public community sentiment

Avoid in phase 1:

- expensive broad institutional news feeds
- unsupported scraping as a core dependency
- wide multi-asset coverage

### Phase 2: Quality And Enterprise Readiness

Add or evaluate:

- Polygon if moving into equities and richer real-time coverage
- Alpaca where it improves developer velocity or market-data flexibility
- curated news feed providers only after product value is demonstrated

## Why Crypto First Is Recommended

Crypto is strategically attractive for the MVP because:

- it trades continuously
- social and narrative signals are strong
- users are already comfortable with digital-native research tools
- it reduces the operational complexity of limited market hours

This does not mean the long-term company should remain crypto-only. It means crypto is a good proving ground for the first bot economy.

## Commercial And Legal Notes

The company should validate, with counsel where needed:

- commercial use rights
- redistribution restrictions
- caching and storage rules
- API display and attribution obligations
- enterprise resale implications

Those rights matter because the long-term business includes dashboards, alerts, and potentially enterprise APIs.

## Final Recommendation

For the MVP, the cleanest stack is:

- `CoinGecko` as primary crypto market data
- `X` official access for real-time public discussion
- `Reddit` official access for community sentiment
- `Polygon` kept in view for equities and expansion
- `Alpaca` evaluated as a practical secondary market-data option

This stack balances cost, feasibility, and a realistic path to future product expansion.
