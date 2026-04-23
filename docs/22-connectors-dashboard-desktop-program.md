# Connectors, Dashboard, and Desktop Program

## Objective

Ship the next product surface in a way that feels professional:

- stronger API connector coverage
- a more intuitive and monetization-aware dashboard
- installable Windows and macOS distribution

## API Connector Program

### Current live connector base

- Hyperliquid public market data
- CoinGecko market fallback
- Polymarket venue intelligence
- Kalshi venue intelligence
- FRED macro data
- RSS and Reddit signal sources
- Polymarket wallet tracking

### Next connector categories

#### Revenue connectors

- Stripe Checkout session creation
- Stripe webhook ingestion
- Stripe Customer Portal session creation
- Coinbase Onramp session creation
- Coinbase onboarding event reconciliation

#### Customer and operations connectors

- outbound CRM or support webhook
- enterprise export delivery webhook
- account entitlement sync
- audit and incident notifications

#### Future enterprise connectors

- API key issuance and rotation
- usage metering
- export job status callbacks
- SSO or identity-provider hooks

## Connector Design Rules

- every connector gets a named owner
- every connector gets a retry and reconciliation policy
- every connector gets a dashboard health state
- secrets stay server-side only
- every external callback lands in an immutable event ledger

## Dashboard Redesign Brief

The current dashboard already has strong command-center energy. The next redesign should focus on clarity, commercialization, and operator confidence.

### What to add next

- pricing and plan state
- onboarding rail state for fiat and crypto
- connector health board
- entitlement state for account tier and limits
- support and incident panel
- desktop install call-to-action

### Recommended information architecture

1. Live market pulse
2. Commercial launch pulse
3. Account tier and onboarding state
4. Signals, wallets, and edge
5. Strategy Lab and exports
6. Connector and legal operations

### UX principles

- keep the immersive command-center look
- make commercial actions explicit, not hidden
- separate `research insight` from `commercial state`
- use clear status labels like `selected`, `building`, `ready`, `live`
- show blockers, not just good news

## Desktop App Recommendation

Use `Tauri` as the first desktop shell.

Why:

- lighter than Electron
- native installers for Windows and macOS
- good fit for a hosted dashboard shell
- easier to keep the web UI as the main surface

Tauri officially documents Windows and macOS prerequisites plus bundling workflows.

Official reference:

- [Tauri prerequisites](https://v2.tauri.app/start/prerequisites/)
- [Tauri Windows bundling](https://v1.tauri.app/v1/guides/building/windows/)

## Desktop App Architecture

### Phase 1

Hosted web app inside a desktop shell:

- Tauri loads `https://app.bitprivat.com`
- authentication stays server-side
- Stripe and Coinbase flows open in the system browser
- desktop app focuses on convenience and notifications

### Phase 2

Add desktop-native features:

- local notification hooks
- cached last-view state
- deeper watchlist quick actions
- system tray or menu-bar shortcuts

## Distribution Strategy

### Windows

Microsoft now recommends Microsoft Store MSIX submissions for most new apps because Microsoft re-signs the package and users avoid SmartScreen warnings.

Official references:

- [Windows code signing options](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options)
- [SmartScreen reputation guidance](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation)
- [Smart App Control signing guidance](https://learn.microsoft.com/en-us/windows/apps/develop/smart-app-control/code-signing-for-smart-app-control)

Recommended path:

- first target `Microsoft Store MSIX`
- keep direct installer as a secondary channel only if needed

### macOS

Apple documents that software distributed outside the Mac App Store should use Developer ID signing and notarization.

Official references:

- [Apple Developer ID](https://developer.apple.com/support/developer-id/)
- [Notarizing macOS software](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution)

Recommended path:

- distribute outside the Mac App Store at first
- sign with Developer ID
- notarize every release

## Required Desktop Config

Recommended project variables:

- `BSM_DESKTOP_APP_FRAMEWORK`
- `BSM_DESKTOP_BUNDLE_ID`
- `BSM_APPLE_DEVELOPER_TEAM_ID`
- `BSM_WINDOWS_DISTRIBUTION_CHANNEL`

## Delivery Sequence

1. finalize desktop shell architecture
2. create Tauri workspace
3. package Windows beta
4. package notarized macOS beta
5. add desktop download surface to dashboard and landing
6. add versioning and release notes flow
