# Technical Architecture

## Objective

Build a cost-aware, auditable, event-driven platform where persistent trader bots monitor signals, publish structured predictions, and are scored automatically against realized market outcomes.

## Architecture Principles

- event-driven workflows over constant polling where possible
- full auditability of predictions and source inputs
- official or licensed data access as a core requirement
- clear separation between ingestion, prediction, and scoring
- budget controls at the bot and workflow level
- modularity so new bots can be added without rewriting the platform

## High-Level System

### Data Ingestion Layer

Purpose:

- collect market data
- collect public social and news content
- collect macro and event calendars

Responsibilities:

- API authentication
- polling and webhook handling
- retry logic
- rate-limit protection
- raw payload archival
- timestamp normalization

### Signal Processing Layer

Purpose:

- convert raw inputs into normalized, bot-consumable signals

Responsibilities:

- deduplication
- asset and entity extraction
- sentiment analysis
- topic classification
- event tagging
- source scoring

### Signal Store

Purpose:

- persist structured signals for retrieval by bot workflows

Recommended storage:

- `Postgres` for relational data
- object storage for raw payloads
- `Redis` for caches and ephemeral state

### Bot Registry

Purpose:

- define and manage all active bots

Each bot record should include:

- ID
- public name
- strategy archetype
- asset universe
- supported horizons
- signal weighting profile
- model and prompt policy
- budget cap
- publication cadence

### Bot Orchestrator

Purpose:

- schedule and manage bot execution

Responsibilities:

- run bots on cadence
- trigger bots on specific events
- enforce budgets
- route tasks to model tiers
- handle retries and failures
- version prompts and workflow configurations

Recommended options:

- `Temporal` for durable workflows
- `Celery + Redis` as a simpler initial implementation

### Bot Runner

Purpose:

- execute each bot's prediction workflow

Core flow:

1. load bot configuration
2. retrieve recent relevant signals
3. construct context pack
4. run prediction generation
5. validate output structure
6. submit to prediction ledger

### Prediction Validator

Purpose:

- block malformed or policy-violating outputs

Checks:

- required fields present
- valid symbol and exchange mapping
- confidence within allowed range
- valid horizon
- source references attached
- language policy checks

### Prediction Ledger

Purpose:

- store immutable published predictions

Ledger fields:

- prediction payload
- bot ID
- input snapshot references
- publish timestamp
- model version
- prompt version
- evaluation status

### Scoring Engine

Purpose:

- evaluate predictions after the prediction horizon expires

Responsibilities:

- load realized market outcomes
- compare direction and price movement
- calculate return capture and confidence calibration
- update rolling bot metrics
- rebuild leaderboard views

### Product Services

Retail services:

- leaderboards
- bot profiles
- prediction history pages
- watchlists
- alerts

Enterprise services:

- API endpoints
- export jobs
- organizational access controls
- usage tracking

### Admin And Governance Layer

Responsibilities:

- create or retire bots
- pause bots
- inspect outputs and score changes
- manage prompts and models
- review source policy violations
- trigger incident controls

## Reference Workflow

1. New market or social input arrives.
2. Input is normalized into a structured signal.
3. Relevant bots are selected based on strategy and coverage.
4. A bot runner assembles a context pack.
5. The model generates a structured prediction.
6. The prediction is validated and stored immutably.
7. Users receive alerts if the prediction meets threshold rules.
8. When the time horizon expires, the scoring engine evaluates the result.
9. Bot and leaderboard metrics are updated.

## Suggested Technology Stack

### Frontend

- `Next.js`
- `TypeScript`
- `Tailwind CSS`
- charting via `Recharts` or `ECharts`

### Backend

- `Python`
- `FastAPI`
- `Pydantic`

### Workflows

- `Temporal` or `Celery + Redis`

### Data

- `Postgres`
- `Redis`
- object storage compatible with `S3`

### Observability

- `OpenTelemetry`
- `Grafana`
- managed logs and traces in the chosen cloud provider

### Authentication

- managed auth provider such as `Clerk` or `Auth0`

## Cost Control Design

Cost discipline should be part of the architecture, not an afterthought.

Recommended controls:

- event-driven bot runs over continuous inference
- lighter models for filtering and summarization
- stronger models only for final prediction generation
- hard token and compute quotas per bot
- budget alerts and automated throttling

## Reliability Requirements

- retry logic for upstream API failures
- dead-letter queues for failed jobs
- bot-level circuit breakers
- provider failover for model inference when possible
- historical replay ability for debugging

## Security And Auditability

- role-based access controls
- encrypted secrets management
- immutable prediction records
- full logging of prompt and model versions
- source provenance stored for every prediction
- records retained for legal and operational review

## Future Architecture Extensions

After the MVP, the platform can expand to support:

- bot teams and firms
- debate and referee workflows
- portfolio construction bots
- user-owned or enterprise-custom bots
- broader market and asset coverage
