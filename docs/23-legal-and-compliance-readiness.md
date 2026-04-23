# Legal and Compliance Readiness

## Important Framing

This is an operating checklist, not legal advice.

Before paid production launch, the project should retain counsel with payments, fintech, privacy, and securities experience in the jurisdictions where it will sell.

## Recommended Launch Perimeter

Until counsel says otherwise, launch as:

- research and analytics software
- signal monitoring and alerting
- simulation and backtesting
- workspace tooling

Do not launch as:

- a custodian
- a broker
- a trading venue
- an auto-trading or copy-trading product
- a personalized investment adviser

## Why This Boundary Matters

### United States

FinCEN guidance states that users of virtual currency are not necessarily MSBs, but administrators or exchangers can fall inside money transmitter scope depending on activity.

Official references:

- [FinCEN virtual currency guidance](https://www.fincen.gov/resources/statutes-regulations/guidance/application-fincens-regulations-persons-administering)
- [FinCEN release summary](https://www.fincen.gov/news/news-releases/fincen-issues-guidance-virtual-currencies-and-regulatory-responsibilities)

### European Union

MiCA establishes rules for crypto-asset service providers and crypto-related services in the Union, while ESMA has separately issued supervisory guidance for copy-trading services.

Official references:

- [MiCA overview](https://eur-lex.europa.eu/EN/legal-content/summary/european-crypto-assets-regulation-mica.html?app=true)
- [MiCA full text](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=celex%3A32023R1114)
- [ESMA copy-trading supervision guidance](https://www.esma.europa.eu/press-news/esma-news/esma-provides-guidance-supervision-copy-trading-services)

### Investment-advice perimeter

The SEC has published guidance and investor education material on robo-advisers, which is relevant whenever software starts to look like algorithmic investment advice.

Official references:

- [SEC robo-adviser press release and bulletin](https://www.sec.gov/newsroom/press-releases/2017-52)
- [SEC automated investment advice hub](https://www.sec.gov/about/divisions-offices/office-strategic-hub-innovation-financial-technology-finhub/automated-investment-advice)

## Privacy and Data Protection

GDPR applies when offering goods or services to people in the EU or monitoring their behavior there.

Official reference:

- [GDPR text](https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=celex%3A32016R0679)

Minimum privacy program:

- Privacy Policy
- Terms of Service
- Cookie Notice and consent handling where required
- data retention schedule
- subprocessors inventory
- DPA template if selling to enterprise buyers
- privacy contact email

## Payments and PCI

Stripe states that PCI compliance is shared responsibility, but hosted low-risk integrations reduce exposure compared with handling raw card data directly.

Official references:

- [Stripe integration security guide](https://docs.stripe.com/security/guide)
- [Stripe Checkout](https://docs.stripe.com/payments/checkout)

Rule:

- do not build a custom raw-card capture flow first
- use hosted checkout first

## Crypto Operating Model

To keep the regulatory posture lighter:

- let Coinbase or MoonPay handle KYC inside hosted onboarding
- do not custody user wallets or private keys
- do not intermediate funds between unrelated parties
- record provider events and disclosures carefully

## Copy Trading and Execution

This is the highest-risk expansion area.

Before shipping anything that mirrors or auto-executes trades:

- get a formal US and EU regulatory analysis
- review MiFID and MiCA implications
- review adviser, signal, and discretionary management implications
- review whether trader ranking and social-trading features create inducement, suitability, or disclosure obligations

## Legal Document Pack

Before paid launch, prepare:

- Terms of Service
- Privacy Policy
- Cookie Notice
- Risk Disclosure
- Acceptable Use Policy
- Refund and billing policy
- enterprise order form template
- vendor due-diligence folder for Stripe, Coinbase, MoonPay, hosting, email, and analytics tools

## Compliance Operating Checklist

### Corporate

- legal entity established
- banking and accounting workflow established
- cap table and signing authority clear

### Product claims

- avoid promises of profit
- avoid language implying personalized advice
- distinguish clearly between research output and execution

### Support and complaints

- support email and SLA
- escalation path for billing and onboarding issues
- complaints log

### AML and sanctions

- named owner for sanctions and AML coordination
- policy for responding to provider flags and law-enforcement requests
- prohibited-jurisdiction screening policy if required by providers

### Security and incident response

- named incident owner
- webhook signature verification
- secret rotation process
- breach notification playbook

## Desktop Distribution Compliance

### Windows

Microsoft documents that Store MSIX distribution is re-signed by Microsoft and avoids SmartScreen warnings for most new apps.

### macOS

Apple documents that Developer ID signing and notarization are required for software distributed outside the Mac App Store under normal Gatekeeper expectations.

Official references:

- [Windows code signing options](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options)
- [Apple Developer ID](https://developer.apple.com/support/developer-id/)
- [Apple notarization](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution)

## Mandatory Go-Live Checklist

- counsel retained and launch memo delivered
- operating entity and jurisdiction recorded
- Terms, Privacy, Cookie, and Risk pages published
- payment flows hosted and webhook-verified
- crypto onboarding flows hosted and provider terms linked
- no direct custody of customer funds or keys
- no auto-execution or copy trading without separate approval
- support, complaints, and incident ownership assigned
- Windows and macOS releases signed appropriately

## Practical Recommendation

The safest professional next move is:

1. monetize the analytics product first
2. keep onboarding hosted through regulated third-party providers
3. stay out of custody and execution
4. delay copy trading until the licensing and disclosure pack is approved
