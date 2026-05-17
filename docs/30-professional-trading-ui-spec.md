# BITprivat Professional Trading UI Specification

Version 1.0 - May 2026

## Product Direction

BITprivat must feel like a serious trading workstation, not a collection of dashboards. The UI prioritizes live price, unrealized P&L, order safety, and fast comprehension. Social trading, bots, simulation, and connectors stay available, but the main mental model is:

1. Read market state.
2. Understand exposure and risk.
3. Preview an action.
4. Confirm only when the impact is clear.

## Mandatory Design Principles

### 1. Financial Clarity

Every financial value must include unit, direction, and context:

- P&L: `+$1,284.44 USD`, direction shown by sign and profit/loss color.
- Average price: `avg $100,786.10 USD`.
- Fee: `Est. fee $3.94 USD`.
- Margin: `Est. margin $5,192.11 USD`.
- Leverage: explicit selector, never hidden.
- Liquidation price: visible when margin/perps/CFDs are involved.
- Side: `Long`, `Short`, `Buy Yes`, `Sell No`, not ambiguous.

### 2. Visual Hierarchy

Most visible:

- Live price.
- Unrealized P&L.
- Current position side and size.

Second priority:

- Order ticket preview.
- Order book spread.
- Margin, fee, buying power.

Destructive actions:

- `Market sell`, `Close partial`, `Close all`, `Cancel all`.
- Always require confirmation.
- Use danger styling only for destructive actions and negative P&L, not decoration.

### 3. Trading Semiotics

Color is semantic:

- `--color-profit`: positive P&L only.
- `--color-loss`: negative P&L only.
- `--color-bid`: bid/depth liquidity.
- `--color-ask`: ask/depth liquidity.
- `--color-warning`: margin and delayed data warnings.
- `--color-margin-call`: liquidation/margin call warnings.

No random green/red decorative cards.

### 4. Perceived Performance

The UI must show continuous progress:

- Skeleton loaders for initial dashboard state.
- Debounced symbol search.
- Optimistic UI only where safe, such as local watchlist highlighting.
- No animation on live numbers; only subtle 300ms flash on price direction.
- Long lists should be virtualized once they exceed 200 rows.

### 5. Accessibility

Target WCAG 2.1 AA:

- Contrast at least 4.5:1 for text.
- Keyboard focus rings on every button, input, select, link.
- Screen-reader labels for order side, order book prices, positions, and destructive buttons.
- Tables keep clear column labels on desktop and card-like rows on mobile.

### 6. Theme

Default is dark mode with a neutral slate/zinc palette and a single blue/cyan brand accent. Light mode is supported by tokens, not by duplicating components.

## Design System

### Typography

- UI: Inter or Geist.
- Financial numbers: tabular numerals via `font-variant-numeric: tabular-nums`.
- Headings: modern sans, no decorative serif in the trading app.

### Spacing

- Base grid: 4px.
- Pro density: about 20% less padding than Simple mode.
- Simple mode uses larger controls and fewer columns.

### Tokens

```css
--color-profit: #22c55e;
--color-loss: #ef4444;
--color-bid: #2dd4bf;
--color-ask: #fb923c;
--color-warning: #facc15;
--color-margin-call: #f97316;
```

### Components

- `Button`: primary, secondary, ghost, danger.
- `Input`.
- `Select`.
- `Tabs`.
- `Badge`.
- `Tooltip`.
- `Modal`.
- `Drawer`.
- `Toast`.
- `DataTable`.
- `OrderTicket`.
- `PositionRow`.
- `WatchlistRow`.
- `ChartToolbar`.
- `StatusPill`: connected, disconnected, delayed.

## Information Architecture

### 1. Onboarding & Auth

Screens:

- Login.
- Register.
- 2FA.
- Forgot password.
- KYC wizard: identity -> address proof -> pending verification.
- Risk disclosure.
- Appropriateness test, simplified in Simple mode.

### 2. Dashboard

Simple:

- Total portfolio.
- Top 3 positions.
- 5-symbol watchlist.
- Primary CTA: `Tranzactioneaza`.

