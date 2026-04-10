# Open-Source Stack Watchlist

## Purpose

This note captures a user-supplied post that replaces expensive paid tools with open-source alternatives and maps those tools to the Bot Society Markets roadmap.

The goal is not to adopt everything blindly. The goal is to preserve the source list, verify the referenced projects at a high level, and decide which ones are:

- immediate integration candidates
- research references
- developer tooling
- competitor or benchmark intelligence

This memo is the project bookmark for that stack.

## Source Post Summary

The post proposes replacing a high-cost trading workflow with a mostly open-source stack:

1. TradingView Pro -> `tradingview/lightweight-charts`
2. Bloomberg Terminal -> `mortada/fredapi` plus an LLM layer
3. Backtesting platform -> `evan-kolberg/prediction-market-backtesting`
4. Real-time dashboard -> `txbabaxyz/polyrec`
5. Bot framework -> `dylanpersonguy/Polymarket-Trading-Bot`
6. Strategy reverse engineering -> `ent0n29/polybot`
7. Paper trading for AI agents -> `agent-next/polymarket-paper-trader`
8. Token savings -> `rtk-ai/rtk`
9. Claude Code alternative -> `aaif-goose/goose`
10. Wallet tracking and copy trading -> `@KreoPolyBot`

## Verification Snapshot

Snapshot date: `2026-04-10`

Verified from public repository metadata and source pages at the time of writing:

| Tool | Repo / Source | Verified status | Notes |
| --- | --- | --- | --- |
| lightweight charts | `tradingview/lightweight-charts` | active, Apache-2.0, TypeScript, ~14.5k stars | strong direct frontend candidate |
| FRED API | `mortada/fredapi` | active, Apache-2.0, Python, ~1.3k stars | strong macro data enrichment candidate |
| prediction market backtesting | `evan-kolberg/prediction-market-backtesting` | active, Python, ~376 stars | promising, but license shows `NOASSERTION` and must be reviewed before direct use |
| polyrec | `txbabaxyz/polyrec` | active, MIT, Python, ~171 stars | useful dashboard and research reference |
| Polymarket-Trading-Bot | `dylanpersonguy/Polymarket-Trading-Bot` | active, TypeScript, ~169 stars | ambitious scope, but no clear license in metadata, so treat as reference until reviewed |
| polybot | `ent0n29/polybot` | active, MIT, Java, ~361 stars | reference architecture for data and analytics pipelines |
| polymarket-paper-trader | `agent-next/polymarket-paper-trader` | active, MIT, Python, ~95 stars | strong simulation and evaluation candidate |
| rtk | `rtk-ai/rtk` | active, Apache-2.0, Rust, ~22k stars | developer productivity tool, not product dependency |
| goose | `aaif-goose/goose` | active, Apache-2.0, Rust, ~40k stars | developer agent tool, not product dependency |
| Kreo | `@KreoPolyBot` on Telegram | live Telegram bot | benchmark and market-intel reference, not an internal dependency |

Important note:

- The current Goose repository verified for this memo is `aaif-goose/goose`.
- Some social-post claims such as exact line counts, token savings percentages, or profitability should be treated as unverified marketing claims until independently tested.

## Decision Map

### Tier 1: Immediate integration candidates

These fit the current Bot Society Markets architecture with acceptable complexity.

#### 1. `tradingview/lightweight-charts`

Why it fits:

- We already have a browser-based product shell.
- It can materially improve the public site and dashboard quickly.
- It is maintained by TradingView and small enough to adopt without dragging in a massive framework.

Recommended use:

- replace simple hand-built price visuals with embeddable chart components
- use on asset detail views, bot detail views, and score-history charts
- keep our existing API and just improve presentation

Recommended priority: `P1`

#### 2. `mortada/fredapi`

Why it fits:

- Our backend is already Python-first.
- FRED data is highly relevant for macro-sensitive bots and regime classification.
- It strengthens the research layer without forcing a frontend rewrite.

Recommended use:

- add a macro data provider module
- ingest FRED series for rates, inflation, dollar liquidity, credit spreads, and risk regime proxies
- expose selected macro context as bot inputs and dashboard overlays

Recommended priority: `P1`

#### 3. `agent-next/polymarket-paper-trader`

Why it fits:

- It helps us evaluate AI bot behavior safely before live execution.
- Paper trading aligns with our current product posture, which is research and analytics first.
- It creates a bridge between prediction outputs and execution simulation.

Recommended use:

- connect selected bot predictions to a paper-trading sandbox
- compare bot call quality versus executable market outcomes and slippage
- add a future "paper portfolio" mode for bot personas

Recommended priority: `P1`

### Tier 2: High-value candidates after review

These are interesting, but they should not be pulled in directly without a tighter technical and legal pass.

#### 4. `evan-kolberg/prediction-market-backtesting`

Why it is valuable:

- It is directly aligned with Polymarket and Kalshi workflows.
- It may accelerate serious event-market backtesting.

Why we should be careful:

- License metadata currently returns `NOASSERTION`.
- It is a fork with deeper coupling to its own framework assumptions.
- It is better treated as a research spike before adoption.

