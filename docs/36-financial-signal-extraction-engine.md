# BITprivat Financial Signal Extraction Engine

Version 1.0 - June 2026

## Purpose

The financial signal extraction engine converts trading creator transcripts into strict JSON market claims. It is the first step before price resolution, creator scoring, and managed-paper execution.

This engine does not provide advice, does not create orders, and does not validate performance. It extracts claims only.

## Backend Contract

Runtime module:

- `api/app/financial_signal_extractor.py`

Prompt version:

- `financial-signal-extractor-v1.0`

API route:

- `POST /api/v1/social-traders/extract-signals`
- Compatibility alias: `POST /api/social-traders/extract-signals`

Input:

```json
{
  "video_id": "vid-001",
  "channel_id": "chan-001",
  "video_publish_ts": "2026-06-02T14:02:00Z",
  "language": "en",
  "transcript": "[00:42] I'm long Bitcoin here with a target of 112000 and a stop under 99500 for this week."
}
```

Output:

```json
{
  "video_id": "vid-001",
  "channel_id": "chan-001",
  "video_publish_ts": "2026-06-02T14:02:00Z",
  "language": "en",
  "signals": [
    {
      "asset": "BTC",
      "asset_type": "crypto",
      "direction": "long",
      "claim_type": "tradeable",
      "conviction": 0.66,
      "horizon": "swing",
      "horizon_hours": 168,
      "entry": null,
      "target": 112000.0,
      "invalidation": 99500.0,
      "is_personal_position": true,
      "evidence_quote": "I'm long Bitcoin here with a target of 112000 and a stop under 99500 for this week.",
      "evidence_timestamp_sec": 42,
      "extractor_confidence": 0.8
    }
  ]
}
```

## Extraction Rules

- Extract only from transcript body.
- Ignore video titles and thumbnails.
- Normalize assets, for example `Bitcoin -> BTC`, `Nasdaq -> NDX`, `S&P -> SPX`, `Gold -> GOLD`.
- Emit one asset and one direction per signal.
- Use `tradeable` only for a directional call a user could act on.
- Use `commentary` for broad market opinions with no actionable setup.
- Use `educational` for teaching, definitions, recaps, or historical examples.
- Use `neutral` only for explicit wait/no-trade/chop views.
- Never invent entry, target, or invalidation levels.
- Evidence quotes must be 30 words or fewer.
- If no market claim exists, return `"signals": []`.

## System Prompt

The exact production LLM contract is stored in:

- `FINANCIAL_SIGNAL_EXTRACTION_SYSTEM_PROMPT`

The prompt requires JSON only, no prose, no markdown, no advice, and no fabricated signals.

## Current Implementation

The shipped backend includes:

- Pydantic request/result models.
- Strict quote length validation.
- Canonical asset mapping.
- Direction and claim-type inference.
- Timestamp parsing for `[MM:SS]` and `[HH:MM:SS]` transcript lines.
- Safe deterministic extraction for immediate tests and product demos.

The deterministic extractor is intentionally conservative. It is not the final LLM parser.

## Next Build Step

Wire this contract into the YouTube ingestion worker:

```mermaid
flowchart LR
  YouTube["YouTube video + captions"] --> Extract["financial-signal-extractor-v1.0"]
  Extract --> Store["Structured signal store"]
  Store --> Resolve["Price resolution service"]
  Resolve --> Scores["Creator validation scores"]
  Scores --> UI["Validated / Proxy Social Traders UI"]
```

Required next work:

- Persist extracted `tradeable` signals into a dedicated signal/prediction table.
- Snapshot `price_at_publish`.
- Resolve outcomes after `horizon_hours`.
- Recompute creator scores only from resolved predictions.
- Keep all live trading locked behind legal and risk gates.
