"use strict";

const ROUTES = {
  "/dashboard": "home",
  "/home": "home",
  "/markets": "data",
  "/data": "data",
  "/ideas": "ideas",
  "/strategies": "strategies",
  "/results": "results",
  "/signals": "social",
  "/social-traders": "social",
  "/trade": "paper",
  "/paper": "paper",
  "/portfolio": "portfolio",
  "/connections": "connections",
  "/learn": "learn",
  "/settings": "settings",
};

const NAV_ROUTE_FOR_PAGE = {
  home: "/dashboard",
  data: "/data",
  ideas: "/ideas",
  strategies: "/strategies",
  results: "/results",
  social: "/social-traders",
  paper: "/paper",
  portfolio: "/portfolio",
  connections: "/connections",
  learn: "/learn",
  settings: "/settings",
};

const COPY = {
  en: {
    nav_start: "Start",
    nav_home: "Home",
    nav_data: "Explore data",
    nav_ideas: "My ideas",
    nav_strategies: "Strategies",
    nav_results: "Test results",
    nav_follow: "Follow and practice",
    nav_experts: "Expert bots",
    nav_practice: "Practice",
    nav_portfolio: "Portfolio",
    nav_manage: "Manage",
    nav_connections: "Connections",
    nav_learn: "Learn",
    nav_settings: "Settings",
    search_placeholder: "Search data, strategies, or expert bots",
  },
  ro: {
    nav_start: "Incepe",
    nav_home: "Acasa",
    nav_data: "Exploreaza date",
    nav_ideas: "Ideile mele",
    nav_strategies: "Strategii",
    nav_results: "Rezultate teste",
    nav_follow: "Urmarire si practica",
    nav_experts: "Boti experti",
    nav_practice: "Practica",
    nav_portfolio: "Portofoliu",
    nav_manage: "Administrare",
    nav_connections: "Conexiuni",
    nav_learn: "Invata",
    nav_settings: "Setari",
    search_placeholder: "Cauta date, strategii sau boti experti",
  },
};

const DATASETS = [
  {
    id: "live-markets",
    name: "Live market prices",
    question: "What is the market doing now?",
    description: "Prices, daily movement, volume, volatility, and trend context for supported crypto assets.",
    category: "market",
    icon: "PX",
    assets: "BTC, ETH, SOL",
    coverage: "Live snapshot + historical route",
    license: "Public provider terms",
    uses: ["Charts", "Strategies", "Paper"],
  },
  {
    id: "prediction-markets",
    name: "Prediction-market intelligence",
    question: "What probabilities are markets assigning?",
    description: "Public Polymarket and Kalshi market context normalized into evidence for research bots.",
    category: "alternative",
    icon: "PM",
    assets: "Events and crypto-linked markets",
    coverage: "Current public markets",
    license: "Provider-specific public access",
    uses: ["Research", "Signals", "Backtests"],
  },
  {
    id: "macro",
    name: "Macro conditions",
    question: "What is changing in the economy?",
    description: "Rates, inflation, liquidity, and economic regime context with source-aware provider states.",
    category: "macro",
    icon: "MA",
    assets: "Global and US macro series",
    coverage: "Daily to monthly",
    license: "Public or user-configured",
    uses: ["Research", "Regime filters"],
  },
  {
    id: "creator-evidence",
    name: "Creator evidence",
    question: "What are tracked market creators saying?",
    description: "YouTube evidence converted into structured claims, confidence, risk notes, and research-bot profiles.",
    category: "social",
    icon: "YT",
    assets: "Crypto and prediction markets",
    coverage: "Configured channels and discovery queries",
    license: "Metadata and permitted public evidence",
    uses: ["Signals", "Expert bots", "Paper"],
  },
  {
    id: "wallet-intelligence",
    name: "Wallet intelligence",
    question: "What are selected public wallets doing?",
    description: "Tracked public activity and directional context without custody of user private keys.",
    category: "onchain",
    icon: "0X",
    assets: "Configured public addresses",
    coverage: "Provider-dependent",
    license: "Public chain data",
    uses: ["Research", "Signals"],
  },
  {
    id: "user-upload",
    name: "Your own dataset",
    question: "Can I test private or proprietary information?",
    description: "A planned upload path for licensed CSV and Parquet data with schema and rights validation.",
    category: "private",
    icon: "+",
    assets: "User defined",
    coverage: "Not available yet",
    license: "User-declared rights required",
    uses: ["Planned"],
  },
];

const STRATEGY_TEMPLATES = [
  {
    id: "trend-guard",
    name: "Trend with a safety exit",
    level: "Beginner",
    description: "Follow sustained price direction, then exit when loss or trend limits are reached.",
    inputs: "Price trend + volatility",
    risk: "Medium",
    assets: "BTC, ETH",
  },
  {
    id: "creator-confirmation",
    name: "Creator view with market confirmation",
    level: "Guided",
    description: "Act only when a creator thesis and current market direction agree.",
    inputs: "Creator evidence + price",
    risk: "Medium-high",
    assets: "BTC, ETH, SOL",
  },
  {
    id: "event-dislocation",
    name: "Prediction-market gap",
    level: "Advanced",
    description: "Compare event probabilities with external evidence and test where they diverge.",
    inputs: "Polymarket + Kalshi + news",
    risk: "High",
    assets: "Event markets",
  },
];

const LESSONS = [
  { id: "data-mode", duration: "3 min", title: "Live, delayed, setup, or unavailable?", description: "Learn how BITprivat labels the truth behind every number." },
  { id: "backtest", duration: "6 min", title: "What a backtest can and cannot prove", description: "Understand historical tests without confusing them for future performance." },
  { id: "drawdown", duration: "4 min", title: "The simplest way to understand drawdown", description: "See the worst fall from a previous portfolio high in normal language." },
  { id: "paper", duration: "5 min", title: "Why practice comes before live money", description: "Use simulated capital to expose execution and strategy mistakes safely." },
  { id: "creator", duration: "7 min", title: "How creator bots are evaluated", description: "Separate public commentary, actionable calls, proxy returns, and validated outcomes." },
  { id: "risk", duration: "5 min", title: "Set a loss limit before an entry", description: "Build risk rules while decisions are calm, not after a market move." },
];

const state = {
  page: ROUTES[window.location.pathname] || "home",
  dashboard: null,
  dashboardPromise: null,
  dataFilter: "all",
  language: localStorage.getItem("bp-language") || "en",
  theme: localStorage.getItem("bp-theme") || "light",
  experience: localStorage.getItem("bp-experience") || "simple",
  ideas: readStoredList("bp-ideas"),
  strategyDraft: readStoredObject("bp-strategy-draft"),
};

const root = document.getElementById("page-root");
const drawer = document.getElementById("app-drawer");
const drawerBackdrop = document.getElementById("drawer-backdrop");
const commandPalette = document.getElementById("command-palette");
const commandBackdrop = document.getElementById("command-backdrop");
const commandInput = document.getElementById("command-input");
const commandResults = document.getElementById("command-results");

function readStoredList(key) {
  try {
    const value = JSON.parse(localStorage.getItem(key) || "[]");
    return Array.isArray(value) ? value : [];
  } catch (_error) {
    return [];
  }
}

function readStoredObject(key) {
  try {
    const value = JSON.parse(localStorage.getItem(key) || "null");
    return value && typeof value === "object" ? value : null;
  } catch (_error) {
    return null;
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, Number(value) || 0));
}

function locale() {
  return state.language === "ro" ? "ro-RO" : "en-US";
}

function money(value, currency = "USD", maximumFractionDigits = 0) {
  return new Intl.NumberFormat(locale(), {
    style: "currency",
    currency,
    maximumFractionDigits,
  }).format(Number(value) || 0);
}

function number(value, digits = 0) {
  return new Intl.NumberFormat(locale(), { maximumFractionDigits: digits }).format(Number(value) || 0);
}

function percent(value, digits = 1) {
  return `${new Intl.NumberFormat(locale(), { minimumFractionDigits: digits, maximumFractionDigits: digits }).format((Number(value) || 0) * 100)}%`;
}

function dateLabel(value) {
  if (!value) return "Not available";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return new Intl.DateTimeFormat(locale(), { dateStyle: "medium", timeStyle: "short" }).format(parsed);
}

function relativeDate(value) {
  if (!value) return "No recent update";
  const then = new Date(value).getTime();
  const delta = Date.now() - then;
  if (!Number.isFinite(delta)) return dateLabel(value);
  const minutes = Math.round(delta / 60000);
  if (Math.abs(minutes) < 60) return `${Math.max(1, Math.abs(minutes))}m ago`;
  const hours = Math.round(minutes / 60);
  if (Math.abs(hours) < 48) return `${Math.abs(hours)}h ago`;
  const days = Math.round(hours / 24);
  return `${Math.abs(days)}d ago`;
}

function statusChip(label, stateName = "partial") {
  return `<span class="status-chip ${escapeHtml(stateName)}">${escapeHtml(label)}</span>`;
}

function showToast(message) {
  const region = document.getElementById("toast-region");
  if (!region) return;
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.textContent = message;
  region.appendChild(toast);
  window.setTimeout(() => toast.remove(), 4200);
}

async function fetchJson(path, options = {}) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 14000);
  try {
    const response = await fetch(path, {
      credentials: "same-origin",
      headers: { "Accept": "application/json", "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
      signal: controller.signal,
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = payload.detail || payload.message || `Request failed (${response.status})`;
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    return payload;
  } finally {
    window.clearTimeout(timeout);
  }
}

async function refreshDashboardAfterMutation(message) {
  await loadDashboard(true);
  renderCurrentPage();
  if (document.body.classList.contains("drawer-open")) openAccount();
  showToast(message);
}

async function registerPlatformUser(form) {
  const data = new FormData(form);
  await fetchJson("/api/auth/register", {
    method: "POST",
    body: JSON.stringify({
      display_name: data.get("display_name"),
      email: data.get("email"),
      password: data.get("password"),
    }),
  });
  await refreshDashboardAfterMutation("Account created. Your personal workspace is active.");
}

async function loginPlatformUser(form) {
  const data = new FormData(form);
  await fetchJson("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({
      email: data.get("email"),
      password: data.get("password"),
    }),
  });
  await refreshDashboardAfterMutation("Signed in.");
}