Recommended use:

- evaluate as a standalone research workstream
- test whether we can export our prediction archive into its format
- only integrate after license review and architecture fit review

Recommended priority: `P2`

#### 5. `txbabaxyz/polyrec`

Why it is valuable:

- It shows a compact live-market terminal approach with useful indicator and logging ideas.
- Good inspiration for a future operator or quant console.

Why it is not a direct dependency today:

- Our product is web-first, not terminal-first.
- We should borrow concepts, not absorb another UI paradigm into the core product.

Recommended use:

- mine for dashboard concepts, feed blending patterns, and data logging ideas
- keep as a reference for a future internal ops console

Recommended priority: `P2`

#### 6. `ent0n29/polybot`

Why it is valuable:

- Strong reference for a more industrial-grade market-data and analytics pipeline.
- Relevant if we grow into Kafka, ClickHouse, and Grafana style observability.

Why it is not immediate:

- It introduces stack complexity beyond current MVP needs.
- It is more useful as a blueprint than a drop-in.

Recommended use:

- use as reference when upgrading analytics architecture
- compare its event flow, storage model, and monitoring ideas against our roadmap

Recommended priority: `P2`

### Tier 3: Reference only unless reviewed deeply

#### 7. `dylanpersonguy/Polymarket-Trading-Bot`

Why it is interesting:

- Large scope, many strategy modes, and directly relevant domain ideas
- useful to compare feature coverage and operational shape

Why we should not integrate it directly yet:

- metadata did not expose a clear software license at snapshot time
- it is large enough to become an architectural transplant rather than a clean dependency
- importing strategy code without a careful audit would create technical and legal risk

Recommended use:

- use as competitive and architectural reference
- inspect strategy taxonomy, dashboard ideas, and market-scanner patterns
- do not vendor or embed until license and code-quality review are complete

Recommended priority: `P3`

### Tier 4: Developer tooling, not product dependencies

#### 8. `rtk-ai/rtk`

Use:

- reduce token spend in developer workflows if we later standardize on supported tools

Decision:

- useful for engineering productivity
- not part of the customer-facing platform

#### 9. `aaif-goose/goose`

Use:

- alternative open agent tooling for dev workflows, experiments, or internal automation

Decision:

- valuable as optional internal tooling
- not part of the runtime product architecture

### Tier 5: Competitor or benchmark intelligence

#### 10. `@KreoPolyBot`

Use:

- track market expectations for wallet-following and copy-trade experiences
- benchmark UX, alert cadence, and perceived value

Decision:

- external benchmark only
- not an internal dependency

## What Bot Society Markets Should Actually Adopt

### Recommended adoption order

1. `lightweight-charts`
2. `fredapi`
3. `polymarket-paper-trader`
4. `prediction-market-backtesting` after license review

### Recommended reference set

1. `polyrec`
2. `polybot`
3. `Polymarket-Trading-Bot`

### Recommended non-product tooling

1. `rtk`
2. `goose`

## Concrete follow-up work

### Near-term engineering tasks

1. Replace current basic chart rendering with `lightweight-charts`
2. Add a `fredapi` provider module and macro regime dashboard cards
3. Define a paper-trading adapter boundary so bot predictions can be simulated before any live execution work
4. Open a dedicated legal and licensing review for `prediction-market-backtesting` and `Polymarket-Trading-Bot`

### Architecture guardrails

1. Prefer API-level or adapter-level integration over vendoring large third-party codebases
2. Treat unlicensed or unclear-license repositories as reference material only until clarified
3. Keep the product web-first; do not let terminal tooling dictate the customer-facing architecture
4. Use external bot frameworks for idea extraction, not wholesale adoption

## Bottom Line

This source pack is useful and worth preserving.

For Bot Society Markets, the highest-quality immediate moves are:

- `lightweight-charts` for the web product surface
- `fredapi` for macro-aware signal enrichment
- `polymarket-paper-trader` for safe execution simulation

The rest should mostly inform roadmap decisions, infrastructure upgrades, and competitor awareness rather than become direct runtime dependencies right away.

## Sources

- [tradingview/lightweight-charts](https://github.com/tradingview/lightweight-charts)
- [mortada/fredapi](https://github.com/mortada/fredapi)
- [evan-kolberg/prediction-market-backtesting](https://github.com/evan-kolberg/prediction-market-backtesting)
- [txbabaxyz/polyrec](https://github.com/txbabaxyz/polyrec)
- [dylanpersonguy/Polymarket-Trading-Bot](https://github.com/dylanpersonguy/Polymarket-Trading-Bot)
- [ent0n29/polybot](https://github.com/ent0n29/polybot)
- [agent-next/polymarket-paper-trader](https://github.com/agent-next/polymarket-paper-trader)
- [rtk-ai/rtk](https://github.com/rtk-ai/rtk)
- [aaif-goose/goose](https://github.com/aaif-goose/goose)
- [Kreo Polymarket](https://t.me/KreoPolyBot?start=ref-kreohub)
