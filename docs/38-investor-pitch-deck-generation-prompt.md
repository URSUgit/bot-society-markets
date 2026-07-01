# BITprivat Investor Pitch Deck Generation Prompt

Version 1.0 - July 1, 2026  
Purpose: Copy-ready prompt for generating a professional investor presentation  
Audience: Strategic seed investor considering an equal 50/50 partnership  
Output language: English  
Currency: EUR unless a cited source uses another currency

## Copy-Ready Prompt

```text
You are an institutional-quality venture capital presentation strategist, fintech product expert, financial modeler, and information designer.

Create a polished, evidence-based investor pitch deck for BITprivat. The deck must be suitable for a serious strategic investor evaluating a EUR 1.5 million investment and an equal founder-investor partnership. It must explain the product clearly to an investor who understands software and finance but is not necessarily a quantitative trader.

Do not write a generic crypto pitch. Do not promise investment returns. Do not invent users, revenue, partnerships, licenses, historical performance, regulatory approvals, or product capabilities. Clearly separate:

1. What exists and is demonstrable today.
2. What is partially implemented.
3. What is planned.
4. What requires legal, security, data-license, or venue approval.
5. What is an illustrative financial projection rather than observed performance.

The deck should position BITprivat as an approachable Market Intelligence and Strategy OS that turns an investment idea into an understandable, evidence-backed simulation without requiring code.

BITprivat combines:

- a beginner-friendly Data Library;
- guided strategy creation in normal language;
- historical research and backtesting;
- strategy optimization with anti-overfitting controls;
- creator and social-trader intelligence built from public evidence;
- prediction-market, crypto, macro, and social data connectors;
- transparent performance reports and provenance;
- paper-first strategy deployment;
- optional Pro tools powered by the open-source LEAN engine;
- gated live execution only after legal, security, risk, and operational approval.

The simple product journey is:

Explore Data -> Describe an Idea -> Build Rules -> Test on History -> Understand Risk -> Practice with Paper Money -> Seek Approval for Live Deployment

The differentiated thesis is:

Most platforms give professional traders more tools. BITprivat makes institutional research discipline understandable to normal people while preserving evidence, auditability, and professional controls underneath.

Use these project source files as the internal source of truth:

- docs/00-founder-memo.md
- docs/01-product-requirements-document.md
- docs/03-technical-architecture.md
- docs/04-financial-model.md
- docs/05-execution-roadmap.md
- docs/06-investor-memo.md
- docs/09-founder-deck-script.md
- docs/20-commercial-expansion-program.md
- docs/23-legal-and-compliance-readiness.md
- docs/24-bitprivat-business-model-strategy.md
- docs/33-bitprivat-master-rebuild-plan.md
- docs/37-quantconnect-capability-and-retail-ux-plan.md

If source files conflict, use this prompt as the controlling financial and transaction assumption, while identifying the conflict in the appendix.

CURRENT PRODUCT TRUTH

Present current progress honestly:

- A working FastAPI-based product is deployed publicly through Cloudflare and Akash.
- The platform includes authentication foundations, market-data adapters, provider status, strategy creation, basic backtesting, paper-order preview and risk checks, audit events, social-trader research, and legal/risk pages.
- Existing market adapters include Binance, CoinGecko, and Hyperliquid modes.
- Existing venue-intelligence adapters include Polymarket and Kalshi public information.
- YouTube creator discovery and financial-signal extraction exist, but current production social discovery may operate in demo/research mode.
- The present production database is a temporary SQLite configuration; shared managed Postgres is a required near-term infrastructure milestone.
- Strategy Lab and paper trading are MVP-level capabilities, not yet institutional execution infrastructure.
- Live trading is not commercially ready and must remain gated.
- No audited revenue, paid-user traction, validated commercial retention, or counsel-approved live-trading authorization has been provided. Do not imply otherwise.

PRODUCTS AND REVENUE

Show one shared engine supporting two products:

1. BITprivat Personal
   - Free: data discovery, selected market views, and limited tests.
   - Explore: approximately EUR 29/month for expanded data, saved ideas, and reports.
   - Automate: approximately EUR 99/month for advanced tests, creator bots, and paper deployments.
   - Team: approximately EUR 299/month for multiple seats, shared strategies, approvals, and higher limits.

2. BITprivat Enterprise OS
   - Research and intelligence pilots from approximately EUR 25,000 ARR.
   - Growth contracts around EUR 50,000-100,000 ARR.
   - Private deployment, white-label, API, security, and custom connector contracts above EUR 100,000 ARR.

Additional future revenue may come from licensed premium datasets, usage-based API access, strategy packs, private connectors, and white-label deployments. Do not include performance fees or assets-under-management revenue in the base model because those require separate legal analysis.

INVESTMENT PROPOSAL

Use this as an illustrative transaction for discussion, not a binding offer:

- Investment: EUR 1,500,000 in primary capital.
- Investor ownership at closing before any employee option pool: 50%.
- Founder ownership at closing before any employee option pool: 50%.
- Implied pre-money valuation: EUR 1,500,000.
- Implied post-money valuation: EUR 3,000,000.
- Security: preferred equity or local legal equivalent, subject to counsel.
- Liquidation preference: illustrative 1x non-participating preference.
- Future financing: founder and investor dilute proportionally unless either exercises agreed pro-rata rights.
- Employee option pool: if a 10% pool is created after closing and funded equally by both partners, the fully diluted cap table becomes Founder 45%, Investor 45%, Option Pool 10%.

Explain that an exact 50/50 company can create decision deadlock. Present a professional governance structure:

- five-person board: two founder nominees, two investor nominees, and one mutually selected independent director;
- founder/CEO controls ordinary operations within the approved annual budget;
- reserved matters require defined supermajority or mutual consent;
- independent escalation and mediation process for deadlocks;
- buy-sell, right-of-first-refusal, tag-along, drag-along, and good-leaver/bad-leaver provisions drafted by counsel;
- founder IP assignment, confidentiality, and vesting treatment confirmed during diligence;
- investor information rights, quarterly reporting, and annual budget approval;
- no investor guarantee of company or trading performance.

Do not present the 50/50 terms as legally final. Add a visible statement that valuation, tax, governance, securities, and shareholder terms require Romanian/EU counsel and tax advice.

USE OF FUNDS

Use this allocation for the EUR 1.5 million round:

- 40% / EUR 600,000: engineering, product, connectors, backtesting, and LEAN integration.
- 20% / EUR 300,000: data, ML, SocialPulse, AdvisorRank, and signal validation.
- 15% / EUR 225,000: go-to-market, community pilots, content, and enterprise pilots.
- 10% / EUR 150,000: legal, compliance, privacy, and commercial contracts.
- 10% / EUR 150,000: infrastructure, security, observability, and business continuity.
- 5% / EUR 75,000: operating contingency.

State that this is designed for approximately 15-18 months of runway, depending on hiring timing, data contracts, revenue, and regulatory scope. Do not claim that this round necessarily funds the company to profitability.

FIVE-YEAR BASE MODEL

Use the following illustrative base case. Round display values sensibly, but preserve the underlying calculations. Label all values as management projections, unaudited, and subject to revision.

Operating drivers:

| Metric | Year 1 | Year 2 | Year 3 | Year 4 | Year 5 |
| Average paying retail users | 200 | 950 | 3,250 | 8,500 | 18,500 |
| Year-end paying retail users | 400 | 1,500 | 5,000 | 12,000 | 25,000 |
| Blended retail ARPU/month | EUR 59 | EUR 65 | EUR 72 | EUR 80 | EUR 88 |
| Average enterprise customers | 1 | 5 | 14 | 30 | 55 |
| Year-end enterprise customers | 2 | 8 | 20 | 40 | 70 |
| Average enterprise ACV | EUR 30k | EUR 40k | EUR 55k | EUR 70k | EUR 90k |

Revenue and profitability:

| EUR millions | Year 1 | Year 2 | Year 3 | Year 4 | Year 5 |
| Retail subscription revenue | 0.142 | 0.741 | 2.808 | 8.160 | 19.536 |
| Enterprise revenue | 0.030 | 0.200 | 0.770 | 2.100 | 4.950 |
| Usage, data, API, and white-label | 0.010 | 0.060 | 0.250 | 0.750 | 2.000 |
| Total revenue | 0.182 | 1.001 | 3.828 | 11.010 | 26.486 |
| Cost of revenue | 0.091 | 0.400 | 1.225 | 2.863 | 5.827 |
| Gross profit | 0.091 | 0.601 | 2.603 | 8.147 | 20.659 |
| Gross margin | 50% | 60% | 68% | 74% | 78% |
| Operating expenses | 1.100 | 1.800 | 3.200 | 5.800 | 9.500 |
| EBITDA | -1.009 | -1.199 | -0.597 | 2.347 | 11.159 |

Illustrative year-end ARR:

| EUR millions | Year 1 | Year 2 | Year 3 | Year 4 | Year 5 |
| Year-end ARR | 0.36 | 1.59 | 5.82 | 15.52 | 35.90 |

Explain that the model reaches illustrative annual EBITDA profitability in Year 4, not necessarily cash-flow break-even at the same moment. Working capital, capitalized development, taxes, financing, and exceptional legal/data expenses are not modeled in detail.

UNIT ECONOMICS TARGETS

These are target economics, not observed metrics:

Retail at Year 3 maturity:

- blended ARPU: EUR 72/month;
- gross margin: 68%;
- gross profit per paid user: approximately EUR 49/month;
- target blended CAC: EUR 350;
- target CAC payback: approximately 7 months;
- target monthly paid-user churn: 3.0%;
- illustrative gross-profit LTV: approximately EUR 1,630;
- illustrative LTV/CAC: approximately 4.7x.

Enterprise at Year 3 maturity:

- average ACV: EUR 55,000;
- target gross margin: approximately 80%;
- target sales and onboarding CAC: EUR 20,000;
- target CAC payback: approximately 5-6 months;
- target gross revenue retention: at least 85%;
- target net revenue retention after expansion: above 100%.

Show formulas in the financial appendix. Clearly state that early cohorts will likely perform worse than mature targets.

SCENARIO ANALYSIS

Create a conservative, base, and upside case. Use these Year 5 revenue ranges:

- Conservative: EUR 9-12 million.
- Base: approximately EUR 26.5 million.
- Upside: EUR 45-60 million.

The scenario drivers must include:

- paid-user conversion;
- churn and retention;
- retail ARPU mix;
- enterprise sales cycle and ACV;
- data-license cost;
- model and compute cost;
- customer-support intensity;
- legal timing for paper and live features;
- creator/social acquisition efficiency.

Show a sensitivity table for Year 5 revenue and EBITDA under at least:

- retail users 30% below and 30% above base;
- ARPU 15% below and 15% above base;
- gross margin five points below and five points above base;
- enterprise customer count 30% below and 30% above base.

MARKET-SIZING RULES

Do not use a single inflated third-party TAM number. Build a bottom-up market model and label every assumption.

Create three layers:

1. Initial serviceable market: active crypto, prediction-market, and self-directed users who pay for data, automation, or research software.
2. Expansion market: financial creators, small trading teams, advisors, funds, brokers, venues, and data providers.
3. Long-term platform market: multi-asset research, backtesting, data access, APIs, and private deployment.

Use an illustrative bottom-up serviceable revenue calculation:

- 100,000 potential paying personal users x EUR 80 monthly blended ARPU = EUR 96 million ARR.
- 500 potential enterprise customers x EUR 75,000 ACV = EUR 37.5 million ARR.
- API, data, and white-label revenue equal to approximately 15% of subscription and enterprise revenue = approximately EUR 20 million ARR.
- Illustrative serviceable revenue opportunity: more than EUR 150 million ARR.

This is a planning calculation, not a claim of current demand or market share.

Use current public demand indicators only when cited directly. Suitable examples include:

- QuantConnect reports a community above 500,000 and hundreds of thousands of monthly backtests.
- Robinhood reported 27.0 million funded customers and 4.2 million Gold subscribers for Q4 2025; use the latest available official filing when generating the deck.
- Robinhood reported substantial prediction-market contract activity in 2025; use exact wording and dates from the official investor release.

Do not imply these users are BITprivat customers or directly addressable without further evidence.

REQUIRED SLIDE STRUCTURE

Create a 22-slide main presentation plus a financial and diligence appendix.

Slide 1 - Cover
- BITprivat
- "Market intelligence and strategy automation made understandable"
- Equal strategic partnership proposal
- Confidential and date stamp

Slide 2 - Investment thesis
- One sentence describing the opportunity.
- Three reasons this company can become valuable.
- One explicit statement that this is software infrastructure, not a guaranteed-return product.

Slide 3 - The problem
- Financial data, social opinions, research, backtesting, and execution are fragmented.
- Existing professional tools are difficult for normal users.
- Social trading lacks consistent evidence, provenance, and outcome validation.

Slide 4 - The solution
- Show the seven-step product journey.
- Emphasize plain language above professional infrastructure.

Slide 5 - Product experience
- Visualize Home, Explore Data, Strategy Builder, Test Results, Expert Bots, and Practice.
- Show Simple mode and optional Pro mode.

Slide 6 - Why now
- AI capability.
- Retail demand for premium financial tools.
- Growth of prediction-market and crypto participation.
- Open-source LEAN maturity.
- Include dated primary-source evidence.

Slide 7 - Data Library
- Explain source, coverage, freshness, cost, quality, and license transparency.
- Explain why data provenance creates trust.

Slide 8 - Social Trader intelligence
- Public evidence -> structured claim -> price-resolved outcome -> transparent bot profile.
- Clearly label research bots and paper allocation.

Slide 9 - Strategy engine
- Idea -> blueprint -> backtest -> validation -> paper -> gated live.
- Explain the hybrid BITprivat and LEAN runtime.

Slide 10 - Differentiation
- Compare BITprivat with QuantConnect, TradingView, generic copy-trading tools, social dashboards, and institutional terminals.
- Use dimensions such as beginner usability, data provenance, creator evidence, no-code testing, paper-first controls, Pro depth, and enterprise governance.
- Be factual and respectful; do not claim competitors lack features without evidence.

Slide 11 - Business model
- Personal plans, Enterprise OS, API/data, and white-label.
- Show recurring revenue and expansion logic.

Slide 12 - Go-to-market
- Creator and community wedge.
- Public evidence reports and strategy scorecards.
- Retail conversion.
- Enterprise pilots beginning with research and alerts, not live execution.

Slide 13 - Current progress
- Use a Shipped / Partial / Planned / Gated table.
- Include public deployment and implemented modules.
- State explicitly that commercial traction remains to be validated.

Slide 14 - Technology and moat
- Source graph.
- Outcome archive.
- Strategy version history.
- User preference and paper-execution feedback.
- Explain the compounding data and trust loop.

Slide 15 - Regulatory and safety posture
- Research and paper-first default.
- Data licensing.
- No custody target.
- Audit trail.
- Risk limits and kill switch before live.
- Cite current ESMA copy/auto-trading guidance and MiCA qualification concerns.

Slide 16 - Market opportunity
- Bottom-up TAM/SAM/SOM.
- Dated demand indicators.
- Avoid unsupported market-research graphics.

Slide 17 - Unit economics
- Retail and enterprise targets.
- CAC payback, gross margin, LTV/CAC, retention.
- Clearly mark as targets.

Slide 18 - Five-year financial model
- Revenue composition chart.
- Gross margin line.
- EBITDA bars.
- Break-even timing.

Slide 19 - Scenarios and capital needs
- Conservative, base, and upside.
- Explain that a follow-on round may be needed before profitability.
- Identify the milestones needed for that financing.

Slide 20 - Investment ask and use of funds
- EUR 1.5 million.
- Use-of-funds chart.
- 15-18 month runway.
- 12-18 month milestones.

Slide 21 - Equal partnership and governance
- EUR 1.5 million pre-money / EUR 3.0 million post-money.
- 50% founder / 50% investor before option pool.
- Optional 45% / 45% / 10% fully diluted structure.
- Board, reserved matters, reporting, and deadlock mechanism.

Slide 22 - Closing
- What the investor enables.
- What must be proven in the next 18 months.
- Clear diligence and next-step request.

REQUIRED APPENDIX

Include:

A. Detailed five-year operating assumptions.
B. Full five-year P&L table.
C. Year 1 quarterly cash and hiring plan.
D. Revenue formulas and unit-economics formulas.
E. Scenario and sensitivity tables.
F. Cap table before investment, at closing, after a 10% option pool, and after an illustrative future round.
G. Governance and reserved-matters outline.
H. Product readiness matrix.
I. Technical architecture and infrastructure plan.
J. Data-provider and licensing register.
K. Legal and regulatory risk register.
L. Key-person, cybersecurity, model, market, data, and execution risks.
M. Due-diligence request list.
N. Source list with publication dates and URLs.

YEAR 1 QUARTERLY CASH PLAN

Build a quarterly budget totaling approximately EUR 1.5 million over 15-18 months. Use this starting allocation, then reconcile it with the use-of-funds slide:

- Core payroll and contractors: EUR 700,000.
- Data and model services: EUR 220,000.
- Infrastructure and security: EUR 130,000.
- Legal, compliance, accounting, and insurance: EUR 150,000.
- Product design, research, and user testing: EUR 80,000.
- Growth and enterprise pilots: EUR 145,000.
- Contingency: EUR 75,000.

Show headcount sequencing rather than assuming the full team starts on day one:

- Founder/CEO and current technical leadership.
- Backend/data engineer.
- Frontend/product engineer.
- Quant/research engineer.
- ML/social-intelligence engineer.
- Infrastructure/security support.
- Product/growth operator.
- Fractional legal/compliance and finance support.

MILESTONES FUNDED BY THE ROUND

Months 0-3:
- Shared Postgres, queue, object storage, and async backtests.
- New separate-route application shell.
- Data Library MVP.

Months 4-6:
- Guided Strategy Builder.
- Reproducible reports.
- Validated social-trader outcomes.
- Initial closed user cohort.

Months 7-12:
- LEAN worker integration.
- Optimization and out-of-sample validation.
- Continuous paper deployments.
- First paid personal users and enterprise research pilots.

Months 13-18:
- Retention and unit-economics proof.
- Security and compliance hardening.
- One approved testnet or sandbox venue.
- Decision package for a gated live beta or continued research-only commercialization.

FINANCIAL PRESENTATION RULES

- Use EUR consistently.
- Show formulas and assumptions in the appendix.
- Never mix ARR, recognized annual revenue, MRR, GMV, trading volume, or assets under management.
- Do not describe backtest returns as company revenue.
- Do not include customer trading gains in BITprivat financial projections.
- Do not imply data or compute gross margin without including vendor costs.
- State whether numbers are actual, target, estimate, or projection.
- Include dates on all market statistics.
- Include a downside case and expected future financing need.
- Use at most one decimal place for EUR millions and whole percentages on main slides.
- Keep detailed values in appendix tables.

SOURCE AND FACT-CHECKING RULES

- Prefer official company filings, regulator publications, official API documentation, and audited reports.
- Every external statistic needs a source and publication date in the slide footer.
- Never cite a search result page.
- If a number cannot be verified, omit it or display it as an explicit management assumption.
- Verify all additions, percentages, CAGR values, ARR values, and cap-table totals.
- Keep direct quotations short and within copyright limits.

Recommended official starting sources:

- QuantConnect platform: https://www.quantconnect.com/
- QuantConnect Dataset Market: https://www.quantconnect.com/datasets/
- QuantConnect dataset licensing: https://www.quantconnect.com/docs/v2/cloud-platform/datasets/licensing
- QuantConnect Research Pipeline: https://www.quantconnect.com/docs/v2/cloud-platform/research-pipeline
- LEAN repository: https://github.com/QuantConnect/Lean
- Robinhood investor relations: https://investors.robinhood.com/
- ESMA copy-trading guidance: https://www.esma.europa.eu/press-news/esma-news/esma-provides-guidance-supervision-copy-trading-services
- ESMA MiCA copy/auto-trading Q&A: https://www.esma.europa.eu/publications-data/questions-answers/2463
- ESMA algorithmic-trading supervisory material: https://www.esma.europa.eu/
- YouTube Data API: https://developers.google.com/youtube/v3/docs
- Interactive Brokers API: https://www.interactivebrokers.com/campus/ibkr-api-page/twsapi-doc/

VISUAL DIRECTION

Use a premium European fintech editorial style, not a neon crypto template.

- 16:9 widescreen.
- Warm off-white or very light stone background for most slides.
- Deep navy text and one controlled teal accent.
- Dark slides only for section breaks or the closing slide.
- Clean grotesk typography with tabular numerals for financial tables.
- Strong whitespace and a consistent grid.
- Simple diagrams, not screenshots filled with tiny dashboard widgets.
- No purple gradients, glowing coins, robots, circuit-board heads, or stock-photo traders.
- Use green and red only for positive and negative financial values.
- Use real product screenshots only when they are current and legible.
- Use a maximum of one primary message, one chart, and three supporting points per main slide.
- Put detailed content in the appendix rather than shrinking text.

For each slide, provide:

1. Slide number and title.
2. One-sentence purpose.
3. Exact on-slide copy.
4. Recommended visual or chart.
5. Data and calculation notes.
6. Source footnotes.
7. Speaker notes of 60-120 words.

FINAL QUALITY CHECK

Before delivering the deck, verify:

- The company name is BITprivat everywhere.
- The investment ask is EUR 1.5 million.
- The pre-money is EUR 1.5 million and post-money is EUR 3.0 million.
- Founder and investor ownership are equal before shared option-pool dilution.
- All cap tables total 100%.
- Use of funds totals EUR 1.5 million and 100%.
- Five-year revenue totals match operating assumptions.
- Gross profit equals revenue less cost of revenue.
- EBITDA equals gross profit less operating expenses.
- Current product facts are separated from projections.
- No unverified traction appears.
- No investment-performance guarantee appears.
- Live trading is shown as gated, not currently available.
- Legal and data-license risks are visible.
- Every external number has a dated primary source.
- The investor can understand the product without knowing trading terminology.

End with this disclaimer in small but readable text:

"Confidential discussion material. Financial projections and transaction terms are illustrative, unaudited, and subject to due diligence, definitive documentation, legal and tax advice, and change. Nothing in this presentation is investment advice or a guarantee of product, company, or trading performance."
```

