# Polymarket Open-Source Integration Memo

## Purpose

This memo converts a community repo list into a practical implementation plan for `Bot Society Markets`.

The goal is not to install everything. The goal is to identify the highest-leverage building blocks for:

- faster strategy research
- stronger Polymarket-specific signal quality
- repeatable backtesting
- wallet and market microstructure intelligence
- production-grade bot orchestration

## Executive Summary

The best repo in the list for our core trading roadmap is `prediction-market-backtesting`.

It is the strongest match for the end-state we want: serious simulation on Polymarket and Kalshi with realistic execution modeling, portfolio replay, charting, and optimizer support. It should become the external benchmark engine we graduate into once our current in-house Strategy Lab needs deeper market-microstructure realism.

The second most useful group is the pair `collectmarkets2` and `mlmodelpoly`.

Together, they point to a very practical edge stack:

- collect real wallet behavior
- collect exchange and Polymarket microstructure
- estimate fair value versus market odds
- use the gap as a tradable signal

That is much closer to a differentiated Polymarket product than generic LLM agent frameworks alone.

The best orchestration layer from the list is `pydantic-ai`.

It is a strong candidate for the next generation of our bot runtime because it gives us typed, validated agents without locking us into one model vendor.

The best research-enrichment ideas come from `/last30days`, but it should be treated as a source pattern, not a hard dependency.

`n8n`, `Firecrawl`, and `Tavily MCP` are useful operational tools, but they are not the core moat. They should be optional infrastructure, not the center of the architecture.

## Repo-By-Repo Extraction

### 1. prediction-market-backtesting

Repo:

- https://github.com/evan-kolberg/prediction-market-backtesting

What it is:

- a NautilusTrader-based backtesting framework with custom Polymarket and Kalshi adapters
- supports multi-market replay, runner abstractions, optimizer support, charting, and execution-modeling topics like fees, slippage, passive order logic, queue position, and latency

Why it matters for us:

- this is the closest thing in the list to a professional simulation engine for prediction markets
- it directly addresses the exact gap between our current fast Strategy Lab and a serious institutional-grade backtest layer
- it is especially useful once we want:
  - market-specific fill modeling
  - more realistic order execution assumptions
  - portfolio-level replay instead of only simple indicator logic
  - optimizer-driven parameter search

Decision:

- adopt as a strategic integration target
- do not replace our current Strategy Lab immediately
- use our current lab for fast iteration and use this repo as the next-tier validation engine

Best use inside this project:

- add a future `advanced backtest` mode that exports our strategy configuration into this framework
- benchmark our in-house strategies against a more realistic Polymarket/Kalshi execution model

## 2. TradingAgents

Repo:

- https://github.com/TauricResearch/TradingAgents

What it is:

- a multi-agent LLM trading framework with configurable components

Why it matters for us:

- useful as a reference for how to structure specialized research, debate, and decision agents
- helpful for inspiration on multi-agent collaboration and configuration patterns

What it does not solve by itself:

- it is not Polymarket-specific
- it does not create a durable edge on its own
- without stronger data, evaluation, and execution layers, it risks becoming generic agent theater

Decision:

- borrow orchestration ideas only
- do not make it a core dependency right now

Best use inside this project:

- inspire future bot-role decomposition such as:
  - research bot
  - risk bot
  - execution bot
  - referee bot

## 3. /last30days

Repo:

- https://github.com/mvanhorn/last30days-skill

What it is:

- an agent-led research skill that synthesizes signals across Reddit, HN, Polymarket, GitHub, and optionally more sources

Useful extraction:

- cross-source trend clustering
- Polymarket-aware noise filtering and entity disambiguation
- engagement-weighted research summarization
- a strong pattern for turning messy public information into a structured brief

Why it matters for us:

- our current stack already ingests signals
- what this repo suggests is a better research synthesis layer, especially for event-driven markets

Decision:

- borrow product and signal-ranking ideas
- do not embed the whole repo directly

