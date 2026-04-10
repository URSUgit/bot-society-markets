# Prediction Market Adapter Guide

## Purpose

This guide explains the Strategy Lab adapter package for `prediction-market-backtesting`.

The adapter package is intentionally a bridge, not a fake one-click import.

`Bot Society Markets` currently runs asset-level simulations on BTC, ETH, and SOL history. `prediction-market-backtesting` replays specific Polymarket markets with PMXT historical order-book data. Those are related workflows, but they are not the same dataset or execution model.

## What The Adapter Pack Does

Each advanced export writes a companion ZIP package alongside the JSON export artifact.

The ZIP contains:

- the original Bot Society export bundle
- `adapter_manifest.json`
- `market_mapping_template.json`
- `strategy_config.json`
- `runner_template.py`
- `pmxt.env.example`
- `README.md`

## Why This Is The Right Shape

This is the professional boundary:

- our Strategy Lab is fast and thesis-oriented
- `prediction-market-backtesting` is venue-specific and execution-oriented
- a serious workflow should map one into the other explicitly

That gives us a path from:

- quick research
- to market selection
- to order-book replay
- to more realistic execution validation

without pretending those are the same backtest.

## External Repo Contract We Aligned To

On April 10, 2026, the public `prediction-market-backtesting` repository exposed:

- a public runner contract with `NAME`, `DESCRIPTION`, `DATA`, `REPLAYS`, `STRATEGY_CONFIGS`, `REPORT`, `EXECUTION`, `EXPERIMENT`, and `run()`
- PMXT local raw archive layouts for `polymarket_orderbook_YYYY-MM-DDTHH.parquet`
- required raw parquet columns:
  - `market_id`
  - `update_type`
  - `data`
- required JSON payload types:
  - `book_snapshot`
  - `price_change`

The adapter pack mirrors those assumptions in a way that is safe to hand off to a quant or operator.

## Recommended Workflow

1. Run a Strategy Lab simulation inside Bot Society Markets.
2. Generate the advanced export.
3. Download the adapter pack.
4. Choose a Polymarket market whose thesis matches the exported asset view.
5. Fill in `market_mapping_template.json` with market slug, token index, condition ID, and token ID.
6. Review `strategy_config.json` and tune the suggested mapping.
7. Copy `runner_template.py` into the external repo and execute the backtest there.

## Strategy Mapping

Current preset mapping:

- `trend_follow` -> `QuoteTickEMACrossoverStrategy`
- `mean_reversion` -> `QuoteTickMeanReversionStrategy`
- `breakout` -> `QuoteTickBreakoutStrategy`
- `buy_hold` -> `QuoteTickDeepValueHoldStrategy` as a long-only proxy

The last mapping is intentionally approximate and should be treated as a benchmark proxy, not an exact equivalent.

## Next Step

The next logical upgrade is a dedicated market-mapping workspace where a user can attach one Strategy Lab export to one or more specific Polymarket markets and generate a fully populated runner file without placeholders.