## Internal Review Checklist

Before using the prompt with a slide-generation tool:

- Confirm whether the investment currency should remain EUR.
- Confirm that EUR 1.5 million for equal ownership is the intended opening proposal.
- Confirm which entity owns the code, domain, brand, and other intellectual property.
- Replace founder and team placeholders with verified biographies.
- Insert only current product screenshots.
- Confirm whether an employee option pool should exist at closing.
- Have counsel review the equal-control and deadlock structure.
- Reconcile the forecast with a separate spreadsheet before presenting it externally.
- Mark any achieved traction with dated supporting evidence.
- Remove any roadmap item the company no longer intends to build.

## Financial Model Notes

The five-year model is deliberately more conservative than the earlier directional Year 2 base case in `docs/04-financial-model.md`. It assumes a slower commercial ramp, substantial cost of data and compute, and a likely follow-on financing requirement before profitability.

The model is not an accounting forecast. A complete investor data room should eventually include:

- a monthly 36-month integrated P&L, cash-flow, and balance-sheet model;
- hiring dates and fully loaded employment costs by jurisdiction;
- VAT and corporate-tax treatment;
- capitalization and amortization policy for development costs;
- deferred-revenue schedule for annual subscriptions;
- payment-processing, chargeback, and bad-debt assumptions;
- provider-by-provider data and compute costs;
- legal, licensing, insurance, and audit estimates;
- financing dilution and option-pool scenarios;
- founder IP contribution and related-party disclosures.

## Change Log

| Date | Change |
| --- | --- |
| 2026-07-01 | Initial all-inclusive investor pitch prompt, five-year model, and equal-partnership proposal created. |
