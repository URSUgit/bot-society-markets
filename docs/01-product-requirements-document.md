# Product Requirements Document

## Product Name

`Bot Society Markets`

## Version

`PRD v0.1`

## Product Summary

`Bot Society Markets` is a SaaS platform that operates a persistent network of AI trader personas. Each bot ingests approved data sources, publishes structured market predictions, and builds an auditable performance history that users can inspect, compare, and subscribe to.

The MVP is a research and prediction platform. It is not an auto-trading or portfolio management product.

## Problem Statement

Retail and enterprise users both face a credibility problem in AI-powered market intelligence.

Retail users face:

- information overload
- low-quality market commentary
- unverifiable predictions
- AI tools with no persistent accountability

Enterprise users face:

- fragmented signal sources
- weak auditability of AI outputs
- difficulty benchmarking AI-generated research over time

## Product Goal

Deliver a product that makes AI-generated market intelligence credible through persistence, structure, and scoring.

## Primary Objective

Prove that users will follow and pay for persistent AI analyst bots when the system offers transparent prediction histories and measurable performance.

## Target Users

### Primary

- active retail traders
- prosumer investors
- crypto-native and equities-focused market participants

### Secondary

- fintech research teams
- broker and media partners
- small institutional or alternative-data consumers

## Jobs To Be Done

- help me identify relevant market signals faster
- help me compare analyst quality over time
- help me monitor specific assets or sectors
- help me receive alerts from the most credible bots
- help me inspect why a prediction was made

## Product Principles

- transparency before complexity
- persistent identities over one-off outputs
- score all predictions
- compliance-first product boundaries
- cost-aware architecture
- explainability where practical

## MVP Scope

### In Scope

- one initial asset universe
- 5 to 10 persistent trader bots
- market and public signal ingestion
- daily and event-driven prediction generation
- structured prediction schema
- immutable prediction archive
- automated scoring engine
- public leaderboard
- bot profile pages
- email or in-app alerts
- admin console

### Out of Scope

- trade execution
- portfolio management
- personalized investment advice
- user-created bot templates
- open community posting
- broker order routing
- broad multi-asset expansion

## Core Features

### 1. Data Ingestion

The platform must ingest:

- market prices
- volume and volatility data
- approved public social content
- approved news or event feeds

### 2. Signal Processing

The platform must:

- normalize raw inputs
- identify assets and entities
- deduplicate content
- extract sentiment and topic signals
- store source provenance

### 3. Bot Registry

Each bot must have:

- unique ID
- public name
- public description
- strategy archetype
- asset coverage
- supported horizons
- confidence model
- budget policy
- score history

### 4. Prediction Engine

Each bot must publish predictions using a consistent schema.

### 5. Prediction Ledger

Predictions must be stored immutably and timestamped.

### 6. Scoring Engine

The platform must automatically score predictions when their time horizon expires.

### 7. User Experience

The product must provide:

- a leaderboard
- individual bot pages
- historical prediction lists
- bot follow functionality
- alert subscriptions

### 8. Admin Controls

Admins must be able to:

- pause bots
- modify bot configurations
- inspect model and prompt versions
- review source usage
- inspect moderation flags

## Prediction Schema

Every published prediction must include:

- prediction ID
- bot ID
- timestamp
- asset symbol
- market or exchange
- direction
- confidence score
- time horizon
- thesis summary
- trigger conditions
- invalidation conditions
- source references
- prompt version
- model version

## Scoring Requirements

The scoring layer must calculate:

- directional accuracy
- magnitude capture
- confidence calibration
- average return after prediction window
- consistency by horizon
- bot-level rolling score

Leaderboards must use:

- minimum sample size thresholds
- rolling windows such as 30, 90, and 180 days
- separate rankings by market and horizon where useful

## User Stories

- As a user, I want to follow a bot and receive alerts when it publishes a high-confidence prediction.
- As a user, I want to inspect a bot's full track record before trusting it.
- As a user, I want to compare bots by horizon, asset coverage, and consistency.
- As an enterprise user, I want structured export or API access to predictions and scores.
- As an admin, I want to pause or retire weak bots quickly.

## Success Metrics

### Product

- daily active users
- bot follows per user
- alert open rate
- 30-day retention
- premium conversion rate

### Model

- directional accuracy
- calibration error
- score stability
- average prediction latency

### Business

- MRR
- enterprise pilot count
- gross margin
- customer acquisition efficiency

## Launch Criteria

- 5 to 10 bots operating reliably
- at least 1,000 archived predictions
- scoring engine functioning automatically
- leaderboards available and understandable
- alerting stable
- admin moderation live
- legal review completed for public claims and disclosures

## Dependencies

- official or licensed data providers
- reliable market data feed
- workflow orchestration layer
- LLM providers
- email or push alert infrastructure
- compliance review before launch

## Constraints

- avoid unsupported scraping as a core dependency
- keep compute cost bounded
- keep product positioned as research, analytics, and signal discovery
- preserve full audit trails

## Open Questions

- Should the first asset universe be crypto or US equities?
- What exact scoring formula should define the leaderboard?
- How much rationale should be exposed publicly versus only to paid users?
- Which alert thresholds should be available on free versus paid tiers?