Pro:

- Configurable grid.
- Chart.
- Order Book.
- Order Ticket.
- Positions.
- Watchlist.
- News.
- Account Summary.

### 3. Trading Workspace

Pro layout:

```text
+----------------+------------------------------+----------------------+
| Watchlist      | Chart + live price + uPnL     | Order Ticket         |
| Search/filter  | Toolbar: TF/indicators/full   | Order Book           |
| Asset groups   | Account summary strip         | Recent Trades        |
+----------------+------------------------------+----------------------+
| Open Positions | Open Orders | Order History | Trade History | Funding |
+-----------------------------------------------------------------------+
```

Simple layout:

```text
+-----------------------------------------------------------------------+
| Large chart + live price                                               |
| Symbol selector | Fiat amount | Buy | Sell                             |
| Two-step confirmation with fee, margin, side and risk summary          |
+-----------------------------------------------------------------------+
```

### 4. Portfolio

- Equity.
- Cash.
- Margin used %.
- Buying power.
- Daily P&L.
- Asset-class breakdown.
- Performance history: 1D, 1W, 1M, 1Y, ALL.
- CSV export.

### 5. Markets / Discover

Tabs:

- Crypto.
- Stocks.
- Forex.
- Trending.
- Gainers.
- Losers.

Card fields:

- Price.
- Change %.
- Volume.
- 24h sparkline.
- Asset class, region, sector, market cap filters.

### 6. Positions & Orders

Mobile must support this as a standalone screen:

- Symbol.
- Side.
- Size.
- Entry.
- Mark.
- uPnL.
- Liquidation price when applicable.
- Actions: Close, TP/SL, Add margin.
- Pro bulk actions: close all, cancel all orders.

### 7. Wallet / Funds

- Deposit fiat.
- Deposit crypto with network warning.
- Withdraw with 2FA and address whitelist.
- Transfer spot <-> futures.
- Transaction history with status pipeline.

### 8. Settings & Profile

- Security: 2FA, sessions, read-only API keys for Pro.
- Preferences: RO/EN, timezone, Simple/Pro default, order confirmations.
- Pro layout presets.
- Notifications: price alerts, fills, margin calls, funding.

### 9. Special States

Must be explicitly designed:

- Initial loading.
- WebSocket reconnecting.
- Market closed.
- Maintenance.
- Insufficient margin.
- Order rejected with code and human message.
- Partial fill.
- Persistent liquidation warning banner.

## Critical Flows

### 1. Market Order - Simple

```text
Select symbol -> Enter fiat amount -> Buy/Sell -> Review fee/risk -> Confirm -> Toast fill
```

Microcopy:

> Ordinul tau a fost executat partial: 0.5 / 1.0 BTC

### 2. Limit + TP/SL - Pro

```text
Open ticket -> Select Limit -> Enter quantity and price -> Attach TP/SL -> Preview impact -> Submit -> Appears in Open Orders
```

### 3. Partial Position Close

```text
Position row -> Close partial -> Quantity modal -> Confirm -> Position size updates
```

Microcopy:

> Esti pe cale sa inchizi o pozitie short. Actiunea nu poate fi anulata dupa executie.

### 4. Margin Call

```text
Persistent red/orange banner -> User chooses reduce position or add collateral -> Countdown if applicable -> Alert delivered
```

Microcopy:

> Marja disponibila insuficienta. Adauga fonduri sau reduce leverage.

### 5. Simple <-> Pro Switch

```text
Toggle mode -> Layout changes under 200ms -> Preference persists -> First-time tooltip explains density and risk controls
```

## Live Data Feedback

- Price ticks flash up/down for 300ms.
- Order book level click populates ticket price.
- Connection indicator states: `Live`, `Delayed 15m`, `Offline`.
- All timestamps use user timezone.

## Current Implementation

Implemented in:

- `api/app/static/dashboard.html`
- `api/app/static/styles.css`
- `api/app/static/app.js`

The new workspace is a front-end control surface and demo-safe interaction layer. Live execution remains gated until legal, KYC, broker, and risk checks are fully operational.