function isEvmChain(chain) {
  return new Set(["ethereum", "arbitrum", "base", "polygon", "optimism", "bsc", "avalanche"]).has(String(chain || "").toLowerCase());
}

async function connectPlatformWallet(form) {
  const data = new FormData(form);
  const chain = String(data.get("chain") || "base").toLowerCase();
  const provider = String(data.get("provider") || "walletconnect").toLowerCase();
  let address = String(data.get("address") || "").trim();
  const label = String(data.get("label") || "").trim() || null;
  if (isEvmChain(chain)) {
    if (!window.ethereum?.request) throw new Error("Install or unlock MetaMask, Rabby, or Coinbase Wallet to verify an EVM wallet.");
    const accounts = await window.ethereum.request({ method: "eth_requestAccounts" });
    address = String(address || accounts?.[0] || "").toLowerCase();
    if (!address) throw new Error("No wallet address was returned by the browser wallet.");
    const challenge = await fetchJson("/api/me/wallets/challenge", {
      method: "POST",
      body: JSON.stringify({ chain, provider, address, label }),
    });
    const signature = await window.ethereum.request({
      method: "personal_sign",
      params: [challenge.message, address],
    });
    await fetchJson("/api/me/wallets/verify", {
      method: "POST",
      body: JSON.stringify({ challenge_id: challenge.challenge_id, signature }),
    });
  } else {
    if (!address) throw new Error("Paste the public wallet address for this non-EVM chain.");
    await fetchJson("/api/me/wallets", {
      method: "POST",
      body: JSON.stringify({ chain, provider, address, label }),
    });
  }
  await refreshDashboardAfterMutation("Wallet connected in read-only mode.");
}

function loadDashboard(force = false) {
  if (state.dashboard && !force) return Promise.resolve(state.dashboard);
  if (state.dashboardPromise && !force) return state.dashboardPromise;
  state.dashboardPromise = fetchJson(`/api/dashboard${force ? `?v=${Date.now()}` : ""}`)
    .then((payload) => {
      state.dashboard = payload;
      updateChrome(payload);
      return payload;
    })
    .finally(() => {
      state.dashboardPromise = null;
    });
  return state.dashboardPromise;
}

function marketState(payload) {
  const provider = payload?.provider_status || {};
  const source = String(provider.market_provider_source || "").toLowerCase();
  const mode = String(provider.market_provider_mode || "").toLowerCase();
  if (!provider.market_provider_ready) return "blocked";
  if (mode === "demo" || source.includes("seed") || source.includes("demo")) return "setup";
  return "live";
}

function socialState(payload) {
  const provider = payload?.provider_status || {};
  const mode = String(provider.social_discovery_provider_mode || provider.social_discovery_provider || "setup").toLowerCase();
  return mode === "youtube" && provider.social_discovery_configured ? "live" : "setup";
}

function updateChrome(payload) {
  const provider = payload.provider_status || {};
  const mode = marketState(payload);
  const stateDot = document.getElementById("rail-state-dot");
  stateDot.className = `state-dot ${mode === "live" ? "live" : mode === "blocked" ? "blocked" : "warning"}`;
  document.getElementById("rail-state-label").textContent = mode === "live" ? "Market data connected" : mode === "setup" ? "Real provider setup needed" : "Provider needs attention";
  document.getElementById("rail-state-detail").textContent = provider.market_provider_source || provider.market_provider_mode || "Provider status";

  const banner = document.getElementById("mode-banner");
  banner.dataset.state = mode;
  const titles = {
    live: "Live provider data",
    setup: "Real provider setup",
    blocked: "Market provider unavailable",
  };
  document.getElementById("mode-banner-title").textContent = titles[mode];
  document.getElementById("mode-banner-detail").textContent = mode === "live"
    ? `${provider.market_provider_source || "Provider"} is supplying the current market snapshot.`
    : mode === "setup"
      ? "Connect real providers before using this data for decisions. Every action remains paper-first."
      : provider.market_provider_warning || "Open Connections to review the missing dependency.";

  const session = payload.auth_session || {};
  const profile = payload.user_profile || {};
  const name = session.user?.display_name || profile.display_name || "Guest workspace";
  document.getElementById("account-name").textContent = name;
  document.getElementById("account-tier").textContent = session.authenticated ? `${profile.tier || "Personal"} account` : "Research mode";
  document.getElementById("account-initials").textContent = name.split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase() || "IP";

  const alerts = Array.isArray(profile.recent_alerts) ? profile.recent_alerts.filter((item) => !item.read_at).length : 0;
  const alertBadge = document.getElementById("notification-count");
  alertBadge.textContent = String(alerts);
  alertBadge.classList.toggle("visible", alerts > 0);
}

function applyPreferences() {
  document.body.dataset.theme = state.theme;
  document.body.dataset.experience = state.experience;
  document.documentElement.lang = state.language;
  document.getElementById("language-toggle").textContent = state.language.toUpperCase();
  document.querySelectorAll("[data-copy]").forEach((element) => {
    const key = element.dataset.copy;
    if (COPY[state.language]?.[key]) element.textContent = COPY[state.language][key];
  });
}

