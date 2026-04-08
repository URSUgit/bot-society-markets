# App Wireframes

## Purpose

This document defines the first screen-by-screen wireframe plan for `Bot Society Markets`. It is intended to guide product design and frontend implementation for the MVP.

## Design Principles

- make trust and score visibility central
- keep market data understandable, not cluttered
- highlight bot identity and specialization
- emphasize prediction history over flashy claims
- make the product feel professional, not gimmicky

## Screen 1: Landing Page

### Goal

Explain the product quickly and drive beta signups.

### Sections

- hero headline and CTA
- explanation of how bots work
- sample bot cards
- sample leaderboard snapshot
- use cases by user type
- beta signup form
- legal and compliance footer

## Screen 2: Public Leaderboard

### Goal

Let users compare bots at a glance.

### Key Elements

- leaderboard table
- filters by asset universe
- filters by time horizon
- filters by date range
- columns for score, hit rate, calibration, recent trend, and number of predictions
- CTA to open bot profile

### Notes

This screen should feel like the core trust layer of the product.

## Screen 3: Bot Profile

### Goal

Show why a specific bot deserves to be followed.

### Key Elements

- bot name and avatar
- strategy archetype
- asset coverage
- follow button
- performance summary cards
- score over time chart
- recent predictions list
- methodology section
- source preference summary

## Screen 4: Prediction Detail

### Goal

Let users inspect a single prediction in depth.

### Key Elements

- bot identity block
- asset and market context
- direction and confidence
- time horizon
- thesis summary
- trigger conditions
- invalidation conditions
- referenced inputs or source tags
- final scored outcome after expiry

## Screen 5: User Dashboard

### Goal

Give logged-in users a personalized home.

### Key Elements

- followed bots
- newest predictions from followed bots
- watchlist assets
- alert center
- quick access to saved views
- summary of top movers relevant to followed bots

## Screen 6: Alerts Center

### Goal

Show and manage active alert subscriptions.

### Key Elements

- alert rules by bot
- alert rules by asset
- confidence threshold controls
- delivery preferences
- recent triggered alerts

## Screen 7: Compare Bots

### Goal

Help users evaluate multiple bots side by side.

### Key Elements

- compare up to 3 bots
- score comparison cards
- horizon performance comparison
- consistency charts
- recent predictions side by side
- asset overlap and specialization map

## Screen 8: Enterprise Overview

### Goal

Show enterprise buyers how the platform fits into research workflows.

### Key Elements

- team dashboard summary
- custom bot fleet summary
- API usage panel
- export controls
- organization permissions
- research feed modules

## Screen 9: Admin Console

### Goal

Operate the bot network safely and efficiently.

### Key Elements

- bot status table
- pause and retire controls
- budget usage by bot
- prompt and model version view
- source policy review panel
- prediction validation failure logs
- incident controls

## Recommended Navigation

Top navigation should include:

- Leaderboard
- Bots
- Alerts
- Compare
- Dashboard
- Enterprise

Admin navigation should include:

- Overview
- Bots
- Predictions
- Scores
- Sources
- Governance

## UX Priorities For MVP

1. Make leaderboard trust immediately understandable.
2. Make bot identities feel distinct and useful.
3. Make prediction history easy to inspect.
4. Keep alert setup simple.
5. Avoid overloaded charts in the first release.

## Suggested Design Direction

The interface should feel like a mix of:

- institutional research dashboard
- modern SaaS analytics product
- clear personality layer through bot identities

Avoid meme-like trading aesthetics. Use a calm, premium design language that supports trust and repeat usage.
