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

## Data Pipeline

```text
Worker cycle or Scan New Videos button
  -> YouTube search/list ordered by date
  -> videos/list metadata and statistics hydration
  -> channels/list public avatar and channel metadata hydration
  -> title + description extraction for asset, direction, confidence
  -> social trader scorecard update
  -> normalized social signals inserted for bot scoring
  -> dashboard decision feed and paper deployment controls
```

## Live Activation

Required production values:

```text
BSM_SOCIAL_DISCOVERY_PROVIDER=youtube
BSM_YOUTUBE_API_KEY=<YouTube Data API key>
BSM_YOUTUBE_DISCOVERY_QUERIES=crypto market prediction bitcoin ethereum,polymarket trading strategy prediction market,macro crypto market analysis
BSM_YOUTUBE_CHANNEL_IDS=<optional comma-separated curated channel IDs>
BSM_YOUTUBE_VIDEO_LIMIT=12
BSM_WORKER_INTERVAL_SECONDS=300
```

For continuous monitoring on Akash, deploy the worker SDL:

```powershell
.\deploy\akash\trigger-github-cli-deploy.ps1 -Mode update -WithWorker -ConfirmSpend
```

The GitHub Akash workflows already promote `social_discovery_provider=auto` to `youtube` when `BSM_YOUTUBE_API_KEY` exists as a repository secret.

## Compliance Boundary

- Use official YouTube Data API metadata and public thumbnails.
- Do not impersonate creators or fabricate animated faces.
- Show real public channel avatars only with a monitoring animation around the image.
- Keep managed allocation paper-only until legal and operational gates pass.
- Display confidence, evidence, risk notes, and simulated performance as research, not guaranteed returns.

## Next Upgrade

The next material upgrade is transcript enrichment:

- fetch captions/transcripts where legally available
- fall back to user-provided or licensed transcript providers
- attach source provenance per transcript segment
- run deeper thesis extraction, target/invalidation extraction, and time-horizon detection
- keep every extracted decision auditable back to the source video