function syncActiveNav() {
  const activeRoute = NAV_ROUTE_FOR_PAGE[state.page];
  document.querySelectorAll(".primary-nav a[data-route]").forEach((link) => {
    link.classList.toggle("active", link.dataset.route === activeRoute);
    if (link.dataset.route === activeRoute) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
}

function pageHeader(kicker, title, description, actions = "") {
  return `
    <header class="page-header">
      <div class="page-heading">
        <p class="eyebrow">${escapeHtml(kicker)}</p>
        <h1>${escapeHtml(title)}</h1>
        <p>${escapeHtml(description)}</p>
      </div>
      ${actions ? `<div class="page-actions">${actions}</div>` : ""}
    </header>`;
}

function renderError(error) {
  root.innerHTML = `
    ${pageHeader("Connection", "This page could not load", "Your data remains unchanged. Retry the request or check the provider status.")}
    <section class="error-state">
      <h2>We could not reach the BITprivat API</h2>
      <p>${escapeHtml(error?.message || "Unknown request error")}</p>
      <button class="button" type="button" data-retry-page>Retry</button>
    </section>`;
}

function renderHome(payload) {
  const summary = payload.summary || {};
  const paper = payload.paper_trading?.summary || {};
  const assets = payload.assets || [];
  const signals = payload.recent_signals || [];
  const mState = marketState(payload);
  const modeText = mState === "live" ? "Live market context" : "Research workspace";
  return `
    ${pageHeader("Your workspace", "Make one informed decision at a time", "Explore evidence, test an idea, and practice before risking real money.", `
      <a class="button secondary" href="/data">Explore data</a>
      <a class="button" href="/ideas">Start an idea</a>`)}

    <section class="hero-panel">
      <div class="hero-copy">
        <p class="eyebrow">${escapeHtml(modeText)}</p>
        <h2>From a market question to a test you can understand.</h2>
        <p>BITprivat combines market prices, public evidence, and clear risk rules. It shows what is known, what is simulated, and what still needs validation.</p>
        <div class="hero-actions">
          <a class="button" href="/ideas">Describe an idea</a>
          <a class="button secondary" href="/social-traders">Explore expert bots</a>
        </div>
      </div>
      <aside class="hero-aside">
        <span>Your strategy journey</span>
        <strong>Start with evidence</strong>
        <p>Each step unlocks only after the previous one produces enough evidence.</p>
        <div class="journey-steps">
          <div class="journey-step active"><i>1</i>Explore information</div>
          <div class="journey-step"><i>2</i>Write an idea</div>
          <div class="journey-step"><i>3</i>Test on history</div>
          <div class="journey-step"><i>4</i>Practice with paper money</div>
        </div>
      </aside>
    </section>

    <section class="metric-grid" aria-label="Workspace summary">
      <article class="metric-card"><span>Practice portfolio</span><strong>${money(paper.equity || paper.starting_balance)}</strong><small>${paper.open_positions || 0} open paper position(s)</small></article>
      <article class="metric-card"><span>Market sources</span><strong>${number(summary.tracked_assets || assets.length)}</strong><small>${mState === "live" ? "Provider-connected assets" : "Research snapshot assets"}</small></article>
      <article class="metric-card"><span>Fresh evidence</span><strong>${number(summary.signals_last_24h || 0)}</strong><small>Signals observed in the last 24 hours</small></article>
      <article class="metric-card"><span>Research bots</span><strong>${number(summary.active_bots || 0)}</strong><small>Transparent scored bot profiles</small></article>
    </section>

    <section class="content-grid asymmetric">
      <article class="panel">
        <div class="panel-head"><div class="panel-title"><h2>Market snapshot</h2><p>Direction, price, and data origin in one compact view.</p></div><a class="text-link" href="/data">View all data</a></div>
        <div class="asset-list">${assets.map(renderAssetRow).join("") || emptyCompact("No market assets are available.")}</div>
      </article>
      <article class="panel">
        <div class="panel-head"><div class="panel-title"><h2>Latest evidence</h2><p>Recent public information entering the research engine.</p></div><a class="text-link" href="/social-traders">Expert bots</a></div>
        <div class="activity-list">${signals.slice(0, 5).map(renderSignalItem).join("") || emptyCompact("No recent evidence is available.")}</div>
      </article>
    </section>

    <section class="panel" style="margin-top:14px">
      <div class="panel-head"><div class="panel-title"><h2>Choose your next step</h2><p>The platform stays simple until you ask for professional detail.</p></div></div>
      <div class="quick-paths">
        <a class="path-card" href="/data"><span class="card-icon">01</span><strong>Explore useful data</strong><p>Find information by the question it can answer.</p><small>Open Data Library</small></a>
        <a class="path-card" href="/strategies"><span class="card-icon">02</span><strong>Start from a template</strong><p>Use tested structure instead of a blank screen.</p><small>Browse strategies</small></a>
        <a class="path-card" href="/paper"><span class="card-icon">03</span><strong>Practice safely</strong><p>Preview costs and risk before a simulated order.</p><small>Open practice account</small></a>
      </div>
    </section>`;
}

function renderAssetRow(asset) {
  const change = Number(asset.change_24h) || 0;
  const direction = change > 0 ? "positive" : change < 0 ? "negative" : "";
  return `
    <div class="asset-row">
      <div class="asset-name"><span class="asset-symbol">${escapeHtml(asset.asset)}</span><span><strong>${escapeHtml(asset.asset)}</strong><small>${escapeHtml(asset.source || "Unknown source")}</small></span></div>
      <div class="asset-cell"><strong>${money(asset.price, "USD", asset.price < 10 ? 3 : 0)}</strong><small>Current price</small></div>
      <div class="asset-cell"><strong class="${direction}">${change > 0 ? "+" : ""}${percent(change)}</strong><small>24 hours</small></div>
      <div class="asset-cell asset-volume"><strong>${money(asset.volume_24h, "USD", 0)}</strong><small>Volume</small></div>
      <button class="row-action" type="button" data-open-asset="${escapeHtml(asset.asset)}" aria-label="Open ${escapeHtml(asset.asset)} details">&gt;</button>
    </div>`;
}

function renderSignalItem(signal) {
  const sentiment = Number(signal.sentiment) || 0;
  return `
    <div class="activity-item">
      <span class="activity-icon">${escapeHtml(signal.asset || "?")}</span>
      <span class="activity-copy"><strong>${escapeHtml(signal.title || signal.summary || "Market evidence")}</strong><span>${escapeHtml(signal.author_handle || signal.provider_name || signal.source || "Unknown provider")}</span><time>${relativeDate(signal.observed_at)} - quality ${percent(signal.source_quality_score || 0)}</time></span>
      ${statusChip(sentiment > 0.15 ? "Bullish" : sentiment < -0.15 ? "Bearish" : "Neutral", sentiment > 0.15 ? "live" : sentiment < -0.15 ? "blocked" : "partial")}
    </div>`;
}

function emptyCompact(message) {
  return `<div class="compact-item"><span class="compact-copy"><span>${escapeHtml(message)}</span></span></div>`;
}

function datasetRuntime(dataset, payload) {
  const provider = payload.provider_status || {};
  if (dataset.id === "live-markets") {
    const stateName = marketState(payload);
  return { state: stateName, label: stateName === "live" ? "Live" : stateName === "setup" ? "Setup needed" : "Blocked", source: provider.market_provider_source || "Market provider" };
  }
  if (dataset.id === "creator-evidence") {
    const stateName = socialState(payload);
  return { state: stateName, label: stateName === "live" ? "Configured" : "Setup needed", source: provider.social_discovery_provider_source || "Social discovery" };
  }
  if (dataset.id === "macro") {
    const live = provider.macro_provider_live_capable && provider.macro_provider_configured;
  return { state: live ? "live" : "setup", label: live ? "Configured" : "Setup needed", source: provider.macro_provider_source || "Macro provider" };
  }
  if (dataset.id === "wallet-intelligence") {
    const live = provider.wallet_provider_live_capable && provider.wallet_provider_configured;
  return { state: live ? "live" : "setup", label: live ? "Configured" : "Setup needed", source: provider.wallet_provider_source || "Wallet provider" };
  }
  if (dataset.id === "prediction-markets") {
    const venues = provider.venue_signal_providers || [];
    return { state: venues.length ? "live" : "partial", label: venues.length ? "Public API" : "Partial", source: venues.map((item) => item.mode || item.source).filter(Boolean).join(", ") || "Venue providers" };
  }
  return { state: "planned", label: "Planned", source: "Not connected" };
}

function renderData(payload) {
  const filters = [
    ["all", "All information"], ["market", "Market"], ["social", "People"], ["macro", "Economy"], ["alternative", "Events"], ["onchain", "On-chain"],
  ];
  const visible = state.dataFilter === "all" ? DATASETS : DATASETS.filter((item) => item.category === state.dataFilter);
  return `
    ${pageHeader("Data Library", "Find information by the question it answers", "Every dataset shows its source, freshness, limits, cost posture, and permitted use before you add it to a strategy.", `<button class="button secondary" type="button" data-open-license>How licensing works</button><a class="button" href="/ideas">Use data in an idea</a>`)}
    <div class="filter-bar" aria-label="Dataset filters">${filters.map(([id, label]) => `<button class="chip-button ${state.dataFilter === id ? "active" : ""}" type="button" data-data-filter="${id}">${label}</button>`).join("")}</div>
    <section class="card-grid">${visible.map((dataset) => renderDatasetCard(dataset, datasetRuntime(dataset, payload))).join("")}</section>
    <section class="inline-notice" style="margin-top:16px"><span class="state-dot warning"></span><p><strong>Licensing is part of the product.</strong> BITprivat will not mirror or resell restricted third-party datasets. Paid and user-owned sources remain locked to their permitted research, charting, backtest, or live uses.</p></section>`;
}

function renderDatasetCard(dataset, runtime) {
  return `
    <article class="data-card">
      <div class="card-topline"><span class="card-icon">${escapeHtml(dataset.icon)}</span>${statusChip(runtime.label, runtime.state)}</div>
      <div><p class="eyebrow">${escapeHtml(dataset.question)}</p><h3>${escapeHtml(dataset.name)}</h3></div>
      <p>${escapeHtml(dataset.description)}</p>
      <div class="card-meta">${dataset.uses.map((use) => `<span>${escapeHtml(use)}</span>`).join("")}</div>
      <div class="card-footer"><small>${escapeHtml(runtime.source)}</small><button class="text-link" type="button" data-open-dataset="${escapeHtml(dataset.id)}">Preview</button></div>
    </article>`;
}

function renderIdeas() {
  const cards = state.ideas.length
    ? state.ideas.map((idea) => `
        <article class="idea-card">
          <div class="card-topline">${statusChip(idea.stage || "Idea", "planned")}<small class="number">${escapeHtml(relativeDate(idea.createdAt))}</small></div>
          <h3>${escapeHtml(idea.title)}</h3>
          <p>${escapeHtml(idea.hypothesis)}</p>
          <div class="card-meta"><span>${escapeHtml(idea.market || "Crypto")}</span><span>${escapeHtml(idea.evidence || "Price")}</span></div>
          <div class="card-footer"><small>Saved on this device</small><button class="text-link" type="button" data-promote-idea="${escapeHtml(idea.id)}">Build strategy</button></div>
        </article>`).join("")
    : "";
  return `
    ${pageHeader("Research notebook", "Capture the idea before choosing the tools", "A useful strategy starts with a testable belief, not a collection of indicators.", `<button class="button" type="button" data-add-idea>+ New idea</button>`)}
    ${cards ? `<section class="card-grid">${cards}</section>` : `
      <section class="empty-state"><div><span class="card-icon">?</span><h2>No ideas yet</h2><p>Write one sentence about what you believe may happen and why. BITprivat will help turn it into rules later.</p><button class="button" type="button" data-add-idea>Write your first idea</button></div></section>`}
    <section class="panel" style="margin-top:14px"><div class="panel-head"><div class="panel-title"><h2>A strong idea has three parts</h2><p>Keep it understandable enough to explain without a chart.</p></div></div><div class="quick-paths"><article class="path-card"><span class="card-icon">1</span><strong>Observation</strong><p>What pattern or behavior did you notice?</p></article><article class="path-card"><span class="card-icon">2</span><strong>Reason</strong><p>Why might this pattern continue or repeat?</p></article><article class="path-card"><span class="card-icon">3</span><strong>Failure condition</strong><p>What evidence would prove the idea wrong?</p></article></div></section>`;
}

function renderStrategies(payload) {
  const authenticated = Boolean(payload.auth_session?.authenticated);
  const draft = state.strategyDraft;
  return `
    ${pageHeader("Strategy Builder", "Turn an idea into clear, testable rules", "Start from a guided template. Professional parameters remain available in Pro mode.", `<a class="button secondary" href="/ideas">Review ideas</a><a class="button" href="/simulation">Open Strategy Lab</a>`)}
    ${draft ? `<section class="inline-notice" style="margin-bottom:14px"><span class="state-dot live"></span><p><strong>Draft ready:</strong> ${escapeHtml(draft.title)}. Continue with a template, then open Strategy Lab for the historical test.</p></section>` : ""}
    <section class="card-grid">${STRATEGY_TEMPLATES.map((template) => `
      <article class="strategy-card">
        <div class="strategy-head"><span class="card-icon">${escapeHtml(template.id.split("-").map((x) => x[0]).join("").toUpperCase())}</span>${statusChip(template.level, template.level === "Beginner" ? "ready" : "partial")}</div>
        <h3>${escapeHtml(template.name)}</h3><p>${escapeHtml(template.description)}</p>
        <div class="detail-list pro-only"><div><span>Inputs</span><strong>${escapeHtml(template.inputs)}</strong></div><div><span>Risk</span><strong>${escapeHtml(template.risk)}</strong></div><div><span>Assets</span><strong>${escapeHtml(template.assets)}</strong></div></div>
        <div class="card-footer"><small>${authenticated ? "Can be saved to your account" : "Preview available without sign-in"}</small><button class="text-link" type="button" data-open-template="${escapeHtml(template.id)}">Use template</button></div>
      </article>`).join("")}</section>
    <section class="panel" style="margin-top:14px"><div class="panel-head"><div class="panel-title"><h2>Your promotion path</h2><p>A strategy cannot skip directly from an idea to live money.</p></div></div><div class="quick-paths"><article class="path-card"><span class="card-icon">01</span><strong>Historical test</strong><p>Measure return, costs, worst loss, and benchmark comparison.</p></article><article class="path-card"><span class="card-icon">02</span><strong>Validation</strong><p>Check a period that was not used to tune the rules.</p></article><article class="path-card"><span class="card-icon">03</span><strong>Practice</strong><p>Observe the same rules with live information and simulated capital.</p></article></div></section>`;
}

function renderResults(payload) {
  const authenticated = Boolean(payload.auth_session?.authenticated);
  const score = payload.summary?.average_bot_score || 0;
  return `
    ${pageHeader("Test results", "Understand performance without a statistics degree", "Return is only one part of a result. BITprivat puts the worst loss, consistency, fees, and data quality beside it.", `<a class="button" href="/simulation">Run a historical test</a>`)}
    <section class="metric-grid"><article class="metric-card"><span>Personal completed tests</span><strong>${authenticated ? "0" : "--"}</strong><small>${authenticated ? "No saved run in this workspace" : "Sign in to store private results"}</small></article><article class="metric-card"><span>Research-bot average score</span><strong>${number(score, 1)}</strong><small>Not a personal investment return</small></article><article class="metric-card"><span>Test engine</span><strong>V1</strong><small>Local MVP; LEAN integration planned</small></article><article class="metric-card"><span>Live promotion</span><strong>Locked</strong><small>Paper and validation gates required</small></article></section>
    <section class="empty-state"><div><span class="card-icon">R</span><h2>Your first understandable report starts in Strategy Lab</h2><p>Choose an asset, period, entry rule, exit rule, and risk limit. The result will separate modeled performance from real-world proof.</p><a class="button" href="/simulation">Open Strategy Lab</a></div></section>
    <section class="panel" style="margin-top:14px"><div class="panel-head"><div class="panel-title"><h2>Every future report will answer these questions</h2><p>Simple mode first, professional metrics one level deeper.</p></div></div><div class="quick-paths"><article class="path-card"><span class="card-icon">EUR</span><strong>What happened to EUR 1,000?</strong><p>Final value after modeled fees and slippage.</p></article><article class="path-card"><span class="card-icon">DD</span><strong>What was the worst fall?</strong><p>Maximum decline from a previous portfolio high.</p></article><article class="path-card"><span class="card-icon">VS</span><strong>Was it better than holding?</strong><p>Compare the strategy with a simple benchmark.</p></article></div></section>`;
}

function renderSocial(payload) {
  const social = payload.social_trading || {};
  const traders = social.top_traders || [];
  const sState = socialState(payload);
  return `
    ${pageHeader("Expert Bots", "Explore one creator profile at a time", "Each bot is a BITprivat research model built from public evidence. Proxy returns are not verified trading performance.", `<button class="button secondary" type="button" data-social-method>How scoring works</button><a class="button" href="/connections">Connect sources</a>`)}
      <section class="inline-notice" style="margin-bottom:16px"><span class="state-dot ${sState === "live" ? "live" : "warning"}"></span><p><strong>${sState === "live" ? "YouTube discovery configured." : "Creator discovery needs a real provider."}</strong> Creator videos are thesis evidence, not proof of fills. Market-validated outcomes must replace proxy performance before commercial claims.</p></section>
    <section class="metric-grid"><article class="metric-card"><span>Creator profiles</span><strong>${number(traders.length)}</strong><small>Indexed research bots</small></article><article class="metric-card"><span>Paper allocation</span><strong>${money(social.allocated_usd || 0)}</strong><small>Never presented as live capital</small></article><article class="metric-card"><span>Available paper limit</span><strong>${money(social.unallocated_usd || social.portfolio_limit_usd || 0)}</strong><small>User-controlled simulation limit</small></article><article class="metric-card"><span>Discovery mode</span><strong>${escapeHtml(social.provider_mode || "setup")}</strong><small>Provider truth shown above</small></article></section>
    <section class="card-grid">${traders.map(renderTraderCard).join("") || `<div class="empty-state"><div><h2>No creator profiles found</h2><p>Connect creator intelligence sources to run a research scan.</p></div></div>`}</section>`;
}

function renderTraderCard(trader) {
  const avatar = trader.avatar_url ? `<img src="${escapeHtml(trader.avatar_url)}" alt="">` : escapeHtml(initials(trader.display_name));
  const roi = trader.validation_state === "validated" ? trader.avg_return : trader.proxy_roi ?? trader.roi_if_followed;
  return `
    <article class="trader-card">
      <div class="trader-head"><span class="trader-avatar">${avatar}</span><span class="trader-identity"><strong>${escapeHtml(trader.display_name)}</strong><small>${escapeHtml(trader.handle || trader.platform || "Creator")}</small></span>${statusChip(trader.validation_state || "proxy", trader.validation_state === "validated" ? "ready" : "partial")}</div>
      <p>${escapeHtml(trader.description || trader.strategy_profile || "Public creator evidence profile")}</p>
      <div class="trader-metrics"><div><span>BIT score</span><strong>${number(trader.composite_score, 1)}</strong></div><div><span>${trader.validation_state === "validated" ? "Return" : "Proxy ROI"}</span><strong class="${Number(roi) >= 0 ? "positive" : "negative"}">${percent(roi || 0)}</strong></div><div><span>Signals</span><strong>${number(trader.signal_count)}</strong></div></div>
      <div class="card-meta">${(trader.primary_assets || []).slice(0, 4).map((asset) => `<span>${escapeHtml(asset)}</span>`).join("")}</div>
      <div class="card-footer"><small>${escapeHtml(trader.copy_trade_readiness === "signals_only" ? "Signals only" : trader.deploy_status || "Not deployed")}</small><button class="text-link" type="button" data-open-trader="${escapeHtml(trader.slug)}">Explore profile</button></div>
    </article>`;
}

function renderPaper(payload) {
  const paper = payload.paper_trading || {};
  const summary = paper.summary || {};
  const venues = payload.paper_venues?.venues || [];
  const exposurePct = summary.equity ? clamp(summary.open_exposure / summary.equity * 100, 0, 100) : 0;
  return `
    ${pageHeader("Practice account", "Test decisions with simulated money", "Paper trading helps expose bad rules and execution assumptions. It does not predict live performance.", `<button class="button secondary" type="button" data-reset-paper disabled>Reset account</button><button class="button" type="button" data-preview-order>Preview a paper order</button>`)}
    <section class="metric-grid"><article class="metric-card"><span>Paper equity</span><strong>${money(summary.equity || summary.starting_balance)}</strong><small>Simulated account value</small></article><article class="metric-card"><span>Available cash</span><strong>${money(summary.cash_balance)}</strong><small>Before estimated fees</small></article><article class="metric-card"><span>Unrealized P&L</span><strong class="${Number(summary.unrealized_pnl) >= 0 ? "positive" : "negative"}">${money(summary.unrealized_pnl)}</strong><small>Open paper positions only</small></article><article class="metric-card"><span>Total return</span><strong class="${Number(summary.total_return) >= 0 ? "positive" : "negative"}">${percent(summary.total_return || 0)}</strong><small>Simulation, not real return</small></article></section>
    <section class="content-grid asymmetric">
      <article class="panel"><div class="panel-head"><div class="panel-title"><h2>Open paper positions</h2><p>Size, entry, current value, and simulated P&L.</p></div>${statusChip(`${summary.open_positions || 0} open`, "paper")}</div>${paper.positions?.length ? `<div class="position-list">${paper.positions.map(renderPosition).join("")}</div>` : `<div class="empty-state"><div><span class="card-icon">0</span><h3>No open paper positions</h3><p>Preview a simulated order to see fees, slippage, and risk checks before placing it.</p><button class="button small" type="button" data-preview-order>Preview order</button></div></div>`}</article>
      <aside class="content-grid">
        <article class="panel"><div class="panel-head"><div class="panel-title"><h2>Exposure</h2><p>How much of the paper account is currently at risk.</p></div></div><div class="allocation-summary"><div class="allocation-line"><span>Open exposure</span><strong>${money(summary.open_exposure)}</strong></div><div class="progress-track"><i style="width:${exposurePct}%"></i></div><div class="allocation-line"><span>Portfolio share</span><strong>${number(exposurePct, 1)}%</strong></div></div></article>
        <article class="panel"><div class="panel-head"><div class="panel-title"><h2>Available practice venues</h2><p>Configured does not mean approved for live use.</p></div></div><div class="compact-list">${venues.slice(0, 5).map((venue) => `<div class="compact-item"><span class="compact-copy"><strong>${escapeHtml(venue.name || venue.venue_id || venue.id)}</strong><span>${escapeHtml(venue.summary || venue.mode || "Paper workflow")}</span></span>${statusChip(venue.ready ? "Ready" : venue.state || "Planned", venue.ready ? "ready" : "planned")}</div>`).join("")}</div></article>
      </aside>
    </section>`;
}

function renderPosition(position) {
  const pnl = position.unrealized_pnl || position.realized_pnl || 0;
  return `<div class="position-row"><span class="activity-icon">${escapeHtml(position.asset || "?")}</span><span class="compact-copy"><strong>${escapeHtml(position.asset)} - ${escapeHtml(position.side || "position")}</strong><span>Entry ${money(position.entry_price || position.average_entry_price, "USD", 2)} - size ${number(position.quantity, 4)}</span></span><strong class="number ${Number(pnl) >= 0 ? "positive" : "negative"}">${money(pnl)}</strong></div>`;
}

function renderPortfolio(payload) {
  const summary = payload.paper_trading?.summary || {};
  const allocations = payload.social_trading?.allocations || [];
  return `
    ${pageHeader("Portfolio", "See where simulated money is allocated", "This view currently reflects the internal paper ledger. Connected live accounts remain gated.", `<a class="button secondary" href="/social-traders">Expert bots</a><a class="button" href="/paper">Practice account</a>`)}
    <section class="metric-grid"><article class="metric-card"><span>Total paper equity</span><strong>${money(summary.equity || summary.starting_balance)}</strong><small>Simulated, not custodied</small></article><article class="metric-card"><span>Cash</span><strong>${money(summary.cash_balance)}</strong><small>Available paper buying power</small></article><article class="metric-card"><span>Realized P&L</span><strong class="${Number(summary.realized_pnl) >= 0 ? "positive" : "negative"}">${money(summary.realized_pnl)}</strong><small>Closed paper positions</small></article><article class="metric-card"><span>Win rate</span><strong>${percent(summary.win_rate || 0)}</strong><small>${summary.closed_positions || 0} closed position(s)</small></article></section>
    <section class="content-grid two"><article class="panel"><div class="panel-head"><div class="panel-title"><h2>Asset positions</h2><p>Current paper exposure by asset.</p></div></div>${payload.paper_trading?.positions?.length ? `<div class="position-list">${payload.paper_trading.positions.map(renderPosition).join("")}</div>` : `<div class="empty-state"><div><h3>No allocation yet</h3><p>Your paper account is fully in cash.</p><a class="button small" href="/paper">Open practice account</a></div></div>`}</article><article class="panel"><div class="panel-head"><div class="panel-title"><h2>Expert-bot allocations</h2><p>Delegated research budgets remain paper-only.</p></div></div>${allocations.length ? `<div class="compact-list">${allocations.map((item) => `<div class="compact-item"><span class="compact-copy"><strong>${escapeHtml(item.trader_name || item.trader_slug)}</strong><span>${escapeHtml(item.mode || "signals")}</span></span><strong class="number">${money(item.allocation_limit_usd || item.delegated_usd)}</strong></div>`).join("")}</div>` : `<div class="empty-state"><div><h3>No expert bot allocation</h3><p>Explore a creator profile and choose signals or managed-paper research.</p><a class="button small" href="/social-traders">Explore bots</a></div></div>`}</article></section>`;
}

function renderConnections(payload) {
  const p = payload.provider_status || {};
  const connectors = [
    { name: "Exchange market APIs", source: p.market_provider_source, mode: p.market_provider_mode, ready: p.market_provider_ready, live: marketState(payload) === "live", detail: p.market_provider_warning || "Binance, Hyperliquid, and CoinGecko-style free market feeds power the MVP when configured." },
    { name: "Prediction market APIs", source: "Polymarket / Kalshi public surfaces", mode: "public", ready: true, live: true, detail: "Public event-market surfaces support research and paper strategies without live execution." },
    { name: "Creator intelligence", source: p.social_discovery_provider_source, mode: p.social_discovery_provider_mode, ready: p.social_discovery_ready, live: socialState(payload) === "live", detail: p.social_discovery_warning },
    { name: "Macro data", source: p.macro_provider_source, mode: p.macro_provider_mode, ready: p.macro_provider_ready, live: p.macro_provider_live_capable && p.macro_provider_configured, detail: p.macro_provider_warning },
    { name: "Wallet and stablecoin rails", source: p.wallet_provider_source || "Read-only wallet connection", mode: p.wallet_provider_mode, ready: p.wallet_provider_ready, live: p.wallet_provider_live_capable && p.wallet_provider_configured, detail: p.wallet_provider_warning || "Track read-only wallet addresses and USDC/USDT rails on Base, Arbitrum, Polygon, Optimism, Ethereum, Solana, and Bitcoin." },
  ];
  return `
    ${pageHeader("Connections", "Free APIs, exchanges, wallets, and intelligence feeds", "Connect only what you already have. Missing providers stay blocked until real credentials are configured, and credentials stay in secret stores.", `<a class="button secondary" href="/status">System status</a><button class="button" type="button" data-open-account>Account and wallet</button>`)}
    <section class="card-grid">${connectors.map((connector) => `
      <article class="provider-card"><div class="card-topline"><span class="card-icon">${escapeHtml(initials(connector.name))}</span>${statusChip(connector.live ? "Live" : connector.ready ? "Ready" : "Needs setup", connector.live || connector.ready ? "ready" : "blocked")}</div><h3>${escapeHtml(connector.name)}</h3><p>${escapeHtml(connector.detail || "No provider warning reported.")}</p><div class="detail-list"><div><span>Mode</span><strong>${escapeHtml(connector.mode || "Not set")}</strong></div><div><span>Source</span><strong>${escapeHtml(connector.source || "Not set")}</strong></div></div><div class="card-footer"><small>${connector.live ? "Provider-backed" : "Connect real credentials"}</small><button class="text-link" type="button" data-connection-detail="${escapeHtml(connector.name)}">Details</button></div></article>`).join("")}</section>
    <section class="inline-notice" style="margin-top:16px"><span class="state-dot warning"></span><p><strong>Credentials stay out of this interface.</strong> API keys, database URLs, and wallet secrets belong in deployment secret stores and must never be pasted into public pages or support chat.</p></section>`;
}

function renderLearn() {
  return `
    ${pageHeader("Learning Center", "Learn only what you need for the next decision", "Short lessons explain financial concepts in normal language and connect directly to the feature you are using.")}
    <section class="card-grid">${LESSONS.map((lesson, index) => `<article class="lesson-card"><div class="card-topline"><span class="card-icon">${String(index + 1).padStart(2, "0")}</span><span class="status-chip">${escapeHtml(lesson.duration)}</span></div><h3>${escapeHtml(lesson.title)}</h3><p>${escapeHtml(lesson.description)}</p><div class="card-footer"><small>Beginner guide</small><button class="text-link" type="button" data-open-lesson="${escapeHtml(lesson.id)}">Read lesson</button></div></article>`).join("")}</section>`;
}

function renderSettings(payload) {
  const session = payload.auth_session || {};
  return `
    ${pageHeader("Settings", "Make BITprivat fit how you think", "Language, appearance, experience level, number formatting, and safety confirmations remain consistent on every page.")}
    <section class="content-grid two">
      <article class="panel"><div class="panel-head"><div class="panel-title"><h2>Display</h2><p>Saved on this browser immediately.</p></div></div><div class="setting-row"><span class="setting-copy"><strong>Dark appearance</strong><span>Use a low-light interface across all product pages.</span></span><label class="toggle"><input type="checkbox" data-setting-theme ${state.theme === "dark" ? "checked" : ""}><i></i></label></div><div class="setting-row"><span class="setting-copy"><strong>Professional details</strong><span>Show source schemas, technical metrics, and advanced controls.</span></span><label class="toggle"><input type="checkbox" data-setting-experience ${state.experience === "pro" ? "checked" : ""}><i></i></label></div><div class="setting-row"><span class="setting-copy"><strong>Language</strong><span>English is default; Romanian is available across the shared shell.</span></span><select class="chip-button" data-setting-language><option value="en" ${state.language === "en" ? "selected" : ""}>English</option><option value="ro" ${state.language === "ro" ? "selected" : ""}>Romana</option></select></div></article>
      <article class="panel"><div class="panel-head"><div class="panel-title"><h2>Safety</h2><p>Live execution controls remain locked until approved.</p></div></div><div class="setting-row"><span class="setting-copy"><strong>Confirm every order</strong><span>Always show estimated fees, slippage, and impact before submission.</span></span><label class="toggle"><input type="checkbox" checked disabled><i></i></label></div><div class="setting-row"><span class="setting-copy"><strong>Paper-first mode</strong><span>Orders use simulated capital unless a future live workflow passes all gates.</span></span><label class="toggle"><input type="checkbox" checked disabled><i></i></label></div><div class="setting-row"><span class="setting-copy"><strong>Account security</strong><span>${session.authenticated ? "Manage account and connected wallets here." : "Create a free account before changing personal security settings."}</span></span><button class="button secondary small" type="button" data-open-account>Open account</button></div></article>
    </section>
    <section class="panel" style="margin-top:14px"><div class="panel-head"><div class="panel-title"><h2>Product truth</h2><p>These labels cannot be disabled.</p></div></div><div class="setting-row"><span class="setting-copy"><strong>Data source and freshness</strong><span>Every material value should state where it came from and when it was observed.</span></span>${statusChip("Required", "ready")}</div><div class="setting-row"><span class="setting-copy"><strong>Real, proxy, paper, and live labels</strong><span>Simulation and creator proxy results remain visibly separated from verified outcomes.</span></span>${statusChip("Required", "ready")}</div></section>`;
}

function initials(value) {
  return String(value || "BITprivat").split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase();
}

async function renderCurrentPage(force = false) {
  syncActiveNav();
  document.title = `${pageTitle(state.page)} | BITprivat`;
  root.innerHTML = `<div class="page-skeleton" aria-label="Loading page"><div class="skeleton-line wide"></div><div class="skeleton-line"></div><div class="skeleton-grid"><i></i><i></i><i></i></div></div>`;
  try {
    const payload = await loadDashboard(force);
    const renderers = {
      home: renderHome,
      data: renderData,
      ideas: renderIdeas,
      strategies: renderStrategies,
      results: renderResults,
      social: renderSocial,
      paper: renderPaper,
      portfolio: renderPortfolio,
      connections: renderConnections,
      learn: renderLearn,
      settings: renderSettings,
    };
    root.innerHTML = renderers[state.page](payload);
    root.focus({ preventScroll: true });
  } catch (error) {
    renderError(error);
  }
}

function pageTitle(page) {
  return ({ home: "Home", data: "Explore Data", ideas: "My Ideas", strategies: "Strategies", results: "Test Results", social: "Expert Bots", paper: "Practice", portfolio: "Portfolio", connections: "Connections", learn: "Learn", settings: "Settings" })[page] || "App";
}

function openDrawer({ kicker = "Details", title = "BITprivat", body = "", footer = "" }) {
  document.getElementById("drawer-kicker").textContent = kicker;
  document.getElementById("drawer-title").textContent = title;
  document.getElementById("drawer-body").innerHTML = body;
  document.getElementById("drawer-footer").innerHTML = footer;
  drawer.classList.add("open");
  drawerBackdrop.classList.add("open");
  drawer.setAttribute("aria-hidden", "false");
  document.body.style.overflow = "hidden";
  document.getElementById("drawer-close").focus();
}

function closeDrawer() {
  drawer.classList.remove("open");
  drawerBackdrop.classList.remove("open");
  drawer.setAttribute("aria-hidden", "true");
  document.body.style.overflow = "";
}

function openDataset(datasetId) {
  const dataset = DATASETS.find((item) => item.id === datasetId);
  if (!dataset) return;
  const runtime = datasetRuntime(dataset, state.dashboard || {});
  openDrawer({
    kicker: dataset.question,
    title: dataset.name,
    body: `<section class="drawer-section"><p>${escapeHtml(dataset.description)}</p></section><section class="drawer-section"><h3>Coverage and use</h3><div class="detail-list"><div><span>Assets</span><strong>${escapeHtml(dataset.assets)}</strong></div><div><span>Coverage</span><strong>${escapeHtml(dataset.coverage)}</strong></div><div><span>Current source</span><strong>${escapeHtml(runtime.source)}</strong></div><div><span>License posture</span><strong>${escapeHtml(dataset.license)}</strong></div></div></section><section class="drawer-section"><h3>Permitted product uses</h3><div class="card-meta">${dataset.uses.map((use) => `<span>${escapeHtml(use)}</span>`).join("")}</div></section><div class="inline-notice"><span class="state-dot ${runtime.state === "live" ? "live" : "warning"}"></span><p><strong>${escapeHtml(runtime.label)} state.</strong> Availability does not override provider terms or create redistribution rights.</p></div>`,
    footer: dataset.id === "user-upload" ? `<button class="button" type="button" disabled>Upload planned</button>` : `<a class="button secondary" href="/ideas">Use in an idea</a><button class="button" type="button" data-close-drawer>Close preview</button>`,
  });
}

function openAsset(symbol) {
  const asset = (state.dashboard?.assets || []).find((item) => item.asset === symbol);
  if (!asset) return;
  openDrawer({
    kicker: "Market snapshot",
    title: asset.asset,
    body: `<section class="drawer-section"><div class="detail-list"><div><span>Price</span><strong class="number">${money(asset.price, "USD", asset.price < 10 ? 3 : 0)}</strong></div><div><span>24-hour change</span><strong class="number ${Number(asset.change_24h) >= 0 ? "positive" : "negative"}">${percent(asset.change_24h)}</strong></div><div><span>Volume</span><strong class="number">${money(asset.volume_24h)}</strong></div><div><span>Volatility</span><strong class="number">${percent(asset.volatility)}</strong></div><div><span>Source</span><strong>${escapeHtml(asset.source)}</strong></div><div><span>Observed</span><strong>${escapeHtml(dateLabel(asset.as_of))}</strong></div></div></section><div class="inline-notice"><span class="state-dot warning"></span><p>A current price is not a recommendation. Add rules and a loss limit before testing an idea.</p></div>`,
    footer: `<a class="button secondary" href="/ideas">Create idea</a><button class="button" type="button" data-preview-order data-asset="${escapeHtml(asset.asset)}">Preview paper order</button>`,
  });
}

function openNewIdea() {
  openDrawer({
    kicker: "New research idea",
    title: "What do you believe may happen?",
    body: `<form class="form-grid" id="idea-form"><label class="field"><span>Short title</span><input name="title" maxlength="80" required placeholder="Bitcoin trend after liquidity improves"></label><label class="field"><span>Your hypothesis</span><textarea name="hypothesis" maxlength="600" required placeholder="I believe... because..."></textarea><small>Write a claim that historical evidence could disprove.</small></label><div class="form-row"><label class="field"><span>Market</span><select name="market"><option>Crypto</option><option>Prediction markets</option><option>Multi-asset</option></select></label><label class="field"><span>Primary evidence</span><select name="evidence"><option>Price and volume</option><option>Creator evidence</option><option>Macro data</option><option>Prediction markets</option></select></label></div><label class="field"><span>What would prove it wrong?</span><textarea name="invalidation" maxlength="400" placeholder="The idea is wrong if..."></textarea></label></form>`,
    footer: `<button class="button secondary" type="button" data-close-drawer>Cancel</button><button class="button" type="submit" form="idea-form">Save idea</button>`,
  });
}

function saveIdea(form) {
  const formData = new FormData(form);
  const idea = {
    id: crypto.randomUUID ? crypto.randomUUID() : `idea-${Date.now()}`,
    title: String(formData.get("title") || "").trim(),
    hypothesis: String(formData.get("hypothesis") || "").trim(),
    market: String(formData.get("market") || "Crypto"),
    evidence: String(formData.get("evidence") || "Price and volume"),
    invalidation: String(formData.get("invalidation") || "").trim(),
    stage: "Idea",
    createdAt: new Date().toISOString(),
  };
  if (!idea.title || !idea.hypothesis) return;
  state.ideas.unshift(idea);
  localStorage.setItem("bp-ideas", JSON.stringify(state.ideas));
  closeDrawer();
  toast("Idea saved", "It is stored on this device until the shared Research Idea API is implemented.");
  root.innerHTML = renderIdeas();
}

function promoteIdea(ideaId) {
  const idea = state.ideas.find((item) => item.id === ideaId);
  if (!idea) return;
  state.strategyDraft = { ...idea, promotedAt: new Date().toISOString() };
  localStorage.setItem("bp-strategy-draft", JSON.stringify(state.strategyDraft));
  window.location.href = "/strategies";
}

function openTemplate(templateId) {
  const template = STRATEGY_TEMPLATES.find((item) => item.id === templateId);
  if (!template) return;
  const draftCopy = state.strategyDraft ? `<div class="inline-notice"><span class="state-dot live"></span><p><strong>Idea attached:</strong> ${escapeHtml(state.strategyDraft.title)}</p></div>` : "";
  openDrawer({
    kicker: template.level,
    title: template.name,
    body: `${draftCopy}<section class="drawer-section"><p>${escapeHtml(template.description)}</p></section><section class="drawer-section"><h3>Template structure</h3><div class="detail-list"><div><span>Information</span><strong>${escapeHtml(template.inputs)}</strong></div><div><span>Assets</span><strong>${escapeHtml(template.assets)}</strong></div><div><span>Starting risk</span><strong>${escapeHtml(template.risk)}</strong></div><div><span>Required next step</span><strong>Historical test</strong></div></div></section><div class="inline-notice"><span class="state-dot warning"></span><p>Template settings are a starting point, not proof that the strategy works.</p></div>`,
    footer: `<button class="button secondary" type="button" data-close-drawer>Keep browsing</button><a class="button" href="/simulation">Configure in Strategy Lab</a>`,
  });
}

function openTrader(slug) {
  const trader = state.dashboard?.social_trading?.top_traders?.find((item) => item.slug === slug);
  if (!trader) return;
  const evidence = (trader.evidence || []).slice(0, 5).map((item) => `<div class="compact-item"><span class="activity-icon">${escapeHtml(item.asset || "?")}</span><span class="compact-copy"><strong>${escapeHtml(item.title)}</strong><span>${escapeHtml(item.summary)}</span><small>${dateLabel(item.observed_at)} - confidence ${percent(item.confidence || 0)}</small></span></div>`).join("");
  openDrawer({
    kicker: "Creator research bot",
    title: trader.display_name,
    body: `<section class="drawer-section"><p>${escapeHtml(trader.strategy_profile || trader.description)}</p></section><section class="drawer-section"><h3>Performance truth</h3><div class="detail-list"><div><span>Validation</span><strong>${escapeHtml(trader.validation_state || "proxy")}</strong></div><div><span>BIT score</span><strong class="number">${number(trader.composite_score, 1)}</strong></div><div><span>Proxy ROI</span><strong class="number ${Number(trader.proxy_roi) >= 0 ? "positive" : "negative"}">${percent(trader.proxy_roi || 0)}</strong></div><div><span>Mode allowed</span><strong>${escapeHtml(trader.copy_trade_readiness || "signals_only")}</strong></div></div><p style="margin-top:10px">${escapeHtml(trader.pnl_history_summary || trader.performance_basis)}</p></section><section class="drawer-section"><h3>Current evidence-derived view</h3><p>${escapeHtml(trader.current_market_view || "No current market view available.")}</p></section><section class="drawer-section"><h3>Recent evidence</h3><div class="compact-list">${evidence || emptyCompact("No evidence available")}</div></section><div class="inline-notice"><span class="state-dot warning"></span><p><strong>Research bot, not impersonation.</strong> Public evidence can be incomplete or late. Managed mode remains paper-only.</p></div>`,
    footer: `<button class="button secondary" type="button" data-close-drawer>Close</button><a class="button" href="/paper">Allocate paper budget</a>`,
  });
}

function openOrderPreview(asset = "BTC") {
  closeDrawer();
  if (!state.dashboard?.auth_session?.authenticated) {
    openDrawer({
      kicker: "Personal workspace required",
      title: "Sign in before previewing an order",
      body: `<section class="drawer-section"><p>Order previews use your personal paper balance, exposure, and risk limits. The guest workspace is read-only until you create an account.</p></section><div class="inline-notice"><span class="state-dot warning"></span><p>No order was created. Sign in or register, then return to Practice to calculate fees, slippage, and risk checks.</p></div>`,
      footer: `<button class="button secondary" type="button" data-close-drawer>Not now</button><button class="button" type="button" data-open-account>Sign in or register</button>`,
    });
    return;
  }
  openDrawer({
    kicker: "Paper order preview",
    title: "Review cost and risk before submission",
    body: `<form class="form-grid" id="order-preview-form"><div class="form-row"><label class="field"><span>Asset</span><select name="asset">${(state.dashboard?.assets || [{ asset: "BTC" }, { asset: "ETH" }, { asset: "SOL" }]).map((item) => `<option value="${escapeHtml(item.asset)}" ${item.asset === asset ? "selected" : ""}>${escapeHtml(item.asset)}</option>`).join("")}</select></label><label class="field"><span>Direction</span><select name="side"><option value="buy">Buy</option><option value="sell">Sell</option></select></label></div><label class="field"><span>Order type</span><select name="order_type"><option value="market">Market</option><option value="limit">Limit</option></select></label><label class="field"><span>Amount in USD</span><input name="notional_usd" type="number" min="10" max="10000" step="10" value="100" required><small>This uses simulated capital only.</small></label><label class="field" id="limit-price-field" hidden><span>Limit price</span><input name="price" type="number" min="0.0001" step="0.0001"></label></form><div id="order-preview-result" style="margin-top:16px"></div>`,
    footer: `<button class="button secondary" type="button" data-close-drawer>Cancel</button><button class="button" type="submit" form="order-preview-form">Calculate preview</button>`,
  });
  const orderType = document.querySelector('#order-preview-form [name="order_type"]');
  orderType?.addEventListener("change", () => {
    const field = document.getElementById("limit-price-field");
    field.hidden = orderType.value !== "limit";
  });
}

async function submitOrderPreview(form) {
  const data = new FormData(form);
  const orderType = String(data.get("order_type") || "market");
  const payload = {
    venue: "paper",
    asset: String(data.get("asset") || "BTC"),
    side: String(data.get("side") || "buy"),
    order_type: orderType,
    notional_usd: Number(data.get("notional_usd") || 0),
    is_paper: true,
  };
  if (orderType === "limit") payload.price = Number(data.get("price") || 0);
  const target = document.getElementById("order-preview-result");
  target.innerHTML = `<div class="page-skeleton"><div class="skeleton-line wide"></div><div class="skeleton-line"></div></div>`;
  try {
    const preview = await fetchJson("/api/v1/trading/preview", { method: "POST", body: JSON.stringify(payload) });
    target.innerHTML = `<section class="drawer-section"><h3>Estimated impact</h3><div class="detail-list"><div><span>Reference price</span><strong class="number">${money(preview.reference_price, "USD", 2)}</strong></div><div><span>Estimated fill</span><strong class="number">${money(preview.estimated_fill_price, "USD", 2)}</strong></div><div><span>Quantity</span><strong class="number">${number(preview.quantity, 6)}</strong></div><div><span>Fee</span><strong class="number">${money(preview.estimated_fee, "USD", 2)}</strong></div><div><span>Total cost</span><strong class="number">${money(preview.estimated_total_cost, "USD", 2)}</strong></div></div></section><div class="inline-notice"><span class="state-dot ${preview.risk?.approved ? "live" : "blocked"}"></span><p><strong>${preview.risk?.approved ? "Paper risk checks passed." : "Risk checks blocked this order."}</strong> ${escapeHtml(preview.message || preview.next_action || "Review the checks before continuing.")}</p></div>`;
    toast("Preview calculated", "No order was placed. Review remains separate from submission.");
  } catch (error) {
    target.innerHTML = `<div class="error-state"><h2>Preview unavailable</h2><p>${escapeHtml(error.message)}</p></div>`;
  }
}

function openMethodology() {
  openDrawer({
    kicker: "Evidence and performance",
    title: "How expert bots are scored",
    body: `<section class="drawer-section"><h3>1. Collect evidence</h3><p>BITprivat records public creator statements with source, timestamp, asset, direction, confidence, and supporting context.</p></section><section class="drawer-section"><h3>2. Separate claim types</h3><p>Educational content, general commentary, and actionable calls are not treated as equivalent.</p></section><section class="drawer-section"><h3>3. Resolve outcomes</h3><p>A validated result requires point-in-time market prices and the stated horizon. Content-derived proxy moves remain visibly labeled.</p></section><section class="drawer-section"><h3>4. Apply risk and provenance</h3><p>Freshness, source quality, sample size, drawdown, and consistency influence the BIT score.</p></section>`,
    footer: `<button class="button" type="button" data-close-drawer>Understood</button>`,
  });
}

function openLicenseGuide() {
  openDrawer({
    kicker: "Data rights",
    title: "Availability is not permission to redistribute",
    body: `<section class="drawer-section"><p>BITprivat must know who owns a dataset and which uses are allowed before activating it commercially.</p></section><section class="drawer-section"><h3>Approved acquisition paths</h3><div class="compact-list"><div class="compact-item"><span class="activity-icon">1</span><span class="compact-copy"><strong>Direct provider contract</strong><span>BITprivat receives the needed commercial rights.</span></span></div><div class="compact-item"><span class="activity-icon">2</span><span class="compact-copy"><strong>Permitted public data</strong><span>Terms allow the intended commercial workflow.</span></span></div><div class="compact-item"><span class="activity-icon">3</span><span class="compact-copy"><strong>User-owned connection</strong><span>The user supplies credentials and holds the required license.</span></span></div><div class="compact-item"><span class="activity-icon">4</span><span class="compact-copy"><strong>User upload</strong><span>The user declares rights and accepts validation rules.</span></span></div></div></section>`,
    footer: `<button class="button" type="button" data-close-drawer>Close</button>`,
  });
}

function openConnectionDetail(name) {
  const featureItems = state.dashboard?.feature_readiness?.items || [];
  const relevant = featureItems.filter((item) => JSON.stringify(item).toLowerCase().includes(name.toLowerCase().split(" ")[0])).slice(0, 4);
  openDrawer({
    kicker: "Connection detail",
    title: name,
    body: `<section class="drawer-section"><p>Provider health, secrets, data rights, and production readiness are independent checks. A configured API is not automatically approved for commercial live execution.</p></section><section class="drawer-section"><h3>Related readiness items</h3><div class="compact-list">${relevant.length ? relevant.map((item) => `<div class="compact-item"><span class="compact-copy"><strong>${escapeHtml(item.label || item.name || item.key)}</strong><span>${escapeHtml(item.detail || item.summary || item.state)}</span></span>${statusChip(item.state || "partial", item.state || "partial")}</div>`).join("") : emptyCompact("No detailed readiness record matched this connection.")}</div></section>`,
    footer: `<a class="button secondary" href="/status">Open status</a><a class="button" href="/connections">Connections</a>`,
  });
}

function openLesson(lessonId) {
  const lesson = LESSONS.find((item) => item.id === lessonId);
  if (!lesson) return;
  const content = {
    "data-mode": "Live means a configured provider supplied the current value. Delayed means the value intentionally trails the market. Setup means a real provider must be connected. Unavailable means the system cannot provide a trustworthy value.",
    backtest: "A backtest replays rules against historical information. It can reveal behavior, cost, drawdown, and obvious weaknesses. It cannot guarantee future results, remove selection bias automatically, or reproduce every real fill.",
    drawdown: "Drawdown measures how far a portfolio fell from a previous high before recovering or ending. A strategy that turns EUR 1,000 into EUR 1,200 may still be unsuitable if it temporarily fell to EUR 500.",
    paper: "Paper trading uses current or replayed information with simulated capital. It tests whether rules run as expected, but real liquidity, psychology, outages, and fills may differ.",
    creator: "Creator bots summarize evidence from public content. Titles and commentary are not verified trades. BITprivat separates proxy outcomes from calls resolved against point-in-time market prices.",
    risk: "A loss limit defines how much can be lost before a position or strategy pauses. Set it before entry, combine it with position size, and never assume a stop will fill at the exact requested price.",
  }[lessonId];
  openDrawer({ kicker: lesson.duration, title: lesson.title, body: `<section class="drawer-section"><p>${escapeHtml(content)}</p></section><div class="inline-notice"><span class="state-dot warning"></span><p>This educational content is general information, not personal investment advice.</p></div>`, footer: `<button class="button" type="button" data-close-drawer>Finish lesson</button>` });
}

function openAccount() {
  const session = state.dashboard?.auth_session || {};
  const profile = state.dashboard?.user_profile || {};
  const wallets = profile.wallet_connections || [];
  openDrawer({
    kicker: session.authenticated ? "Personal workspace" : "Free MVP workspace",
    title: session.user?.display_name || profile.display_name || "Create account and connect wallet",
    body: `<section class="drawer-section"><div class="detail-list"><div><span>Authentication</span><strong>${session.authenticated ? "Signed in" : "Guest access"}</strong></div><div><span>Tier</span><strong>${escapeHtml(profile.tier || "Free research")}</strong></div><div><span>Wallets</span><strong>${wallets.length} connected</strong></div><div><span>Trading mode</span><strong>Paper-first</strong></div></div></section><div class="inline-notice"><span class="state-dot warning"></span><p>Accounts unlock durable preferences, paper strategies, alerts, and read-only wallet tracking. Live execution stays locked until risk, legal, and provider gates are complete.</p></div>${session.authenticated ? "" : `<section class="drawer-section"><h3>Create free account</h3><form class="stack-form" id="platform-register-form"><label><span>Name</span><input name="display_name" type="text" autocomplete="name" required></label><label><span>Email</span><input name="email" type="email" autocomplete="email" required></label><label><span>Password</span><input name="password" type="password" autocomplete="new-password" minlength="8" required></label><button class="button" type="submit">Create account</button></form></section><section class="drawer-section"><h3>Sign in</h3><form class="stack-form" id="platform-login-form"><label><span>Email</span><input name="email" type="email" autocomplete="email" required></label><label><span>Password</span><input name="password" type="password" autocomplete="current-password" required></label><button class="button secondary" type="submit">Sign in</button></form></section>`}<section class="drawer-section"><h3>Connect read-only wallet</h3><form class="stack-form" id="platform-wallet-form"><label><span>Chain</span><select name="chain"><option value="base">Base</option><option value="arbitrum">Arbitrum</option><option value="polygon">Polygon</option><option value="optimism">Optimism</option><option value="ethereum">Ethereum</option><option value="solana">Solana</option><option value="bitcoin">Bitcoin</option></select></label><label><span>Provider</span><select name="provider"><option value="metamask">MetaMask</option><option value="walletconnect">WalletConnect</option><option value="coinbase">Coinbase Wallet</option><option value="phantom">Phantom</option><option value="ledger">Ledger</option></select></label><label><span>Address</span><input name="address" type="text" maxlength="128" placeholder="Auto-filled for browser EVM wallets"></label><label><span>Label</span><input name="label" type="text" maxlength="64" placeholder="Main USDC wallet"></label><button class="button" type="submit">Connect wallet</button></form><div class="card-meta"><span>USDC</span><span>USDT</span><span>Base</span><span>Arbitrum</span><span>Polygon</span><span>Optimism</span></div><p class="muted-copy">Read-only wallet tracking only. No private keys, no custody, and no stablecoin transfer button in this MVP.</p></section><section class="drawer-section"><h3>Connected wallets</h3>${wallets.length ? `<div class="compact-list">${wallets.map((wallet) => `<div class="compact-item"><span class="compact-copy"><strong>${escapeHtml(wallet.label || wallet.provider)}</strong><span>${escapeHtml(wallet.chain)} · ${escapeHtml(wallet.address)}</span></span></div>`).join("")}</div>` : `<p class="muted-copy">No wallets connected yet.</p>`}</section>`,
    footer: `<a class="button secondary" href="/connections">API connections</a><button class="button" type="button" data-close-drawer>Close</button>`,
  });
}

function openNotifications() {
  const alerts = state.dashboard?.user_profile?.recent_alerts || [];
  openDrawer({
    kicker: "Alerts",
    title: "Notifications",
    body: alerts.length ? `<div class="compact-list">${alerts.slice(0, 12).map((alert) => `<div class="compact-item"><span class="activity-icon">!</span><span class="compact-copy"><strong>${escapeHtml(alert.title || alert.alert_type || "BITprivat alert")}</strong><span>${escapeHtml(alert.message || alert.summary || "")}</span><small>${dateLabel(alert.created_at)}</small></span></div>`).join("")}</div>` : `<div class="empty-state"><div><h3>No notifications</h3><p>Important provider, strategy, paper-trading, and risk events will appear here.</p></div></div>`,
    footer: `<a class="button secondary" href="/settings">Notification settings</a><button class="button" type="button" data-close-drawer>Close</button>`,
  });
}

function showProviderDetails() {
  const p = state.dashboard?.provider_status || {};
  openDrawer({
    kicker: "Delivery truth",
    title: marketState(state.dashboard) === "live" ? "Live provider data" : "Provider setup required",
    body: `<section class="drawer-section"><div class="detail-list"><div><span>Environment</span><strong>${escapeHtml(p.environment_name || "Unknown")}</strong></div><div><span>Deployment</span><strong>${escapeHtml(p.deployment_target || "Unknown")}</strong></div><div><span>Database</span><strong>${escapeHtml(p.database_backend || "Unknown")}</strong></div><div><span>Market mode</span><strong>${escapeHtml(p.market_provider_mode || "Unknown")}</strong></div><div><span>Market source</span><strong>${escapeHtml(p.market_provider_source || "Unknown")}</strong></div><div><span>Social mode</span><strong>${escapeHtml(p.social_discovery_provider_mode || "Unknown")}</strong></div></div></section>`,
    footer: `<a class="button secondary" href="/connections">Connections</a><a class="button" href="/status">System status</a>`,
  });
}

function toast(title, message) {
  const region = document.getElementById("toast-region");
  const element = document.createElement("div");
  element.className = "toast";
  element.innerHTML = `<i></i><div><strong>${escapeHtml(title)}</strong><p>${escapeHtml(message)}</p></div>`;
  region.appendChild(element);
  window.setTimeout(() => element.remove(), 4500);
}

const commandItems = [
  ["HM", "Home", "Portfolio and next steps", "/dashboard"],
  ["DT", "Explore data", "Sources, coverage, and licensing", "/data"],
  ["ID", "My ideas", "Capture a testable belief", "/ideas"],
  ["ST", "Strategies", "Templates and rules", "/strategies"],
  ["RS", "Test results", "Historical reports", "/results"],
  ["EB", "Expert bots", "Creator evidence profiles", "/social-traders"],
  ["PP", "Practice", "Paper orders and positions", "/paper"],
  ["PF", "Portfolio", "Allocation and P&L", "/portfolio"],
  ["CN", "Connections", "Provider readiness", "/connections"],
  ["LR", "Learning Center", "Short plain-language guides", "/learn"],
  ["SE", "Settings", "Theme, language, and safety", "/settings"],
  ["LB", "Strategy Lab", "Advanced historical testing", "/simulation"],
];

function openCommandPalette() {
  commandPalette.classList.add("open");
  commandBackdrop.classList.add("open");
  commandPalette.setAttribute("aria-hidden", "false");
  commandInput.value = "";
  renderCommandResults("");
  window.setTimeout(() => commandInput.focus(), 20);
}

function closeCommandPalette() {
  commandPalette.classList.remove("open");
  commandBackdrop.classList.remove("open");
  commandPalette.setAttribute("aria-hidden", "true");
}

function renderCommandResults(query) {
  const normalized = query.trim().toLowerCase();
  const matches = commandItems.filter((item) => !normalized || `${item[1]} ${item[2]}`.toLowerCase().includes(normalized));
  commandResults.innerHTML = `<p class="command-group-label">Pages and tools</p>${matches.map((item) => `<button class="command-result" type="button" data-command-url="${item[3]}"><span>${item[0]}</span><span><strong>${item[1]}</strong><small>${item[2]}</small></span></button>`).join("") || `<div class="compact-item"><span class="compact-copy"><span>No matching destination</span></span></div>`}`;
}

function closeMobileNav() {
  document.getElementById("app-rail").classList.remove("open");
  document.getElementById("rail-overlay").classList.remove("open");
}

function bindGlobalEvents() {
  document.getElementById("mobile-menu").addEventListener("click", () => {
    document.getElementById("app-rail").classList.add("open");
    document.getElementById("rail-overlay").classList.add("open");
  });
  document.getElementById("rail-close").addEventListener("click", closeMobileNav);
  document.getElementById("rail-overlay").addEventListener("click", closeMobileNav);
  document.getElementById("global-search").addEventListener("click", openCommandPalette);
  commandBackdrop.addEventListener("click", closeCommandPalette);
  commandInput.addEventListener("input", () => renderCommandResults(commandInput.value));
  drawerBackdrop.addEventListener("click", closeDrawer);
  document.getElementById("drawer-close").addEventListener("click", closeDrawer);
  document.getElementById("theme-toggle").addEventListener("click", () => {
    state.theme = state.theme === "dark" ? "light" : "dark";
    localStorage.setItem("bp-theme", state.theme);
    applyPreferences();
  });
  document.getElementById("language-toggle").addEventListener("click", () => {
    state.language = state.language === "en" ? "ro" : "en";
    localStorage.setItem("bp-language", state.language);
    applyPreferences();
    renderCurrentPage();
  });
  document.querySelectorAll("[data-experience-value]").forEach((button) => button.addEventListener("click", () => {
    state.experience = button.dataset.experienceValue;
    localStorage.setItem("bp-experience", state.experience);
    applyPreferences();
  }));
  document.getElementById("notifications-button").addEventListener("click", openNotifications);
  document.getElementById("account-button").addEventListener("click", openAccount);
  document.getElementById("mode-banner-action").addEventListener("click", showProviderDetails);

  document.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      openCommandPalette();
    }
    if (event.key === "Escape") {
      closeCommandPalette();
      closeDrawer();
      closeMobileNav();
    }
  });

  document.addEventListener("click", (event) => {
 const target = event.target.closest("[data-command-url], [data-open-dataset], [data-open-asset], [data-add-idea], [data-promote-idea], [data-open-template], [data-open-trader], [data-preview-order], [data-social-method], [data-open-license], [data-connection-detail], [data-open-lesson], [data-open-account], [data-close-drawer], [data-retry-page], [data-data-filter]");
    if (!target) return;
    if (target.dataset.commandUrl) window.location.href = target.dataset.commandUrl;
    if (target.dataset.openDataset) openDataset(target.dataset.openDataset);
    if (target.dataset.openAsset) openAsset(target.dataset.openAsset);
    if (target.hasAttribute("data-add-idea")) openNewIdea();
    if (target.dataset.promoteIdea) promoteIdea(target.dataset.promoteIdea);
    if (target.dataset.openTemplate) openTemplate(target.dataset.openTemplate);
    if (target.dataset.openTrader) openTrader(target.dataset.openTrader);
    if (target.hasAttribute("data-preview-order")) openOrderPreview(target.dataset.asset || "BTC");
    if (target.hasAttribute("data-social-method")) openMethodology();
    if (target.hasAttribute("data-open-license")) openLicenseGuide();
    if (target.dataset.connectionDetail) openConnectionDetail(target.dataset.connectionDetail);
 if (target.dataset.openLesson) openLesson(target.dataset.openLesson);
 if (target.hasAttribute("data-open-account")) openAccount();
 if (target.hasAttribute("data-close-drawer")) closeDrawer();
    if (target.hasAttribute("data-retry-page")) renderCurrentPage(true);
    if (target.dataset.dataFilter) {
      state.dataFilter = target.dataset.dataFilter;
      root.innerHTML = renderData(state.dashboard);
    }
  });

  document.addEventListener("submit", async (event) => {
    if (event.target.id === "idea-form") {
      event.preventDefault();
      saveIdea(event.target);
    }
    if (event.target.id === "order-preview-form") {
      event.preventDefault();
      submitOrderPreview(event.target);
    }
    try {
      if (event.target.id === "platform-register-form") {
        event.preventDefault();
        await registerPlatformUser(event.target);
      }
      if (event.target.id === "platform-login-form") {
        event.preventDefault();
        await loginPlatformUser(event.target);
      }
      if (event.target.id === "platform-wallet-form") {
        event.preventDefault();
        await connectPlatformWallet(event.target);
      }
    } catch (error) {
      showToast(error.message || "Account action failed.");
    }
  });

  document.addEventListener("change", (event) => {
    if (event.target.matches("[data-setting-theme]")) {
      state.theme = event.target.checked ? "dark" : "light";
      localStorage.setItem("bp-theme", state.theme);
      applyPreferences();
    }
    if (event.target.matches("[data-setting-experience]")) {
      state.experience = event.target.checked ? "pro" : "simple";
      localStorage.setItem("bp-experience", state.experience);
      applyPreferences();
    }
    if (event.target.matches("[data-setting-language]")) {
      state.language = event.target.value;
      localStorage.setItem("bp-language", state.language);
      applyPreferences();
      renderCurrentPage();
    }
  });
}

applyPreferences();
syncActiveNav();
bindGlobalEvents();
renderCurrentPage();