Best use inside this project:

- build a `research brief` feature for each market and asset
- use engagement-weighted summaries to feed our bots and the Strategy Lab

## 4. polymarket-assistant-tool

Repo:

- https://github.com/FiatFiorino/polymarket-assistant-tool

What it is:

- a real-time terminal dashboard combining Binance order flow with Polymarket prices
- computes multiple indicators and a directional aggregate score

Useful extraction:

- combine exchange microstructure with Polymarket odds
- use order-flow confirmation as a filter for short-horizon prediction markets
- visualize divergence between spot/futures pressure and prediction-market pricing

Why it matters for us:

- this is a concrete clue about where real short-term edge may live
- Polymarket alone is often not enough; pairing it with outside order-flow may help estimate whether odds lag spot sentiment

Decision:

- adopt ideas, not the whole tool

Best use inside this project:

- create a `venue divergence` score inside our dashboard
- feed exchange-vs-Polymarket disagreement into ranking and simulation

## 5. Firecrawl

Repo:

- https://github.com/firecrawl/firecrawl

What it is:

- a web search, scrape, interact, map, and crawl system for agent workflows

Important reality:

- it is open source, but the documented hosted workflow relies on an API key and service account

Useful extraction:

- robust scraping for JS-heavy pages
- LLM-ready markdown/JSON output
- batch and agent-oriented crawling

Decision:

- optional infrastructure tool
- useful when we need better ingestion from websites that RSS and simple scrapers cannot cover
- not part of the core trading moat

Best use inside this project:

- news/event ingestion fallback
- structured extraction from niche market pages, policy pages, and event-specific sources

## 6. Pydantic AI

Repo:

- https://github.com/pydantic/pydantic-ai

What it is:

- a typed, model-agnostic agent framework with strong validation patterns

Why it matters for us:

- if we want production trading bots, typed agent outputs are a major upgrade over loosely structured prompt chains
- it fits our Python-first architecture well
- it reduces the risk of malformed strategy outputs, invalid action plans, and inconsistent research payloads

Decision:

- strong adopt recommendation

Best use inside this project:

- move future bot orchestration and research agents to validated outputs
- define structured schemas for:
  - market thesis
  - catalyst brief
  - trade idea
  - risk constraints
  - invalidation logic

## 7. n8n

Repo:

- https://github.com/n8n-io/n8n

What it is:

- a workflow automation platform with many integrations and AI support

Important reality:

- source-available and self-hostable, but not a standard permissive open-source dependency in the same way as MIT or Apache libraries

Useful extraction:

- operational automation
- webhook routing
- low-code enrichment workflows
- background research flows and alert pipelines

Decision:

- optional ops layer
- not a core library dependency

Best use inside this project:

- schedule news digestion
- send alert workflows
- fan out results to Slack, Telegram, email, or CRM endpoints

## 8. Tavily MCP Server

Repo:

- https://github.com/tavily-ai/tavily-mcp

What it is:

- a search, extract, crawl, and map MCP server for web research

Important reality:

- the documented setup uses a Tavily API key, even though there is a free account path

Useful extraction:

- better live search tooling for research agents
- useful when we need fresher web retrieval than static feeds provide

Decision:

- optional research connector
- not a moat, not a mandatory dependency

Best use inside this project:

- event research workflows
- catalyst verification
- market-specific investigation when bots need current external context

## 9. collectmarkets2

Repo:

- https://github.com/txbabaxyz/collectmarkets2

What it is:

- a Polymarket wallet activity collector and analyzer with CSV export, cyclic collection, and plotting

Why it matters for us:

- wallet behavior is one of the most promising Polymarket-native edges
- if we can identify strong wallets, copy behavior, timing patterns, or clustering behavior, we move closer to a genuinely differentiated signal source

Decision:

- adopt as a design target
- highly relevant to our roadmap

Best use inside this project:

