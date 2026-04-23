# Payments and Onboarding Architecture

## Goal

Design a commercially credible onboarding stack for:

- fiat card subscriptions
- wallet funding with fiat-to-crypto rails
- optional crypto-denominated settlement

The architecture should minimize regulatory load by using hosted providers wherever possible.

## Recommended Provider Stack

| Capability | Primary choice | Why | Fallback |
| --- | --- | --- | --- |
| Fiat subscriptions and cards | `Stripe Checkout + Billing` | Hosted checkout, subscriptions, customer portal, and tax support in one stack | none initially |
| Wallet funding | `Coinbase-hosted Onramp` | Hosted user flow, Coinbase account or guest checkout, card and wallet-friendly rails | `MoonPay` if regional coverage requires it |
| Crypto-denominated settlement | `Coinbase Commerce` | Useful for account credits or enterprise settlement without building custody | stay disabled until needed |

## Why Stripe for Fiat

Stripe officially documents that Checkout is a prebuilt hosted payment page and supports one-time and subscription payments through Checkout Sessions.

Stripe also documents that low-risk integrations such as Checkout and Stripe-hosted payment collection reduce PCI burden compared with handling untokenized card data directly.

Official references:

- [Stripe Checkout](https://docs.stripe.com/payments/checkout)
- [Stripe Subscriptions](https://docs.stripe.com/subscriptions)
- [Stripe Integration Security Guide](https://docs.stripe.com/security/guide)
- [Stripe Security Overview](https://docs.stripe.com/security/stripe)

## Why Coinbase-hosted Onramp for Crypto Funding

Coinbase's official docs state that Coinbase Onramp lets users convert fiat into crypto and send it to any wallet, with a hosted flow that supports Coinbase-account onboarding and guest checkout options.

Official references:

- [Coinbase Onramp Overview](https://docs.cdp.coinbase.com/onramp/onramp-overview)
- [Coinbase-hosted Onramp Quickstart](https://docs.cdp.coinbase.com/onramp/introduction/getting-started)
- [Coinbase-hosted Onramp Overview](https://docs.cdp.coinbase.com/onramp/coinbase-hosted-onramp/overview)
- [Coinbase Onramp and Offramp Overview](https://docs.cdp.coinbase.com/onramp/docs/api-reporting/)

## Why MoonPay Is a Secondary Rail

MoonPay officially documents a hosted on-ramp widget that can be embedded in a web app or mobile web view, with KYC and payment-method handling inside the provider flow.

Official reference:

- [MoonPay On-Ramp Overview](https://dev.moonpay.com/docs/on-ramp-overview)

## Architecture Principles

- hosted checkout first
- hosted onboarding first
- no direct fiat custody
- no direct crypto custody
- event ledger for every commercial provider callback
- entitlement state derived from reconciled billing events, not browser assumptions

## Recommended Event Flow

### Fiat subscriptions

1. User selects plan in the dashboard.
2. Backend creates a Stripe Checkout Session.
3. User completes payment on Stripe-hosted checkout.
4. Stripe sends webhook events.
5. Backend records events in a billing ledger.
6. Entitlements are updated only after webhook confirmation.
7. Dashboard reflects active plan, limits, and renewal state.

### Crypto onboarding

1. User opens wallet funding panel.
2. Backend generates a Coinbase-hosted Onramp session.
3. User completes KYC and payment inside Coinbase.
4. Coinbase webhook or polling confirms completion.
5. Platform records provider event and assigns resulting wallet-funding state.
6. Dashboard shows success, pending, or support-needed state.

### Optional crypto settlement

1. User or enterprise customer selects crypto settlement.
2. Backend creates a Commerce charge or equivalent provider object.
3. Provider confirms settlement through webhook.
4. Backend records event and issues credits or marks invoice paid.

## Internal Components To Add

### Billing service

Responsibilities:

- create Checkout Sessions
- create portal sessions
- map plans to entitlements
- store provider customer IDs and subscription IDs

### Onboarding service

Responsibilities:

- create hosted onramp sessions
- attach wallet destination metadata
- store provider session IDs
- reconcile success, pending, failed, and expired sessions

### Event ledger

Store:

- provider name
- event type
- external event ID
- received timestamp
- signature verification result
- normalized payload
- reconciliation status

### Entitlement engine

Drive:

- dashboard access tiers
- signal history depth
- export access
- Strategy Lab limits
- enterprise connector access

## Secrets and Environment Variables

Recommended project variables:

- `BSM_FIAT_BILLING_PROVIDER`
- `BSM_STRIPE_PUBLISHABLE_KEY`
- `BSM_STRIPE_SECRET_KEY`
- `BSM_STRIPE_WEBHOOK_SECRET`
- `BSM_STRIPE_BASIC_PRICE_ID`
- `BSM_STRIPE_CUSTOMER_PORTAL_ENABLED`
- `BSM_CRYPTO_ONRAMP_PROVIDER`
- `BSM_COINBASE_ONRAMP_API_KEY`
- `BSM_COINBASE_ONRAMP_APP_ID`
- `BSM_CRYPTO_CHECKOUT_PROVIDER`
- `BSM_COINBASE_COMMERCE_API_KEY`
- `BSM_MOONPAY_API_KEY`

## Implementation Order

1. Add billing ledger tables and webhook verification
2. Add plan and entitlement mapping
3. Add Stripe Checkout session creation
4. Add Stripe portal session creation
5. Add Coinbase-hosted Onramp session creation
6. Add commercial event monitoring in the dashboard
7. Add support tooling for failed or pending onboarding states

## Hard Boundaries

- Do not put raw card capture into the custom frontend first.
- Do not release crypto custody features in this phase.
- Do not let client-side UI alone determine paid access.
- Do not market crypto onboarding as investment performance or advisory help.
