# BITprivat Social Trader YouTube Engine

Version 1.0, May 2026

## Purpose

The Social Trader engine monitors public YouTube market creators, converts new videos into explainable trading signals, ranks each creator by simulated follow performance, and lets a retail user deploy a paper-managed allocation to a selected creator.

The current implementation is intentionally paper-first. It creates research and paper-trading signals only. Live copy trading must remain disabled until KYC, suitability, adviser/compliance review, venue authorization, and audit controls are approved.

## User Experience

The dashboard Social Traders section now shows:

- YouTube monitoring mode and cadence
- query/title filters used to find new videos
- public creator avatar with an animated monitoring ring
- follow/deploy controls with delegated capital limits
- ROI windows for 1W, 1M, 1Y, 10Y, and Overall
- current market view inferred from the latest indexed video
- asset exposure and bullish/bearish/neutral bias
- bot decision feed explaining what the system would do and why
- PnL history summary based on simulated paper-follow outcomes
- a managed-paper execution button that converts active creator allocations into capped paper positions

## Data Pipeline

```text
Worker cycle or Scan New Videos button
  -> YouTube search/list ordered by date
  -> videos/list metadata and statistics hydration
  -> channels/list public avatar and channel metadata hydration
  -> public caption/transcript enrichment when available
  -> title + description extraction for asset, direction, confidence
  -> social trader scorecard update
  -> normalized social signals inserted for bot scoring
  -> dashboard decision feed and paper deployment controls
  -> managed-paper execution creates linked predictions and paper positions
```

## Managed-Paper Execution

`POST /api/me/social-traders/execute` evaluates active `managed_paper` allocations, selects high-confidence creator signals, creates normal `social-momentum` predictions linked to the source signal ids, and opens paper positions using the existing paper ledger. It enforces:

- user cash balance
- global paper exposure ceiling
- each creator allocation cap
- max position percent per creator idea
- duplicate position prevention for already-executed source signals

The result returns created predictions, created positions, skipped signals, explanatory messages, and the refreshed paper portfolio snapshot.

## Live Activation

Required production values:

```text
BSM_SOCIAL_DISCOVERY_PROVIDER=youtube
BSM_YOUTUBE_API_KEY=<YouTube Data API key>
BSM_YOUTUBE_DISCOVERY_QUERIES=crypto market prediction bitcoin ethereum,polymarket trading strategy prediction market,macro crypto market analysis
BSM_YOUTUBE_CHANNEL_IDS=<optional comma-separated curated channel IDs>
BSM_YOUTUBE_VIDEO_LIMIT=12
BSM_SOCIAL_DISCOVERY_INTERVAL_SECONDS=1800
BSM_WORKER_INTERVAL_SECONDS=300
```

For continuous monitoring on Akash, deploy the worker SDL:

```powershell
.\deploy\akash\trigger-github-cli-deploy.ps1 -Mode update -WithWorker -ConfirmSpend
```

The GitHub Akash workflows already promote `social_discovery_provider=auto` to `youtube` when `BSM_YOUTUBE_API_KEY` exists as a repository secret.

When the official API returns a temporary quota/auth error, direct video URLs and `@handle`/channel URLs now fall back to public YouTube metadata or public channel RSS. That keeps retail analysis usable while clearly lowering confidence and preserving warning provenance in the discovery ledger.

## Compliance Boundary

- Use official YouTube Data API metadata and public thumbnails.
- Use public captions/transcripts only when YouTube exposes them; otherwise stay on metadata/RSS evidence.
- Do not impersonate creators or fabricate animated faces.
- Show real public channel avatars only with a monitoring animation around the image.
- Keep managed allocation paper-only until legal and operational gates pass.
- Display confidence, evidence, risk notes, and simulated performance as research, not guaranteed returns.

## Next Upgrade

The next material upgrade is deeper transcript intelligence:

- add licensed transcript providers for creators without public captions
- attach source provenance per transcript segment
- run deeper thesis extraction, target/invalidation extraction, and time-horizon detection
- keep every extracted decision auditable back to the source video