- add wallet watchlists
- create wallet conviction scores
- build a `smart money` factor into market ranking and bot prompts

## 10. mlmodelpoly

Repo:

- https://github.com/txbabaxyz/mlmodelpoly

What it is:

- a real-time data collector for Binance plus Polymarket integration
- includes fair value estimation, edge calculation, volatility, bias modeling, monitoring, and a terminal dashboard

Why it matters for us:

- this is the clearest direct clue for a real Polymarket alpha engine in the list
- the important concept is not the TUI itself
- the important concept is fair-value estimation versus market odds, using external market microstructure as context

Decision:

- adopt conceptually as a major roadmap item

Best use inside this project:

- add a `fair value` service that estimates expected probability from external data
- compare fair value to current Polymarket odds
- rank setups by positive edge after fees and slippage assumptions

## Recommended Stack For Bot Society Markets

### Adopt now

- `pydantic-ai`
- ideas and validation benchmarks from `prediction-market-backtesting`
- architecture ideas from `collectmarkets2`
- fair-value and edge concepts from `mlmodelpoly`

### Borrow ideas, not full dependencies

- `TradingAgents`
- `/last30days`
- `polymarket-assistant-tool`

### Optional operational tooling

- `n8n`
- `Firecrawl`
- `Tavily MCP`

## Best Combined Architecture

### Layer 1: Market and venue data

- our current providers
- Polymarket and Kalshi public market feeds
- exchange microstructure inputs inspired by `polymarket-assistant-tool` and `mlmodelpoly`

### Layer 2: Research and event context

- RSS, Reddit, and venue feeds already in the product
- synthesis improvements inspired by `/last30days`
- optional web retrieval via `Firecrawl` or `Tavily`

### Layer 3: Wallet intelligence

- wallet collection and ranking inspired by `collectmarkets2`
- smart-wallet leaderboards
- wallet-followed signal weighting

### Layer 4: Model and fair-value engine

- estimate fair probability using exchange behavior, volatility, momentum, and event signals
- compare fair value to Polymarket odds
- compute `edge after fees`

### Layer 5: Bot orchestration

- move toward typed, validated agents with `pydantic-ai`
- each bot outputs structured trade hypotheses and risk constraints

### Layer 6: Evaluation

- keep the fast in-house Strategy Lab
- later add an advanced validation mode using `prediction-market-backtesting`

## What We Should Build Next

### Move 1

Add a `wallet intelligence` subsystem.

Why:

- it is Polymarket-native
- it is not generic
- it can become a real moat

### Move 2

Add a `fair value and edge` engine.

Why:

- this is how we move from dashboards to actual tradable ranking
- it lets us identify markets where Polymarket pricing appears misaligned with external market context

### Move 3

Upgrade bot orchestration with typed agent outputs.

Why:

- stronger production reliability
- easier testing
- safer automation

### Move 4

Add advanced backtest export into prediction-market-backtesting.

Why:

- once the fair-value engine starts producing hypotheses, we need deeper execution realism before trusting it

## Practical Conclusion

If we want to build something that can eventually beat the field, the strongest path from this repo list is:

1. `collectmarkets2` style wallet intelligence
2. `mlmodelpoly` style fair-value and edge calculation
3. `pydantic-ai` style typed bot orchestration
4. `prediction-market-backtesting` as the serious validation layer

That combination is much more valuable than a generic pile of agent frameworks.

## Source Links Reviewed

- https://github.com/evan-kolberg/prediction-market-backtesting
- https://github.com/TauricResearch/TradingAgents
- https://github.com/mvanhorn/last30days-skill
- https://github.com/FiatFiorino/polymarket-assistant-tool
- https://github.com/firecrawl/firecrawl
- https://github.com/pydantic/pydantic-ai
- https://github.com/n8n-io/n8n
- https://github.com/tavily-ai/tavily-mcp
- https://github.com/txbabaxyz/collectmarkets2
- https://github.com/txbabaxyz/mlmodelpoly
