# Commercial Expansion Program

## Objective

Turn `Bot Society Markets` from a research-grade signal platform into a commercial product with:

- fiat card onboarding
- crypto wallet funding and optional crypto settlement
- enterprise-grade API connectors
- a more conversion-ready dashboard
- installable Windows and macOS apps
- a legal and compliance operating pack that keeps the launch perimeter controlled

## Recommended Product Position

The product should stay in the `research, analytics, alerts, and simulation` lane until outside counsel approves any broader claims or features.

That means:

- do not auto-execute customer trades yet
- do not custody customer fiat or crypto
- do not market the product as personalized investment advice
- do not launch copy-trading until the licensing analysis is complete

## Three-Phase Program

### Phase 1: Revenue Foundation

Timeline: `2 to 4 weeks`

Goals:

- add fiat subscription billing architecture
- lock the crypto onboarding provider stack
- define the commercialization information architecture inside the dashboard
- create the legal document pack and ownership list

Deliverables:

- Stripe integration design
- Coinbase Onramp or MoonPay decision
- webhook event ledger design
- entitlement model for paid plans
- Terms, Privacy, Cookie, and Risk Disclosure drafts

Exit criteria:

- provider decisions approved
- commercial plan tiers approved
- legal review workstream scheduled

### Phase 2: Controlled Implementation

Timeline: `4 to 6 weeks`

Goals:

- implement hosted fiat checkout and billing webhooks
- implement hosted crypto onboarding and reconciliation
- ship connector health for payments and onboarding providers
- redesign dashboard for onboarding, subscription state, and operator visibility
- start the desktop shell

Deliverables:

- Stripe Checkout sessions and webhook handling
- Coinbase-hosted Onramp integration
- subscription entitlements
- payment and connector event log
- Tauri desktop shell proof of concept

Exit criteria:

- users can subscribe without manual ops
- users can fund wallets through a hosted crypto flow
- operator dashboards show billing and onboarding events

### Phase 3: Production Launch Hardening

Timeline: `3 to 5 weeks`

Goals:

- move to managed Postgres everywhere
- prepare Windows and macOS distribution
- finish legal and compliance pack
- run launch readiness and incident drills

Deliverables:

- production Postgres cutover
- Windows MSIX distribution plan
- Apple notarization workflow
- support, complaints, sanctions, and incident playbooks
- launch checklist with named owners

Exit criteria:

- production database and secrets governance in place
- signed desktop distribution path ready
- counsel-approved commercial boundary documented

## Workstreams

### 1. Payments

- Stripe for subscriptions and fiat card onboarding
- hosted checkout first
- entitlement mapping second
- billing automation third

### 2. Crypto Onboarding

- Coinbase-hosted Onramp first
- MoonPay only if geography or partner constraints require it
- optional Coinbase Commerce for crypto-denominated account credits or enterprise settlement

### 3. API Connectors

- keep market intelligence connectors live
- add Stripe webhooks
- add Coinbase webhooks
- add CRM and outbound operations hooks
- add enterprise export endpoints

### 4. Product and Dashboard

- keep the command-center visual language
- add pricing, onboarding, connector health, and entitlement surfaces
- make subscription status and desktop install CTAs visible

### 5. Desktop Distribution

- use `Tauri` for a lightweight desktop shell
- route payment flows through the system browser
- ship Windows through Microsoft Store if possible
- notarize macOS builds with Apple Developer ID

### 6. Legal and Compliance

- company and contracting perimeter
- privacy and cookies
- payments and PCI
- crypto regulatory perimeter
- advisory and copy-trading perimeter
- sanctions and complaints handling

## Launch Gates

### Gate A: Payment Safety

Can users subscribe through hosted checkout without the app handling raw card data?

### Gate B: Crypto Perimeter

Is crypto onboarding fully handled by third-party regulated providers with clear disclosures and no direct custody by the product?

### Gate C: Regulatory Boundary

Do product claims, onboarding, alerts, and public pages clearly keep the service on the research side of the line until counsel approves more?

### Gate D: Desktop Trust

Can Windows and macOS users install signed software without security warnings that damage trust?

## KPI Targets

- subscription conversion from dashboard visit
- activation rate from signup to first watchlist or alert
- percent of successful payment webhooks reconciled automatically
- percent of successful onramp funding events reconciled automatically
- connector uptime by provider
- average time to resolve failed billing or onboarding events

## Recommended Sequence

1. Stripe architecture and entitlements
2. Coinbase-hosted Onramp
3. payment and onboarding event ledger
4. dashboard redesign for conversion and operator controls
5. Tauri shell
6. legal pack and launch checklist
