const DEFAULT_PREFERENCES = {
  theme: "day",
  language: "en",
  workspaceStyle: "institutional",
};
const STORAGE_KEYS = {
  theme: "bitprivat.theme",
  language: "bitprivat.language",
  workspaceStyle: "bitprivat.workspaceStyle",
};
const I18N = {
  en: {
    document_title: "BITprivat Command Center",
    app_title: "Market OS",
    app_subtitle: "Markets, bots, and strategy testing in one clear workflow.",
    nav_operate: "Operate",
    nav_overview: "Overview",
    nav_trading_workspace: "Trading Workspace",
    nav_social_traders: "Social Traders",
    nav_markets: "Markets",
    nav_paper_trade: "Paper Trade",
    nav_bots: "Bots",
    nav_build: "Build",
    nav_strategy_lab: "Strategy Lab",
    nav_connectors: "Connectors",
    nav_workspace: "Workspace",
    nav_account: "Account",
    nav_rules_alerts: "Rules & Alerts",
    nav_company: "Company",
    nav_public_status: "Public Status",
    nav_public_website: "Public Website",
    pref_theme: "Theme",
    pref_day: "Day",
    pref_night: "Night",
    pref_language: "Language",
    operator_active_view: "Active View",
    compact_dashboard_view: "Compact dashboard view",
    open_workspace_window: "Open workspace window",
    status_live: "Live",
    status_delayed_backup: "Delayed 15m backup",
    mode_simple: "Simple",
    simple_buy_sell_title: "Buy/Sell in 2 steps",
    simple_buy_sell_copy: "Choose the fiat amount, review impact, then confirm the order. Designed for newer users.",
    account_eyebrow: "Workspace access",
    account_title: "Start in demo mode or sign in for a personal workspace",
    preferences_title: "Preferences",
    preferences_subtitle: "Choose day/night mode and interface language. English is the default.",
    preferences_note: "Preferences are saved in this browser and applied immediately across the dashboard.",
    preferences_saved: "Preferences saved.",
    saved_locally: "Saved locally",
    workspace_eyebrow: "User workspace",
    workspace_title: "Follows, watchlist, rules, channels, and inbox state",
    focused_workspace: "Focused workspace",
    window_default_subtitle: "Section opened in a compact app window.",
    window_market_console: "Live market provider, bot decision queue, and risk posture.",
    window_trading_workspace: "Trading workspace without leaving the dashboard.",
    window_social_trader: "Creator-trader discovery, follow mode, and managed paper allocation.",
    window_trader_intelligence: "Expert-model research library, citations, comparison, and ask interface.",
    window_intelligence: "Markets, macro context, and signal intelligence in one focused view.",
    window_paper: "Paper positions, venues, and simulated execution controls.",
    window_leaderboard: "Bot scorecards, provenance, and alert posture.",
    window_connectors: "Provider readiness and connector diagnostics.",
    window_account: "Account, auth, billing, and onboarding controls.",
    window_workspace: "Watchlist, rules, alerts, and notification workspace.",
    close: "Close",
    opened_window_status: "{section} opened in a compact workspace window.",
  },
  ro: {
    document_title: "BITprivat Centru de Comanda",
    app_title: "Market OS",
    app_subtitle: "Piete, boti si testare de strategii intr-un flux clar.",
    nav_operate: "Operare",
    nav_overview: "Privire generala",
    nav_trading_workspace: "Spatiu de trading",
    nav_social_traders: "Traderi sociali",
    nav_markets: "Piete",
    nav_paper_trade: "Paper trading",
    nav_bots: "Boti",
    nav_build: "Construire",
    nav_strategy_lab: "Laborator strategii",
    nav_connectors: "Conectori",
    nav_workspace: "Spatiu lucru",
    nav_account: "Cont",
    nav_rules_alerts: "Reguli si alerte",
    nav_company: "Companie",
    nav_public_status: "Status public",
    nav_public_website: "Website public",
    pref_theme: "Tema",
    pref_day: "Zi",
    pref_night: "Noapte",
    pref_language: "Limba",
    operator_active_view: "Vedere activa",
    compact_dashboard_view: "Dashboard compact",
    open_workspace_window: "Fereastra workspace deschisa",
    status_live: "Live",
    status_delayed_backup: "Backup intarziat 15m",
    mode_simple: "Simplu",
    simple_buy_sell_title: "Cumpara/Vinde in 2 pasi",
    simple_buy_sell_copy: "Alege suma in fiat, verifica impactul, apoi confirma ordinul. Creat pentru utilizatori noi.",
    account_eyebrow: "Acces workspace",
    account_title: "Porneste in mod demo sau autentifica-te pentru un workspace personal",
    preferences_title: "Preferinte",
    preferences_subtitle: "Alege modul zi/noapte si limba interfetei. Engleza este implicita.",
    preferences_note: "Preferintele sunt salvate in acest browser si aplicate imediat in dashboard.",
    preferences_saved: "Preferinte salvate.",
    saved_locally: "Salvat local",
    workspace_eyebrow: "Workspace utilizator",
    workspace_title: "Urmari, watchlist, reguli, canale si inbox",
    focused_workspace: "Workspace focalizat",
    window_default_subtitle: "Sectiunea s-a deschis intr-o fereastra compacta.",
    window_market_console: "Provider live de piata, coada de decizii bot si postura de risc.",
    window_trading_workspace: "Spatiu de trading fara sa parasesti dashboardul.",
    window_social_trader: "Descoperire creatori-traderi, mod follow si alocare paper administrata.",
    window_trader_intelligence: "Biblioteca de modele expert, citari, comparatii si interfata de intrebari.",
    window_intelligence: "Piete, context macro si inteligenta de semnal intr-o vedere focalizata.",
    window_paper: "Pozitii paper, venue-uri si controale de executie simulata.",
    window_leaderboard: "Scorecard-uri boti, provenienta si postura alertelor.",
    window_connectors: "Pregatire provideri si diagnostice pentru conectori.",
    window_account: "Cont, autentificare, billing si controale de onboarding.",
    window_workspace: "Watchlist, reguli, alerte si workspace de notificari.",
    close: "Inchide",
    opened_window_status: "{section} s-a deschis intr-o fereastra compacta.",
  },
};
let appPreferences = { ...DEFAULT_PREFERENCES };

function currentLocale() {
  return appPreferences.language === "ro" ? "ro-RO" : "en-US";
}

function t(key, replacements = {}) {
  const dictionary = I18N[appPreferences.language] || I18N.en;
  const template = dictionary[key] || I18N.en[key] || key;
  return Object.entries(replacements).reduce(
    (value, [name, replacement]) => value.replaceAll(`{${name}}`, replacement),
    template,
  );
}

const finiteNumberOrNull = (value) => {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
};
const fmtPercent = (value, digits = 0) => {
  const numeric = finiteNumberOrNull(value);
  return numeric === null ? "--" : `${(numeric * 100).toFixed(digits)}%`;
};
const fmtScore = (value) => {
  const numeric = finiteNumberOrNull(value);
  return numeric === null ? "--" : numeric.toFixed(1);
};
const fmtPrice = (value) => {
  const numeric = finiteNumberOrNull(value);
  return numeric === null ? "--" : Intl.NumberFormat(currentLocale(), { maximumFractionDigits: numeric > 1000 ? 0 : 2 }).format(numeric);
};
const fmtUsd = (value, digits = 0) => Intl.NumberFormat(currentLocale(), {
  style: "currency",
  currency: "USD",
  notation: Math.abs(Number(value)) >= 1000000 ? "compact" : "standard",
  maximumFractionDigits: digits,
}).format(Number(value || 0));
const fmtCompactNumber = (value) => Intl.NumberFormat(currentLocale(), { notation: "compact", maximumFractionDigits: 1 }).format(Number(value || 0));
const fmtSignedPercent = (value) => {
  const numeric = finiteNumberOrNull(value);
  return numeric === null ? "--" : `${numeric >= 0 ? "+" : ""}${(numeric * 100).toFixed(1)}%`;
};
const fmtBps = (value) => {
  const numeric = finiteNumberOrNull(value);
  return numeric === null ? "--" : `${numeric >= 0 ? "+" : ""}${numeric.toFixed(0)} bps`;
};
const fmtDateTime = (value) => value ? new Date(value).toLocaleString(currentLocale(), { dateStyle: "medium", timeStyle: "short" }) : "n/a";
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (character) => ({
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
})[character]);
const fmtFileSize = (value) => {
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric <= 0) {
    return "0 B";
  }
  if (numeric < 1024) {
    return `${Math.round(numeric)} B`;
  }
  if (numeric < 1024 * 1024) {
    return `${(numeric / 1024).toFixed(1)} KB`;
  }
  return `${(numeric / (1024 * 1024)).toFixed(2)} MB`;
};
const AUTO_REFRESH_MS = 20000;
const RUN_CYCLE_STAGES = [
  "Pulling market context",
  "Hydrating signal input",
  "Ranking analyst bots",
  "Scoring archive windows",
  "Refreshing dashboard surface",
];

function fmtRelativeTime(value) {
  if (!value) {
    return "n/a";
  }
  const date = value instanceof Date ? value : new Date(value);
  const deltaSeconds = Math.max(0, Math.round((Date.now() - date.getTime()) / 1000));
  if (deltaSeconds < 5) {
    return "just now";
  }
  if (deltaSeconds < 60) {
    return `${deltaSeconds}s ago`;
  }
  const deltaMinutes = Math.round(deltaSeconds / 60);
  if (deltaMinutes < 60) {
    return `${deltaMinutes}m ago`;
  }
  const deltaHours = Math.round(deltaMinutes / 60);
  if (deltaHours < 24) {
    return `${deltaHours}h ago`;
  }
  const deltaDays = Math.round(deltaHours / 24);
  return `${deltaDays}d ago`;
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function qualityLabel(score) {
  const numeric = Number(score);
  if (numeric >= 0.82) {
    return "Institutional-grade";
  }
  if (numeric >= 0.72) {
    return "High-conviction";
  }
  if (numeric >= 0.62) {
    return "Monitor";
  }
  return "Low-conviction";
}

function qualityCardClass(score) {
  const numeric = Number(score);
  if (numeric >= 0.78) {
    return "tone-high";
  }
  if (numeric >= 0.62) {
    return "tone-mid";
  }
  return "tone-low";
}

function freshnessLabel(score) {
  const numeric = Number(score);
  if (numeric >= 0.82) {
    return "Near real-time";
  }
  if (numeric >= 0.68) {
    return "Current";
  }
  if (numeric >= 0.52) {
    return "Aging";
  }
  return "Stale";
}

function provenanceLabel(score) {
  const numeric = Number(score);
  if (numeric >= 0.82) {
    return "Evidence strong";
  }
  if (numeric >= 0.68) {
    return "Evidence good";
  }
  if (numeric >= 0.52) {
    return "Evidence mixed";
  }
  return "Evidence thin";
}

function humanizeKey(value) {
  return String(value || "")
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function sourceTypeLabel(value) {
  const labels = {
    "prediction-market": "Venue",
    social: "Social",
    news: "News",
    macro: "Macro",
    venue: "Venue",
  };
  return labels[value] || humanizeKey(value);
}

function sentimentLabel(value) {
  const numeric = Number(value);
  if (numeric >= 0.18) {
    return "Bullish lean";
  }
  if (numeric <= -0.18) {
    return "Bearish lean";
  }
  return "Balanced";
}

function readinessLevelLabel(level) {
  switch (level) {
    case "live":
      return "Live";
    case "ready":
      return "Ready";
    case "building":
      return "Building";
    default:
      return "Selected";
  }
}

function readinessLevelVariant(level) {
  switch (level) {
    case "live":
    case "ready":
      return "positive";
    case "building":
      return "warning";
    default:
      return "neutral";
  }
}

function providerState(providerStatus) {
  const healthy = providerStatus?.market_provider_ready
    && providerStatus?.signal_provider_ready
    && providerStatus?.macro_provider_ready
    && providerStatus?.wallet_provider_ready
    && providerStatus?.social_discovery_ready;
  const fallback = providerStatus?.market_fallback_active
    || providerStatus?.signal_fallback_active
    || providerStatus?.macro_fallback_active
    || providerStatus?.wallet_fallback_active
    || providerStatus?.social_discovery_fallback_active;
  if (fallback) {
    return { label: "Fallback active", variant: "warning" };
  }
  if (healthy) {
    return { label: "Nominal", variant: "positive" };
  }
  return { label: "Attention", variant: "warning" };
}

let selectedBotSlug = null;
let latestSnapshot = null;
let latestLandingSnapshot = null;
let lastDashboardRefreshAt = null;
let nextDashboardRefreshAt = null;
let autoRefreshEnabled = true;
let autoRefreshTimer = null;
let countdownTimer = null;
let dashboardLoadInFlight = false;
let socialTradingLoadInFlight = false;
let socialTradingRetryTimer = null;
let publicSocialReadOrigin = null;
let statusPageLoadInFlight = false;
let statusPageTimer = null;
let previousLeaderboardScores = new Map();
let runCycleStageTimer = null;
let chartInstances = new Map();
let assetHistoryCache = new Map();
let selectedLandingAsset = null;
let selectedDashboardAsset = null;
let selectedMacroSeries = null;
let chartResizeFrame = null;
let simulationConfig = null;
let latestSimulationResult = null;
let latestAdvancedExport = null;
let latestSocialExecution = null;
let socialMarketplaceState = {
  query: "",
  asset: "all",
  risk: "all",
  mode: "all",
  sort: "score",
};
let socialMarketplaceFilterTimer = null;
let selectedSocialTraderId = null;
let traderIntelligenceState = {
  profiles: [],
  workspace: null,
  selectedProfileId: null,
  selectedCompareIds: new Set(),
  activeTab: "library",
  profileTab: "overview",
  filters: {
    query: "",
    category: "all",
    status: "all",
    source: "all",
    confidence: "all",
    sort: "last_analyzed",
    insightQuery: "",
    insightType: "all",
    insightConfidence: "all",
  },
  comparison: null,
  askAnswers: new Map(),
};
let savedStrategies = [];
let savedBacktestRuns = [];
let sectionObserverInitialized = false;
const EDGE_TRANSIENT_STATUS_CODES = new Set([522, 523, 524, 530]);
let suppressDashboardWindowOpenUntil = 0;
let dashboardWindowState = {
  section: null,
  placeholder: null,
  lastFocus: null,
};
let currentOrderPreview = null;
let currentOrderRequest = null;

function workspaceEditable(snapshot = latestSnapshot) {
  return Boolean(snapshot?.auth_session?.authenticated) && !snapshot?.user_profile?.is_demo_user;
}

function disabledAttr(disabled) {
  return disabled ? 'disabled aria-disabled="true"' : "";
}

function requireEditable() {
  if (workspaceEditable()) {
    return true;
  }
  setStatus("Sign in to modify your personal workspace. Demo mode is read-only.");
  return false;
}

function applyWorkspaceMode(snapshot = latestSnapshot) {
  const canEdit = workspaceEditable(snapshot);
  const workspaceNote = document.getElementById("workspace-mode-note");
  const forms = [
    "watchlist-form",
    "alert-rule-form",
    "notification-channel-form",
    "wallet-connect-form",
    "trader-intelligence-form",
    "trader-intelligence-ask-form",
  ];

  if (workspaceNote) {
    if (canEdit) {
      workspaceNote.textContent = `Signed in as ${snapshot?.user_profile?.display_name || "workspace user"}. Personal workspace changes are enabled.`;
      workspaceNote.classList.remove("notice-warning");
      workspaceNote.classList.add("notice-soft");
    } else {
      workspaceNote.textContent = "Demo workspace is read-only. Sign in or create an account to save follows, watchlist items, channels, and alert actions.";
      workspaceNote.classList.remove("notice-soft");
      workspaceNote.classList.add("notice-warning");
    }
  }

  forms.forEach((formId) => {
    const form = document.getElementById(formId);
    if (!form) {
      return;
    }
    form.querySelectorAll("input, select, button").forEach((field) => {
      field.disabled = !canEdit;
    });
  });

  const markAllButton = document.getElementById("mark-all-alerts-button");
  if (markAllButton) {
    markAllButton.disabled = !canEdit;
  }
}

async function fetchJson(path, options = {}) {
  const requestOptions = {
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  };
  let response = null;

  try {
    response = await fetch(path, requestOptions);
  } catch (error) {
    response = await fetchJsonThroughLiveOrigin(path, requestOptions, error);
    if (!response) {
      throw error;
    }
  }

  if (!response.ok && shouldRetryViaLiveOrigin(path, response.status)) {
    const directResponse = await fetchJsonThroughLiveOrigin(path, requestOptions);
    if (directResponse) {
      response = directResponse;
    }
  }

  if (!response.ok) {
    let message = `Failed to load ${path}`;
    try {
      const payload = await response.json();
      if (payload?.detail) {
        message = payload.detail;
      }
    } catch (error) {
      console.error(error);
    }
    throw new Error(message);
  }

  if (response.status === 204) {
    return null;
  }
  return response.json();
}

function isRelativeApiPath(path) {
  return typeof path === "string" && path.startsWith("/api/");
}

function shouldRetryViaLiveOrigin(path, statusCode) {
  return isRelativeApiPath(path)
    && !path.startsWith("/api/runtime/")
    && EDGE_TRANSIENT_STATUS_CODES.has(Number(statusCode));
}

async function fetchJsonThroughLiveOrigin(path, options = {}, sourceError = null) {
  if (!isRelativeApiPath(path) || path.startsWith("/api/runtime/")) {
    return null;
  }
  const liveOrigin = await resolvePublicSocialReadOrigin();
  if (!liveOrigin) {
    return null;
  }
  const directUrl = `${liveOrigin}${path}`;
  try {
    return await fetch(directUrl, {
      ...options,
      credentials: "omit",
    });
  } catch (error) {
    console.warn("Direct live-origin retry failed.", {
      path,
      liveOrigin,
      sourceError: sourceError?.message || sourceError?.name || null,
      retryError: error?.message || error?.name || null,
    });
    return null;
  }
}

function setStatus(message) {
  const status = document.getElementById("cycle-status");
  if (status) {
    status.textContent = message;
  }
}

function loadPreferences() {
  try {
    const storedTheme = window.localStorage.getItem(STORAGE_KEYS.theme);
    const storedLanguage = window.localStorage.getItem(STORAGE_KEYS.language);
    const storedWorkspaceStyle = window.localStorage.getItem(STORAGE_KEYS.workspaceStyle);
    appPreferences = {
      theme: ["day", "night"].includes(storedTheme) ? storedTheme : DEFAULT_PREFERENCES.theme,
      language: ["en", "ro"].includes(storedLanguage) ? storedLanguage : DEFAULT_PREFERENCES.language,
      workspaceStyle: ["trader", "institutional"].includes(storedWorkspaceStyle)
        ? storedWorkspaceStyle
        : DEFAULT_PREFERENCES.workspaceStyle,
    };
  } catch (error) {
    console.warn("Preferences unavailable; using defaults.", error);
    appPreferences = { ...DEFAULT_PREFERENCES };
  }
}

function savePreferences() {
  try {
    window.localStorage.setItem(STORAGE_KEYS.theme, appPreferences.theme);
    window.localStorage.setItem(STORAGE_KEYS.language, appPreferences.language);
    window.localStorage.setItem(STORAGE_KEYS.workspaceStyle, appPreferences.workspaceStyle);
  } catch (error) {
    console.warn("Could not persist preferences.", error);
  }
}

function syncPreferenceControls() {
  document.querySelectorAll("[data-preference-theme]").forEach((select) => {
    select.value = appPreferences.theme;
  });
  document.querySelectorAll("[data-preference-language]").forEach((select) => {
    select.value = appPreferences.language;
  });
  document.querySelectorAll("[data-workspace-style]").forEach((button) => {
    const style = button.getAttribute("data-workspace-style");
    const active = style === appPreferences.workspaceStyle;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
}

function applyPreferences({ announce = false } = {}) {
  const body = document.body;
  if (!body) {
    return;
  }

  body.dataset.theme = appPreferences.theme;
  body.dataset.language = appPreferences.language;
  body.dataset.workspaceStyle = appPreferences.workspaceStyle;
  document.documentElement.lang = appPreferences.language === "ro" ? "ro" : "en";
  document.title = t("document_title");

  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = t(node.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((node) => {
    node.setAttribute("placeholder", t(node.dataset.i18nPlaceholder));
  });
  document.querySelectorAll("[data-i18n-aria]").forEach((node) => {
    node.setAttribute("aria-label", t(node.dataset.i18nAria));
  });

  syncPreferenceControls();
  setActiveDashboardSection(window.location.hash || "#market-console-section");
  if (!document.getElementById("dashboard-window")?.classList.contains("hidden")) {
    const openSection = dashboardWindowState.section?.id ? `#${dashboardWindowState.section.id}` : null;
    const title = document.getElementById("dashboard-window-title");
    const subtitle = document.getElementById("dashboard-window-subtitle");
    if (title && openSection) {
      title.textContent = sectionTitleFromHash(openSection);
    }
    if (subtitle && openSection) {
      subtitle.textContent = dashboardWindowSubtitle(openSection);
    }
  }
  if (announce) {
    setStatus(t("preferences_saved"));
  }
}

function bindPreferenceControls() {
  document.querySelectorAll("[data-preference-theme]").forEach((select) => {
    select.addEventListener("change", () => {
      appPreferences.theme = select.value === "night" ? "night" : "day";
      savePreferences();
      applyPreferences({ announce: true });
      resizeVisibleCharts();
    });
  });
  document.querySelectorAll("[data-preference-language]").forEach((select) => {
    select.addEventListener("change", () => {
      appPreferences.language = select.value === "ro" ? "ro" : "en";
      savePreferences();
      applyPreferences({ announce: true });
      resizeVisibleCharts();
    });
  });
  document.querySelectorAll("[data-workspace-style]").forEach((button) => {
    button.addEventListener("click", () => {
      const requestedStyle = button.getAttribute("data-workspace-style");
      appPreferences.workspaceStyle = requestedStyle === "trader" ? "trader" : "institutional";
      savePreferences();
      applyPreferences({ announce: true });
      setStatus(
        appPreferences.workspaceStyle === "trader"
          ? "Trader mode enabled: denser terminal layout."
          : "Institutional mode enabled: cleaner premium layout.",
      );
      resizeVisibleCharts();
    });
  });
}

function applyBillingQueryStatus() {
  const params = new URLSearchParams(window.location.search);
  const billingState = params.get("billing");
  if (billingState === "success") {
    setStatus("Billing returned from Stripe successfully. Refreshing workspace entitlements.");
  } else if (billingState === "cancelled") {
    setStatus("Stripe checkout was cancelled. Your workspace remains unchanged.");
  }
}

function setLiveBadge(label, variant = "neutral") {
  const badge = document.getElementById("live-badge");
  if (!badge) {
    return;
  }
  badge.textContent = label;
  badge.dataset.variant = variant;
}

function sectionTitleFromHash(hash) {
  if (!hash) {
    return "Overview";
  }
  const navLink = document.querySelector(`.sidebar-nav a[href="${hash}"]`);
  return navLink?.textContent?.trim() || humanizeKey(hash.replace("#", "").replace("-section", ""));
}

function isDashboardWorkspaceHash(hash) {
  if (!hash || !hash.startsWith("#")) {
    return false;
  }
  try {
    const section = document.querySelector(hash);
    const hasWorkspaceLink = [...document.querySelectorAll(".sidebar-nav a[href^='#']")]
      .some((link) => link.getAttribute("href") === hash);
    return Boolean(section && hasWorkspaceLink);
  } catch {
    return false;
  }
}

function dashboardWindowNavIcon(hash) {
  const icons = {
    "#market-console-section": "01",
    "#trading-workspace-section": "02",
    "#social-trader-section": "03",
    "#trader-intelligence-section": "04",
    "#intelligence-section": "05",
    "#paper-section": "06",
    "#leaderboard-section": "07",
    "#connectors-section": "08",
    "#account-section": "09",
    "#workspace-section": "10",
  };
  return icons[hash] || ">";
}

function syncDashboardWindowNav(activeHash = "#market-console-section") {
  const nav = document.getElementById("dashboard-window-nav");
  if (!nav) {
    return;
  }
  const links = [...document.querySelectorAll(".sidebar-nav a[href^='#']")]
    .filter((link) => isDashboardWorkspaceHash(link.getAttribute("href")));
  nav.innerHTML = links.map((link) => {
    const hash = link.getAttribute("href");
    const active = hash === activeHash;
    return `
      <a href="${escapeHtml(hash)}" class="${active ? "active" : ""}" ${active ? 'aria-current="page"' : ""}>
        <span>${escapeHtml(dashboardWindowNavIcon(hash))}</span>
        ${escapeHtml(link.textContent?.trim() || sectionTitleFromHash(hash))}
      </a>
    `;
  }).join("");
}

function setActiveDashboardSection(hash) {
  const activeHash = hash || "#market-console-section";
  document.querySelectorAll(".sidebar-nav a[href^='#']").forEach((link) => {
    link.classList.toggle("active", link.getAttribute("href") === activeHash);
  });
  syncDashboardWindowNav(activeHash);

  const activeSection = document.getElementById("operator-active-section");
  const activeDetail = document.getElementById("operator-active-section-detail");
  if (activeSection) {
    activeSection.textContent = sectionTitleFromHash(activeHash);
  }
  if (activeDetail) {
    activeDetail.textContent = document.body.classList.contains("dashboard-window-open")
      ? t("open_workspace_window")
      : t("compact_dashboard_view");
  }
}

function initDashboardSectionObserver() {
  if (sectionObserverInitialized || !document.getElementById("operator-strip")) {
    return;
  }
  sectionObserverInitialized = true;
  const links = [...document.querySelectorAll(".sidebar-nav a[href^='#']")];
  const targets = links
    .map((link) => document.querySelector(link.getAttribute("href")))
    .filter(Boolean);
  if (!targets.length) {
    return;
  }

  if (!("IntersectionObserver" in window)) {
    setActiveDashboardSection(links[0].getAttribute("href"));
    return;
  }

  const observer = new IntersectionObserver((entries) => {
    const visible = entries
      .filter((entry) => entry.isIntersecting)
      .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
    if (visible?.target?.id) {
      setActiveDashboardSection(`#${visible.target.id}`);
    }
  }, {
    rootMargin: "-18% 0px -62% 0px",
    threshold: [0.1, 0.35, 0.6],
  });

  targets.forEach((target) => observer.observe(target));
  setActiveDashboardSection(window.location.hash || links[0].getAttribute("href"));
}

function dashboardWindowSubtitle(hash) {
  const subtitles = {
    "#market-console-section": "window_market_console",
    "#trading-workspace-section": "window_trading_workspace",
    "#social-trader-section": "window_social_trader",
    "#trader-intelligence-section": "window_trader_intelligence",
    "#intelligence-section": "window_intelligence",
    "#paper-section": "window_paper",
    "#leaderboard-section": "window_leaderboard",
    "#connectors-section": "window_connectors",
    "#account-section": "window_account",
    "#workspace-section": "window_workspace",
  };
  return t(subtitles[hash] || "window_default_subtitle");
}

function closeDashboardWindow({ restoreFocus = true, suppressReopen = true, updateHistory = true } = {}) {
  suppressDashboardWindowOpenUntil = suppressReopen ? Date.now() + 2000 : 0;
  const overlay = document.getElementById("dashboard-window");
  const body = document.getElementById("dashboard-window-body");
  const { section, placeholder, lastFocus } = dashboardWindowState;

  if (overlay) {
    overlay.classList.add("hidden");
    delete overlay.dataset.windowKind;
  }
  document.body.classList.remove("dashboard-window-open", "dashboard-window-social-open");

  try {
    section?.querySelector(".dashboard-window-inline-close")?.remove();
    if (section && placeholder?.parentNode) {
      section.classList.remove("in-dashboard-window");
      placeholder.replaceWith(section);
    } else if (section) {
      section.classList.remove("in-dashboard-window");
    }
  } catch (error) {
    console.warn("Could not restore dashboard section from workspace window.", error);
    section.classList.remove("in-dashboard-window");
  }

  if (body && (!section || !body.contains(section))) {
    body.innerHTML = "";
  }
  dashboardWindowState = { section: null, placeholder: null, lastFocus: null };
  if (restoreFocus && lastFocus instanceof HTMLElement) {
    lastFocus.focus({ preventScroll: true });
  }
  if (updateHistory && isDashboardWorkspaceHash(window.location.hash)) {
    window.history.replaceState(null, document.title, `${window.location.pathname}${window.location.search}`);
  }
  resizeVisibleCharts();
}

function closeDashboardWindowFromHash() {
  if (window.location.hash !== "#close-dashboard-window") {
    return false;
  }
  closeDashboardWindow();
  window.history.replaceState(null, document.title, `${window.location.pathname}${window.location.search}`);
  return true;
}

function openDashboardWindowFromHash() {
  if (!document.body.classList.contains("dashboard-body")) {
    return false;
  }
  if (closeDashboardWindowFromHash()) {
    return true;
  }
  const hash = window.location.hash;
  if (!isDashboardWorkspaceHash(hash)) {
    return false;
  }
  const trigger = document.querySelector(`.sidebar-nav a[href="${hash}"]`);
  return openDashboardWindow(hash, trigger, { ignoreSuppression: true });
}

function handleDashboardHashChange() {
  if (openDashboardWindowFromHash()) {
    return;
  }
  setActiveDashboardSection(window.location.hash || "#market-console-section");
}

function openDashboardWindow(hash, trigger = null, { ignoreSuppression = false } = {}) {
  if (!ignoreSuppression && Date.now() < suppressDashboardWindowOpenUntil) {
    return true;
  }
  if (!isDashboardWorkspaceHash(hash)) {
    return false;
  }
  const section = document.querySelector(hash);
  const overlay = document.getElementById("dashboard-window");
  const body = document.getElementById("dashboard-window-body");
  const title = document.getElementById("dashboard-window-title");
  const subtitle = document.getElementById("dashboard-window-subtitle");
  if (!section || !overlay || !body) {
    return false;
  }

  closeDashboardWindow({ restoreFocus: false, suppressReopen: false, updateHistory: false });
  const placeholder = document.createElement("div");
  placeholder.className = "dashboard-window-placeholder";
  placeholder.hidden = true;
  body.querySelector(".dashboard-window-inline-close")?.remove();
  const inlineClose = document.createElement("form");
  inlineClose.className = "dashboard-window-inline-close";
  inlineClose.addEventListener("submit", (event) => {
    event.preventDefault();
    closeDashboardWindow();
  });
  const inlineCloseButton = document.createElement("button");
  inlineCloseButton.className = "button ghost small-button";
  inlineCloseButton.type = "submit";
  inlineCloseButton.dataset.i18n = "close";
  inlineCloseButton.textContent = t("close");
  inlineClose.appendChild(inlineCloseButton);
  section.before(placeholder);
  section.classList.add("in-dashboard-window");
  body.appendChild(section);
  section.prepend(inlineClose);
  const windowKind = hash === "#social-trader-section"
    ? "social"
    : hash === "#trading-workspace-section"
      ? "trading"
      : hash === "#trader-intelligence-section"
        ? "intelligence"
        : "standard";
  overlay.dataset.windowKind = windowKind;
  overlay.classList.remove("hidden");
  suppressDashboardWindowOpenUntil = 0;
  document.body.classList.add("dashboard-window-open");
  document.body.classList.toggle("dashboard-window-social-open", windowKind === "social");
  dashboardWindowState = { section, placeholder, lastFocus: trigger };

  if (title) {
    title.textContent = sectionTitleFromHash(hash);
  }
  if (subtitle) {
    subtitle.textContent = dashboardWindowSubtitle(hash);
  }
  if (window.location.hash !== hash) {
    window.history.replaceState(null, document.title, `${window.location.pathname}${window.location.search}${hash}`);
  }
  overlay.querySelectorAll("[data-action='dashboard-window-close']").forEach((button) => {
    const closeFromControl = (event) => {
      event.preventDefault();
      closeDashboardWindow();
    };
    button.onclick = closeFromControl;
    button.onpointerdown = closeFromControl;
    button.onkeydown = (event) => {
      if (event.key === "Enter" || event.key === " ") {
        closeFromControl(event);
      }
    };
  });
  setActiveDashboardSection(hash);
  setStatus(t("opened_window_status", { section: sectionTitleFromHash(hash) }));

  const closeButton = overlay.querySelector("[data-action='dashboard-window-close']");
  if (closeButton instanceof HTMLElement) {
    closeButton.focus({ preventScroll: true });
  }
  resizeVisibleCharts();
  return true;
}

window.closeDashboardWindow = closeDashboardWindow;
window.openDashboardWindow = openDashboardWindow;

function renderOperatorStrip(snapshot) {
  const strip = document.getElementById("operator-strip");
  if (!strip || !snapshot) {
    return;
  }

  const stateLabel = document.getElementById("operator-state-label");
  const stateDetail = document.getElementById("operator-state-detail");
  const stateDot = document.getElementById("operator-state-dot");
  const topBot = document.getElementById("operator-top-bot");
  const topBotDetail = document.getElementById("operator-top-bot-detail");
  const paperEquity = document.getElementById("operator-paper-equity");
  const paperDetail = document.getElementById("operator-paper-detail");
  const socialTraders = document.getElementById("operator-social-traders");
  const socialDetail = document.getElementById("operator-social-detail");
  const providerCount = document.getElementById("operator-provider-count");
  const providerDetail = document.getElementById("operator-provider-detail");
  const briefStatus = document.getElementById("command-brief-status");
  const briefDetail = document.getElementById("command-brief-detail");

  const provider = snapshot.provider_status || {};
  const state = providerState(provider);
  const leader = snapshot.leaderboard?.[0];
  const paperSummary = snapshot.paper_trading?.summary || {};
  const socialTrading = snapshot.social_trading || {};
  const readyConnectors = snapshot.connector_control?.live_or_ready_count ?? 0;
  const connectorTotal = snapshot.connector_control?.connectors?.length ?? 0;
  const latestOperation = snapshot.latest_operation;

  if (stateLabel) {
    stateLabel.textContent = state.label;
  }
  if (stateDetail) {
    stateDetail.textContent = `${snapshot.summary.pending_predictions} pending calls · ${snapshot.system_pulse?.total_recent_signals ?? 0} recent signals · cycle ${latestOperation ? fmtRelativeTime(latestOperation.completed_at || latestOperation.started_at) : "idle"}`;
  }
  if (stateDot) {
    stateDot.dataset.variant = state.variant;
  }
  if (topBot) {
    topBot.textContent = leader?.name || "Waiting";
  }
  if (topBotDetail) {
    topBotDetail.textContent = leader
      ? `${fmtScore(leader.composite_score)} score · ${fmtPercent(leader.hit_rate)} hit rate`
      : "No ranked bot yet";
  }
  if (paperEquity) {
    paperEquity.textContent = fmtUsd(paperSummary.equity || 0);
  }
  if (paperDetail) {
    paperDetail.textContent = `${fmtSignedPercent(paperSummary.total_return || 0)} total · ${paperSummary.open_positions || 0} open`;
  }
  if (socialTraders) {
    socialTraders.textContent = `${socialTrading.top_traders?.length || 0}`;
  }
  if (socialDetail) {
    const allocationCount = socialTrading.allocations?.length || 0;
    socialDetail.textContent = `${allocationCount} followed · ${socialTrading.youtube_configured ? "YouTube live" : "demo watchlist"}`;
  }
  if (providerCount) {
    providerCount.textContent = `${readyConnectors}/${connectorTotal}`;
  }
  if (providerDetail) {
    providerDetail.textContent = `${snapshot.system_pulse?.live_provider_count ?? 0} live-capable · ${state.label}`;
  }
  if (briefStatus) {
    briefStatus.textContent = state.label;
  }
  if (briefDetail) {
    briefDetail.textContent = stateDetail?.textContent || "Preparing dashboard data";
  }
}

function renderHeroMeta(snapshot) {
  const heroSubmeta = document.getElementById("hero-submeta");
  if (!heroSubmeta) {
    return;
  }
  const latestOperation = snapshot.latest_operation;
  const latestSignal = snapshot.recent_signals?.[0];
  const pulse = snapshot.system_pulse;
  heroSubmeta.textContent = `${snapshot.provider_status.environment_name} environment · ${pulse?.live_provider_count ?? 0} live-capable providers · ${snapshot.paper_venues?.ready_venues ?? 0} paper venues ready · ${snapshot.wallet_intelligence?.wallets?.length || 0} smart wallets · ${snapshot.edge_snapshot?.opportunities?.length || 0} active edge surfaces · latest signal ${latestSignal?.asset || "n/a"} ${latestSignal ? fmtRelativeTime(latestSignal.observed_at) : ""} · last cycle ${latestOperation ? fmtRelativeTime(latestOperation.completed_at || latestOperation.started_at) : "not run yet"}.`;
}

function renderRibbon(snapshot) {
  const lastValue = document.getElementById("refresh-last-value");
  const lastSubtitle = document.getElementById("refresh-last-subtitle");
  const nextValue = document.getElementById("refresh-next-value");
  const nextSubtitle = document.getElementById("refresh-next-subtitle");
  const pressureValue = document.getElementById("pipeline-pressure-value");
  const pressureSubtitle = document.getElementById("pipeline-pressure-subtitle");
  const providerValue = document.getElementById("provider-posture-value");
  const providerSubtitle = document.getElementById("provider-posture-subtitle");
  const activityBadge = document.getElementById("activity-stream-badge");

  if (lastValue) {
    lastValue.textContent = lastDashboardRefreshAt ? fmtRelativeTime(lastDashboardRefreshAt) : "Waiting";
  }
  if (lastSubtitle) {
    lastSubtitle.textContent = lastDashboardRefreshAt ? fmtDateTime(lastDashboardRefreshAt) : "Dashboard has not been hydrated yet";
  }
  if (nextValue) {
    nextValue.textContent = autoRefreshEnabled ? "Queued" : "Paused";
  }
  if (nextSubtitle) {
    nextSubtitle.textContent = autoRefreshEnabled ? "Next pull scheduled automatically" : "Manual refresh mode enabled";
  }

  if (pressureValue) {
    pressureValue.textContent = `${snapshot.summary.pending_predictions} pending`;
  }
  if (pressureSubtitle) {
    pressureSubtitle.textContent = `${snapshot.system_pulse?.total_recent_signals ?? snapshot.summary.signals_last_24h} recent signals · ${snapshot.notification_health.retry_queue_depth} notification retries waiting`;
  }

  const providersHealthy = snapshot.provider_status.market_provider_ready
    && snapshot.provider_status.signal_provider_ready
    && snapshot.provider_status.macro_provider_ready
    && snapshot.provider_status.wallet_provider_ready
    && snapshot.provider_status.social_discovery_ready;
  const fallbackActive = snapshot.provider_status.market_fallback_active
    || snapshot.provider_status.signal_fallback_active
    || snapshot.provider_status.macro_fallback_active
    || snapshot.provider_status.wallet_fallback_active
    || snapshot.provider_status.social_discovery_fallback_active;
  if (providerValue) {
    providerValue.textContent = fallbackActive ? "Fallback active" : (providersHealthy ? "Primary providers stable" : "Needs attention");
  }
  if (providerSubtitle) {
    providerSubtitle.textContent = `${snapshot.system_pulse?.live_provider_count ?? 0} live-capable | ${snapshot.provider_status.market_provider_source} + ${snapshot.provider_status.signal_provider_source} + ${snapshot.provider_status.macro_provider_source} + ${snapshot.provider_status.wallet_provider_source} + ${snapshot.provider_status.social_discovery_provider_source}`;
  }
  if (activityBadge) {
    activityBadge.textContent = autoRefreshEnabled ? `Auto-refresh ${AUTO_REFRESH_MS / 1000}s` : "Manual refresh";
  }

  if (fallbackActive) {
    setLiveBadge("Fallback Active", "warning");
  } else if (providersHealthy) {
    setLiveBadge("Monitoring", "positive");
  } else {
    setLiveBadge("Needs Attention", "warning");
  }
}

function renderLaunchReadiness(launchReadiness) {
  const badge = document.getElementById("launch-readiness-badge");
  const summary = document.getElementById("launch-readiness-summary");
  const grid = document.getElementById("launch-readiness-grid");
  if (!badge || !summary || !grid || !launchReadiness) {
    return;
  }

  badge.textContent = readinessLevelLabel(launchReadiness.level);
  badge.dataset.variant = readinessLevelVariant(launchReadiness.level);
  summary.textContent = launchReadiness.summary;
  grid.innerHTML = (launchReadiness.tracks || []).map((track) => {
    const nextActions = (track.next_actions || []).map((item) => `<li>${item}</li>`).join("");
    const blockers = (track.blockers || []).length
      ? track.blockers.map((item) => `<li>${item}</li>`).join("")
      : "<li>No critical blockers recorded right now.</li>";
    return `
      <article class="launch-track-card launch-${track.level}">
        <div class="launch-track-head">
          <div>
            <p class="eyebrow">${track.label}</p>
            <h4>${track.headline}</h4>
          </div>
          <span class="status-pill" data-variant="${readinessLevelVariant(track.level)}">${readinessLevelLabel(track.level)}</span>
        </div>
        <p class="launch-track-summary">${track.summary}</p>
        <div class="launch-track-meta">
          <span><strong>Provider:</strong> ${track.recommended_provider}</span>
          <span><strong>Target:</strong> ${track.target_release}</span>
        </div>
        <div class="launch-track-columns">
          <div>
            <strong>Next actions</strong>
            <ul class="launch-track-list">${nextActions}</ul>
          </div>
          <div>
            <strong>Blockers</strong>
            <ul class="launch-track-list">${blockers}</ul>
          </div>
        </div>
      </article>
    `;
  }).join("");
}

function connectorStateLabel(state) {
  switch (state) {
    case "live":
      return "Live";
    case "ready":
      return "Ready";
    case "attention":
      return "Attention";
    case "planned":
      return "Planned";
    default:
      return "Demo";
  }
}

function connectorStateVariant(state) {
  switch (state) {
    case "live":
    case "ready":
      return "positive";
    case "attention":
      return "warning";
    default:
      return "neutral";
  }
}

function connectorDiagnosticVariant(status) {
  switch (status) {
    case "pass":
      return "positive";
    case "warn":
    case "fail":
    case "blocked":
      return "warning";
    default:
      return "neutral";
  }
}

function connectorDiagnosticLabel(status) {
  switch (status) {
    case "pass":
      return "Pass";
    case "warn":
      return "Review";
    case "fail":
    case "blocked":
      return "Blocked";
    default:
      return "Waiting";
  }
}

function renderConnectorControl(connectorControl) {
  const summary = document.getElementById("connector-summary");
  const badge = document.getElementById("connector-live-count");
  const grid = document.getElementById("connector-grid");
  if (!summary || !badge || !grid || !connectorControl) {
    return;
  }

  summary.textContent = connectorControl.summary;
  badge.textContent = `${connectorControl.live_or_ready_count}/${(connectorControl.connectors || []).length} ready`;
  badge.dataset.variant = connectorControl.live_or_ready_count >= 4 ? "positive" : "warning";

  grid.innerHTML = (connectorControl.connectors || []).map((connector) => {
    const readinessPercent = Math.round((connector.readiness_score || 0) * 100);
    const envKeys = (connector.env_keys || []).length
      ? connector.env_keys.map((envKey) => `<span>${envKey}</span>`).join("")
      : "<span>No extra secrets listed</span>";
    const nextActions = (connector.next_actions || [])
      .slice(0, 2)
      .map((item) => `<li>${item}</li>`)
      .join("");
    const actionLink = connector.app_url
      ? `<a class="text-link" href="${connector.app_url}" target="${connector.app_url.startsWith("/") ? "_self" : "_blank"}" rel="noreferrer">Open surface</a>`
      : "";
    return `
      <article class="connector-card connector-${connector.state}">
        <div class="connector-head">
          <div>
            <p class="eyebrow">${connector.category}</p>
            <h4>${connector.label}</h4>
          </div>
          <span class="status-pill" data-variant="${connectorStateVariant(connector.state)}">${connectorStateLabel(connector.state)}</span>
        </div>
        <p class="connector-summary">${connector.summary}</p>
        <div class="connector-readiness-row">
          <span>${connector.activation_phase || "Activation"} readiness</span>
          <strong>${readinessPercent}%</strong>
        </div>
        <div class="connector-progress-rail" aria-hidden="true">
          <span style="width: ${readinessPercent}%"></span>
        </div>
        <div class="connector-meta">
          <span><strong>Mode:</strong> ${connector.mode}</span>
          <span><strong>Source:</strong> ${connector.source}</span>
          <span><strong>Target:</strong> ${connector.target_surface}</span>
          <span><strong>Owner:</strong> ${connector.owner || "Platform"}</span>
          <span><strong>Risk:</strong> ${connector.risk_level || "medium"}</span>
        </div>
        <div class="connector-key-row">${envKeys}</div>
        <div class="connector-actions">
          ${actionLink}
          <button class="button tertiary small-button" type="button" data-action="run-connector-check" data-connector-id="${escapeHtml(connector.id)}">Run check</button>
          <span>${connector.live_capable ? "Live-capable" : "Demo-safe"}</span>
          <span>${connector.configured ? "Configured" : "Needs config"}</span>
        </div>
        <ul class="launch-track-list">${nextActions || "<li>No follow-up steps recorded.</li>"}</ul>
      </article>
    `;
  }).join("");
}

async function runConnectorDiagnostic(connectorId, button = null) {
  if (!connectorId) {
    return;
  }
  if (button) {
    button.disabled = true;
  }
  setStatus(`Running activation check for ${connectorId}...`);
  try {
    const payload = await fetchJson(`/api/system/connectors/${encodeURIComponent(connectorId)}/diagnostics`);
    renderConnectorDiagnostic(payload.connector_diagnostic);
    const status = connectorDiagnosticLabel(payload.connector_diagnostic?.overall_status);
    setStatus(`${payload.connector_diagnostic?.label || connectorId} check finished: ${status}.`);
  } finally {
    if (button) {
      button.disabled = false;
    }
  }
}

function renderConnectorDiagnostic(diagnostic) {
  const panel = document.getElementById("connector-diagnostic-panel");
  const title = document.getElementById("connector-diagnostic-title");
  const badge = document.getElementById("connector-diagnostic-badge");
  const summary = document.getElementById("connector-diagnostic-summary");
  const grid = document.getElementById("connector-diagnostic-grid");
  const actions = document.getElementById("connector-diagnostic-actions");
  if (!panel || !title || !badge || !summary || !grid || !actions || !diagnostic) {
    return;
  }

  panel.hidden = false;
  title.textContent = `${diagnostic.label} activation check`;
  badge.textContent = connectorDiagnosticLabel(diagnostic.overall_status);
  badge.dataset.variant = connectorDiagnosticVariant(diagnostic.overall_status);

  if (diagnostic.ready_to_activate && diagnostic.safe_to_promote) {
    summary.textContent = "This connector is ready and safe to promote with the current runtime settings.";
  } else if (diagnostic.blockers?.length) {
    summary.textContent = `${diagnostic.blockers.length} blocker${diagnostic.blockers.length === 1 ? "" : "s"} must be cleared before activation.`;
  } else {
    summary.textContent = "No hard blockers were found, but review warnings before promotion.";
  }

  grid.innerHTML = (diagnostic.checks || []).map((check) => `
    <article class="connector-diagnostic-card diagnostic-${escapeHtml(check.status)}">
      <div class="connector-head">
        <div>
          <p class="eyebrow">${check.required ? "Required" : "Advisory"}</p>
          <h4>${escapeHtml(check.label)}</h4>
        </div>
        <span class="status-pill" data-variant="${connectorDiagnosticVariant(check.status)}">${connectorDiagnosticLabel(check.status)}</span>
      </div>
      <p>${escapeHtml(check.detail)}</p>
    </article>
  `).join("");

  actions.innerHTML = (diagnostic.next_actions || [])
    .slice(0, 5)
    .map((action) => `<li>${escapeHtml(action)}</li>`)
    .join("");

  panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function runAllConnectorDiagnostics(button = null) {
  if (button) {
    button.disabled = true;
  }
  setStatus("Running activation checks across all connectors...");
  try {
    const payload = await fetchJson("/api/system/connectors/diagnostics");
    renderConnectorDiagnostics(payload.connector_diagnostics || []);
    const blockedCount = (payload.connector_diagnostics || []).filter((item) => item.blockers?.length).length;
    setStatus(`Connector sweep finished. ${blockedCount} connector${blockedCount === 1 ? "" : "s"} still blocked.`);
  } finally {
    if (button) {
      button.disabled = false;
    }
  }
}

function renderConnectorDiagnostics(diagnostics) {
  const panel = document.getElementById("connector-diagnostic-panel");
  const title = document.getElementById("connector-diagnostic-title");
  const badge = document.getElementById("connector-diagnostic-badge");
  const summary = document.getElementById("connector-diagnostic-summary");
  const grid = document.getElementById("connector-diagnostic-grid");
  const actions = document.getElementById("connector-diagnostic-actions");
  if (!panel || !title || !badge || !summary || !grid || !actions) {
    return;
  }

  const blocked = diagnostics.filter((item) => item.blockers?.length);
  const promotable = diagnostics.filter((item) => item.safe_to_promote);
  panel.hidden = false;
  title.textContent = "All connector activation checks";
  badge.textContent = blocked.length ? `${blocked.length} blocked` : "Clear";
  badge.dataset.variant = blocked.length ? "warning" : "positive";
  summary.textContent = blocked.length
    ? `${promotable.length}/${diagnostics.length} connectors are safe to promote. Clear the blockers below before activating payments, live data, or venue rails.`
    : `${promotable.length}/${diagnostics.length} connectors are safe to promote. Advisory warnings may still need review.`;

  grid.innerHTML = diagnostics.map((diagnostic) => {
    const blockerSummary = diagnostic.blockers?.length
      ? diagnostic.blockers.slice(0, 2).map((blocker) => `<li>${escapeHtml(blocker)}</li>`).join("")
      : "<li>No hard blockers reported.</li>";
    return `
      <article class="connector-diagnostic-card diagnostic-${escapeHtml(diagnostic.overall_status)}">
        <div class="connector-head">
          <div>
            <p class="eyebrow">${diagnostic.safe_to_promote ? "Promotable" : "Needs work"}</p>
            <h4>${escapeHtml(diagnostic.label)}</h4>
          </div>
          <span class="status-pill" data-variant="${connectorDiagnosticVariant(diagnostic.overall_status)}">${connectorDiagnosticLabel(diagnostic.overall_status)}</span>
        </div>
        <p>${diagnostic.ready_to_activate ? "Ready to activate." : "Not ready for activation yet."}</p>
        <ul class="launch-track-list">${blockerSummary}</ul>
        <button class="text-button" type="button" data-action="run-connector-check" data-connector-id="${escapeHtml(diagnostic.connector_id)}">Open detailed check</button>
      </article>
    `;
  }).join("");

  actions.innerHTML = blocked
    .slice(0, 5)
    .map((diagnostic) => `<li>${escapeHtml(diagnostic.label)}: ${escapeHtml(diagnostic.next_actions?.[0] || "Review connector configuration.")}</li>`)
    .join("");

  panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function renderInfrastructureReadiness(infrastructureReadiness) {
  const summary = document.getElementById("infrastructure-summary");
  const badge = document.getElementById("infrastructure-badge");
  const grid = document.getElementById("infrastructure-task-grid");
  if (!summary || !badge || !grid || !infrastructureReadiness) {
    return;
  }

  summary.textContent = infrastructureReadiness.summary;
  badge.textContent = infrastructureReadiness.production_posture === "ready" ? "Production ready" : "Needs hardening";
  badge.dataset.variant = infrastructureReadiness.production_posture === "ready" ? "positive" : "warning";

  grid.innerHTML = (infrastructureReadiness.tasks || []).map((task) => `
    <article class="infrastructure-task-card infrastructure-${task.state}">
      <div class="connector-head">
        <div>
          <p class="eyebrow">Infrastructure</p>
          <h4>${task.label}</h4>
        </div>
        <span class="status-pill" data-variant="${task.state === "ready" ? "positive" : (task.state === "planned" ? "neutral" : "warning")}">${task.state === "ready" ? "Ready" : (task.state === "planned" ? "Planned" : "Attention")}</span>
      </div>
      <p>${task.detail}</p>
      <small>${task.next_step}</small>
    </article>
  `).join("");
}

function renderProductionCutover(productionCutover) {
  const summary = document.getElementById("cutover-summary");
  const sourceNote = document.getElementById("cutover-source-note");
  const badge = document.getElementById("cutover-badge");
  const grid = document.getElementById("cutover-step-grid");
  if (!summary || !sourceNote || !badge || !grid || !productionCutover) {
    return;
  }

  summary.textContent = productionCutover.summary;
  sourceNote.textContent = productionCutover.source_data_note;
  badge.textContent = productionCutover.posture === "ready" ? "Cutover complete" : "Cutover pending";
  badge.dataset.variant = productionCutover.posture === "ready" ? "positive" : "warning";

  grid.innerHTML = (productionCutover.steps || []).map((step) => {
    const command = step.command
      ? `<pre class="cutover-command"><code>${step.command}</code></pre>`
      : "";
    return `
      <article class="cutover-step-card cutover-${step.state}">
        <div class="connector-head">
          <div>
            <p class="eyebrow">Cutover step</p>
            <h4>${step.label}</h4>
          </div>
          <span class="status-pill" data-variant="${step.state === "ready" ? "positive" : (step.state === "planned" ? "neutral" : "warning")}">${step.state === "ready" ? "Ready" : (step.state === "planned" ? "Planned" : "Attention")}</span>
        </div>
        <p>${step.detail}</p>
        ${command}
      </article>
    `;
  }).join("");
}

function renderMarketTape(assets) {
  const track = document.getElementById("market-tape-track");
  if (!track) {
    return;
  }
  const chips = assets.map((asset) => `
    <article class="tape-chip ${asset.change_24h >= 0 ? "tape-chip-up" : "tape-chip-down"}">
      <span class="tape-chip-symbol">${asset.asset}</span>
      <strong>${fmtPrice(asset.price)}</strong>
      <span>${fmtSignedPercent(asset.change_24h)} · trend ${asset.trend_score.toFixed(2)}</span>
    </article>
  `).join("");
  track.innerHTML = `${chips}${chips}`;
}

function renderMarketConsole(snapshot) {
  const badge = document.getElementById("market-console-badge");
  const stack = document.getElementById("market-console-stack");
  const decisions = document.getElementById("market-console-decisions");
  const risk = document.getElementById("market-console-risk");
  if (!badge || !stack || !decisions || !risk || !snapshot) {
    return;
  }

  const provider = snapshot.provider_status || {};
  const connectors = snapshot.connector_control?.connectors || [];
  const assets = snapshot.assets || [];
  const paperSummary = snapshot.paper_trading?.summary || {};
  const liveConnectors = connectors.filter((connector) => connector.state === "live");
  const readyConnectors = connectors.filter((connector) => connector.state === "live" || connector.state === "ready");
  const fallbackActive = Boolean(
    provider.market_fallback_active
    || provider.signal_fallback_active
    || provider.macro_fallback_active
    || provider.wallet_fallback_active
    || provider.social_discovery_fallback_active
  );

  badge.textContent = fallbackActive ? "Fallback guarded" : `${readyConnectors.length} surfaces ready`;
  badge.dataset.variant = fallbackActive ? "warning" : (readyConnectors.length >= 4 ? "positive" : "neutral");

  const venueLabels = (provider.venue_signal_providers || []).map((item) => item.source).join(", ") || "research queue";
  const stackRows = [
    {
      label: "Market tape",
      value: provider.market_provider_source || "market provider",
      detail: `${assets.length} tracked assets | ${provider.market_provider_mode || "demo"} mode`,
      state: provider.market_provider_ready ? (provider.market_provider_live_capable ? "Live-capable" : "Ready") : "Needs attention",
      variant: provider.market_provider_ready ? "positive" : "warning",
    },
    {
      label: "Signal intake",
      value: provider.signal_provider_source || "signal provider",
      detail: `${snapshot.system_pulse?.total_recent_signals || 0} recent signals | ${provider.signal_provider_mode || "demo"} mode`,
      state: provider.signal_provider_ready ? (provider.signal_provider_live_capable ? "Live-capable" : "Ready") : "Needs attention",
      variant: provider.signal_provider_ready ? "positive" : "warning",
    },
    {
      label: "Prediction venues",
      value: venueLabels,
      detail: `${snapshot.system_pulse?.venue_pulse?.length || 0} active venue pulse cards`,
      state: (provider.venue_signal_providers || []).some((item) => item.ready) ? "Live research" : "Planned",
      variant: (provider.venue_signal_providers || []).some((item) => item.ready) ? "positive" : "neutral",
    },
    {
      label: "Smart money",
      value: provider.wallet_provider_source || "wallet provider",
      detail: `${snapshot.wallet_intelligence?.wallets?.length || 0} tracked profiles | ${provider.wallet_provider_mode || "demo"} mode`,
      state: provider.wallet_provider_ready ? (provider.wallet_provider_live_capable ? "Live-capable" : "Ready") : "Needs attention",
      variant: provider.wallet_provider_ready ? "positive" : "warning",
    },
    {
      label: "Creator discovery",
      value: provider.social_discovery_provider_source || "social discovery",
      detail: `${snapshot.social_trading?.top_traders?.length || 0} trader-creators | ${provider.social_discovery_provider_mode || "demo"} mode`,
      state: provider.social_discovery_ready ? (provider.social_discovery_live_capable ? "YouTube live-capable" : "Ready") : "Needs key",
      variant: provider.social_discovery_ready ? "positive" : "warning",
    },
  ];

  stack.innerHTML = stackRows.map((row) => `
    <article class="console-stack-row">
      <div>
        <span>${escapeHtml(row.label)}</span>
        <strong>${escapeHtml(row.value)}</strong>
        <small>${escapeHtml(row.detail)}</small>
      </div>
      <span class="status-pill" data-variant="${row.variant}">${escapeHtml(row.state)}</span>
    </article>
  `).join("");

  const edgeItems = [...(snapshot.edge_snapshot?.opportunities || [])]
    .sort((a, b) => Math.abs(Number(b.edge_bps || 0)) - Math.abs(Number(a.edge_bps || 0)))
    .slice(0, 2)
    .map((item) => ({
      type: "Edge",
      title: `${item.asset} ${item.stance} edge`,
      meta: `${fmtBps(item.edge_bps)} | fair ${fmtPercent(item.fair_probability)} vs market ${fmtPercent(item.implied_probability)}`,
      strength: Number(item.confidence || 0),
    }));
  const signalItems = [...(snapshot.recent_signals || [])]
    .sort((a, b) => Number(b.source_quality_score || 0) - Number(a.source_quality_score || 0))
    .slice(0, 2)
    .map((item) => ({
      type: item.source_type === "prediction-market" ? "Venue" : "Signal",
      title: `${item.asset} | ${item.title}`,
      meta: `${sentimentLabel(item.sentiment)} | quality ${fmtPercent(item.source_quality_score)} | ${fmtRelativeTime(item.observed_at)}`,
      strength: Number(item.source_quality_score || 0),
    }));
  const predictionItems = [...(snapshot.recent_predictions || [])]
    .sort((a, b) => Number(b.confidence || 0) - Number(a.confidence || 0))
    .slice(0, 1)
    .map((item) => ({
      type: "Bot call",
      title: `${item.asset} ${item.direction} | ${item.bot_name}`,
      meta: `${fmtPercent(item.confidence)} confidence | ${item.horizon_label}`,
      strength: Number(item.confidence || 0),
    }));
  const decisionItems = [...edgeItems, ...signalItems, ...predictionItems].slice(0, 5);

  decisions.innerHTML = decisionItems.length
    ? decisionItems.map((item) => `
      <article class="console-decision">
        <div>
          <span>${escapeHtml(item.type)}</span>
          <strong>${escapeHtml(item.title)}</strong>
          <small>${escapeHtml(item.meta)}</small>
        </div>
        <div class="mini-meter"><i style="width:${(clamp(item.strength, 0, 1) * 100).toFixed(2)}%"></i></div>
      </article>
    `).join("")
    : '<p class="panel-note">Run a pipeline cycle to populate the decision queue.</p>';

  const riskRows = [
    ["Paper equity", fmtUsd(paperSummary.equity || 0), `${fmtSignedPercent(paperSummary.total_return || 0)} total return`],
    ["Cash", fmtUsd(paperSummary.cash_balance || 0), `${fmtUsd(paperSummary.open_exposure || 0)} open exposure`],
    ["Open positions", paperSummary.open_positions || 0, `${paperSummary.closed_positions || 0} closed test positions`],
    ["Execution mode", "Paper only", `${snapshot.paper_venues?.ready_venues || 0} venues ready | live trading disabled`],
  ];

  risk.innerHTML = riskRows.map(([label, value, detail]) => `
    <article>
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
      <small>${escapeHtml(detail)}</small>
    </article>
  `).join("");

  if (!liveConnectors.length) {
    risk.insertAdjacentHTML(
      "beforeend",
      '<p class="console-safety-note">Safety mode: research, live-capable data, and paper accounting are visible, but funded execution is intentionally blocked.</p>'
    );
  }
}

function destroyChart(targetId) {
  const existing = chartInstances.get(targetId);
  if (existing) {
    existing.remove();
    chartInstances.delete(targetId);
  }
}

function normalizeChartPoints(points = []) {
  return points
    .map((point) => ({
      time: Math.floor(new Date(point.time).getTime() / 1000),
      value: Number(point.value),
    }))
    .filter((point) => Number.isFinite(point.time) && Number.isFinite(point.value));
}

async function loadAssetHistory(asset) {
  const symbol = String(asset || "").toUpperCase();
  if (!symbol) {
    return null;
  }
  if (assetHistoryCache.has(symbol)) {
    return assetHistoryCache.get(symbol);
  }
  const payload = await fetchJson(`/api/assets/${encodeURIComponent(symbol)}/history`);
  assetHistoryCache.set(symbol, payload);
  return payload;
}

function renderTimeSeriesChart(targetId, points, options = {}) {
  const container = document.getElementById(targetId);
  if (!container || !window.LightweightCharts) {
    return;
  }
  destroyChart(targetId);
  container.innerHTML = "";

  const data = normalizeChartPoints(points);
  if (!data.length) {
    container.innerHTML = '<p class="panel-note">No chart data is available yet.</p>';
    return;
  }

  const chart = window.LightweightCharts.createChart(container, {
    width: Math.max(container.clientWidth, 320),
    height: options.height || 280,
    layout: {
      background: { color: "transparent" },
      textColor: "#5a6a75",
      fontFamily: '"Avenir Next", "Franklin Gothic Book", "Trebuchet MS", sans-serif',
    },
    grid: {
      vertLines: { color: "rgba(16, 38, 54, 0.08)" },
      horzLines: { color: "rgba(16, 38, 54, 0.08)" },
    },
    rightPriceScale: {
      borderColor: "rgba(16, 38, 54, 0.12)",
    },
    timeScale: {
      borderColor: "rgba(16, 38, 54, 0.12)",
      timeVisible: true,
      secondsVisible: false,
    },
    crosshair: {
      vertLine: { color: "rgba(196, 106, 55, 0.28)" },
      horzLine: { color: "rgba(31, 122, 120, 0.22)" },
    },
  });

  const seriesKind = options.seriesKind === "line"
    ? window.LightweightCharts.LineSeries
    : window.LightweightCharts.AreaSeries;
  const series = chart.addSeries(seriesKind, {
    color: options.lineColor || "#1f7a78",
    lineWidth: 3,
    topColor: options.topColor || "rgba(31, 122, 120, 0.28)",
    bottomColor: options.bottomColor || "rgba(31, 122, 120, 0.04)",
    priceLineVisible: false,
    lastValueVisible: true,
  });
  series.setData(data);
  chart.timeScale().fitContent();
  chartInstances.set(targetId, chart);
}

function resizeVisibleCharts() {
  chartInstances.forEach((chart, targetId) => {
    const container = document.getElementById(targetId);
    if (!container) {
      return;
    }
    chart.resize(
      Math.max(container.clientWidth, 320),
      Math.max(container.clientHeight, 240),
    );
  });
}

function renderPillRow(targetId, items, selectedValue, action) {
  const container = document.getElementById(targetId);
  if (!container) {
    return;
  }
  container.innerHTML = items.map((item) => `
    <button
      class="pill-button ${item.value === selectedValue ? "is-active" : ""}"
      type="button"
      data-action="${action}"
      data-value="${item.value}"
    >${item.label}</button>
  `).join("");
}

async function renderLandingMarketChart(assets) {
  const selectedAsset = selectedLandingAsset || assets?.[0]?.asset;
  if (!selectedAsset) {
    return;
  }
  selectedLandingAsset = selectedAsset;
  renderPillRow(
    "landing-chart-tabs",
    (assets || []).map((asset) => ({ value: asset.asset, label: asset.asset })),
    selectedLandingAsset,
    "select-landing-asset",
  );
  const history = await loadAssetHistory(selectedLandingAsset);
  renderTimeSeriesChart("landing-market-chart", history?.points || [], {
    lineColor: "#1f7a78",
    topColor: "rgba(31, 122, 120, 0.24)",
    bottomColor: "rgba(31, 122, 120, 0.03)",
    height: 300,
  });
  const note = document.getElementById("landing-chart-note");
  if (note) {
    note.innerHTML = `${selectedLandingAsset} history from the market snapshot archive. Charts powered by <a class="text-link" href="https://github.com/tradingview/lightweight-charts" target="_blank" rel="noreferrer">TradingView Lightweight Charts</a>.`;
  }
}

async function renderDashboardMarketChart(assets) {
  const selectedAsset = selectedDashboardAsset || assets?.[0]?.asset;
  if (!selectedAsset) {
    return;
  }
  selectedDashboardAsset = selectedAsset;
  renderPillRow(
    "dashboard-chart-tabs",
    (assets || []).map((asset) => ({ value: asset.asset, label: asset.asset })),
    selectedDashboardAsset,
    "select-dashboard-asset",
  );
  const history = await loadAssetHistory(selectedDashboardAsset);
  renderTimeSeriesChart("dashboard-market-chart", history?.points || [], {
    lineColor: "#c46a37",
    topColor: "rgba(196, 106, 55, 0.24)",
    bottomColor: "rgba(196, 106, 55, 0.04)",
    height: 320,
  });
  const note = document.getElementById("dashboard-chart-note");
  if (note) {
    note.innerHTML = `${selectedDashboardAsset} price history from the Bot Society Markets archive. Charts powered by <a class="text-link" href="https://github.com/tradingview/lightweight-charts" target="_blank" rel="noreferrer">TradingView Lightweight Charts</a>.`;
  }
}

function renderMacroCards(macroSnapshot, gridId, postureId, summaryId) {
  const grid = document.getElementById(gridId);
  const posture = document.getElementById(postureId);
  const summary = document.getElementById(summaryId);
  if (!grid || !macroSnapshot) {
    return;
  }
  if (posture) {
    posture.textContent = macroSnapshot.posture;
  }
  if (summary) {
    summary.textContent = macroSnapshot.summary;
  }
  grid.innerHTML = (macroSnapshot.series || []).map((series) => `
    <article class="macro-card ${qualityCardClass(Math.abs(series.signal_bias))}">
      <span>${series.label}</span>
      <strong>${fmtPrice(series.latest_value)}</strong>
      <p>${series.regime_label} · ${fmtSignedPercent(series.change_percent)}</p>
      <small>${series.unit} · updated ${fmtRelativeTime(series.observed_at)}</small>
    </article>
  `).join("");
}

function renderMacroChart(macroSnapshot) {
  if (!macroSnapshot?.series?.length) {
    return;
  }
  selectedMacroSeries = selectedMacroSeries || macroSnapshot.series[0].series_id;
  renderPillRow(
    "dashboard-macro-tabs",
    macroSnapshot.series.map((series) => ({ value: series.series_id, label: series.label })),
    selectedMacroSeries,
    "select-macro-series",
  );
  const activeSeries = macroSnapshot.series.find((series) => series.series_id === selectedMacroSeries) || macroSnapshot.series[0];
  if (!activeSeries) {
    return;
  }
  renderTimeSeriesChart("dashboard-macro-chart", activeSeries.history || [], {
    lineColor: "#18354a",
    topColor: "rgba(24, 53, 74, 0.18)",
    bottomColor: "rgba(24, 53, 74, 0.03)",
    seriesKind: "line",
    height: 320,
  });
  const note = document.getElementById("dashboard-macro-note");
  if (note) {
    note.textContent = `${activeSeries.label} (${activeSeries.unit}) · ${activeSeries.regime_label} · latest change ${fmtSignedPercent(activeSeries.change_percent)}.`;
  }
}

function renderPaperTrading(paperTrading) {
  const summary = document.getElementById("paper-trading-summary");
  const list = document.getElementById("paper-trading-list");
  if (!summary || !list || !paperTrading) {
    return;
  }
  summary.innerHTML = `
    <article class="pulse-metric-card">
      <span>Equity</span>
      <strong>${fmtPrice(paperTrading.summary.equity)}</strong>
      <small>Total simulated portfolio value</small>
    </article>
    <article class="pulse-metric-card">
      <span>Cash</span>
      <strong>${fmtPrice(paperTrading.summary.cash_balance)}</strong>
      <small>Unallocated simulated buying power</small>
    </article>
    <article class="pulse-metric-card ${paperTrading.summary.unrealized_pnl >= 0 ? "tone-high" : "tone-low"}">
      <span>Unrealized P&L</span>
      <strong>${fmtSignedPercent(paperTrading.summary.unrealized_pnl / paperTrading.summary.starting_balance)}</strong>
      <small>${fmtPrice(paperTrading.summary.unrealized_pnl)} open position mark-to-market</small>
    </article>
    <article class="pulse-metric-card ${paperTrading.summary.realized_pnl >= 0 ? "tone-high" : "tone-low"}">
      <span>Realized P&L</span>
      <strong>${fmtSignedPercent(paperTrading.summary.realized_pnl / paperTrading.summary.starting_balance)}</strong>
      <small>${fmtPrice(paperTrading.summary.realized_pnl)} closed position result</small>
    </article>
    <article class="pulse-metric-card">
      <span>Win rate</span>
      <strong>${fmtPercent(paperTrading.summary.win_rate)}</strong>
      <small>${paperTrading.summary.open_positions} open · ${paperTrading.summary.closed_positions} closed</small>
    </article>
  `;

  list.innerHTML = (paperTrading.positions || []).map((position) => `
    <li>
      <div>
        <strong>${position.bot_name} · ${position.asset} · ${position.direction}</strong>
        <p>${position.status === "open" ? "Open simulated position" : "Closed simulated position"} · ${fmtPercent(position.confidence)} confidence</p>
        <p class="panel-note">Entry ${fmtPrice(position.entry_price)} · current ${fmtPrice(position.current_price)} · allocation ${fmtPrice(position.allocation_usd)}</p>
      </div>
      <div class="workspace-actions">
        <span>${position.status === "open" ? `Unrealized ${fmtPrice(position.unrealized_pnl)}` : `Realized ${fmtPrice(position.realized_pnl || 0)}`}</span>
        <span>${position.opened_at ? fmtRelativeTime(position.opened_at) : "n/a"}</span>
      </div>
    </li>
  `).join("") || "<li><p>No paper positions have been simulated yet.</p></li>";
}

function renderPaperVenues(paperVenues) {
  const summary = document.getElementById("paper-venue-summary");
  const list = document.getElementById("paper-venue-list");
  const sequence = document.getElementById("paper-venue-sequence");
  if (!summary || !list || !paperVenues) {
    return;
  }

  summary.textContent = paperVenues.summary;
  const venues = paperVenues.venues || [];
  list.innerHTML = venues.map((venue) => {
    const statusClass = venue.status === "ready" || venue.status === "manual_only" ? "tone-high" : (venue.status === "needs_credentials" ? "tone-mid" : "tone-low");
    const statusLabel = venue.status.replaceAll("_", " ");
    return `
      <article class="paper-venue-card ${statusClass}">
        <div class="paper-venue-head">
          <div>
            <span>${venue.category}</span>
            <h4>${venue.name}</h4>
          </div>
          <span class="badge">${statusLabel}</span>
        </div>
        <p>${venue.capability_summary}</p>
        <div class="paper-venue-kpis">
          <div><span>Readiness</span><strong>${fmtPercent(venue.readiness_score)}</strong></div>
          <div><span>API</span><strong>${venue.api_capable ? "Yes" : "No"}</strong></div>
          <div><span>Replay</span><strong>${venue.historical_replay_capable ? "Yes" : "No"}</strong></div>
        </div>
        <ul class="edge-signal-list">
          ${(venue.capabilities || []).slice(0, 2).map((capability) => `<li><strong>${capability.label}</strong> - ${capability.detail}</li>`).join("")}
        </ul>
        <div class="paper-venue-actions">
          <a class="text-link" href="${venue.app_url}" target="${venue.app_url.startsWith("/") ? "_self" : "_blank"}" rel="noreferrer">Open venue</a>
          ${venue.docs_url ? `<a class="text-link" href="${venue.docs_url}" target="_blank" rel="noreferrer">Docs</a>` : ""}
        </div>
        <small>${venue.next_action}</small>
      </article>
    `;
  }).join("");

  if (sequence) {
    sequence.innerHTML = (paperVenues.activation_sequence || [])
      .slice(0, 5)
      .map((step, index) => `<li><span>${index + 1}</span><p>${step}</p></li>`)
      .join("");
  }
}

function socialInitials(name) {
  return String(name || "ST")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() || "")
    .join("") || "ST";
}

function socialAvatarStyle(seed) {
  const source = String(seed || "social");
  const score = [...source].reduce((total, character) => total + character.charCodeAt(0), 0);
  return `--avatar-hue:${score % 360}deg`;
}

function socialAvatarMarkup(trader) {
  const animation = escapeHtml(trader.avatar_animation || "youtube-pulse");
  const name = escapeHtml(trader.display_name || "Social trader");
  if (trader.avatar_url) {
    return `
      <div class="social-avatar-bust has-photo ${animation}" style="${socialAvatarStyle(trader.avatar_seed)}">
        <img src="${escapeHtml(trader.avatar_url)}" alt="${name} YouTube profile picture" loading="lazy">
      </div>
    `;
  }
  return `
    <div class="social-avatar-bust ${animation}" style="${socialAvatarStyle(trader.avatar_seed)}">
      <span>${escapeHtml(socialInitials(trader.display_name))}</span>
    </div>
  `;
}

function socialRoiWindowsMarkup(trader) {
  return (trader.roi_windows || []).map((window) => `
    <div>
      <span>${escapeHtml(window.label)}</span>
      <strong class="${Number(window.return_pct || 0) >= 0 ? "profit-text" : "loss-text"}">${fmtSignedPercent(window.return_pct || 0)}</strong>
      <small>${fmtUsd(window.pnl_usd || 0)} · ${window.signal_count || 0} signal(s)</small>
    </div>
  `).join("");
}

function socialDecisionFeedMarkup(trader) {
  return (trader.decision_feed || []).slice(0, 3).map((decision) => `
    <li>
      <div>
        <strong>${escapeHtml(decision.asset)} · ${escapeHtml(humanizeKey(decision.action || "watch"))}</strong>
        <p>${escapeHtml(decision.rationale)}</p>
        <small>${escapeHtml(decision.source_title || "YouTube evidence")} · ${fmtRelativeTime(decision.observed_at)}</small>
      </div>
      <span data-tone="${decision.direction === "bearish" ? "danger" : decision.direction === "bullish" ? "positive" : "warning"}">${escapeHtml(decision.direction)} · ${fmtPercent(decision.confidence || 0)}</span>
    </li>
  `).join("") || "<li><p>No live decision feed yet. Run YouTube discovery to create fresh decisions.</p></li>";
}

function socialExecutionLedgerMarkup(socialTrading) {
  const execution = latestSocialExecution;
  if (execution?.decisions?.length) {
    return execution.decisions.slice(0, 8).map((decision) => {
      const tone = decision.action === "opened_position"
        ? "positive"
        : decision.action?.includes("risk") || decision.action?.includes("low") || decision.action?.includes("unsupported")
          ? "warning"
          : "neutral";
      return `
        <li>
          <div>
            <strong>${escapeHtml(decision.trader_name)} · ${escapeHtml(decision.asset)} ${escapeHtml(decision.direction)}</strong>
            <p>${escapeHtml(decision.reason)}</p>
            <small>${escapeHtml(decision.source_title || "YouTube signal")} · ${fmtRelativeTime(decision.observed_at)}</small>
          </div>
          <span class="badge" data-tone="${tone}">
            ${escapeHtml(humanizeKey(decision.action || "decision"))}
            ${decision.notional_usd ? ` · ${fmtUsd(decision.notional_usd)}` : ""}
          </span>
        </li>
      `;
    }).join("");
  }

  const decisions = socialTrading?.decision_feed || [];
  return decisions.slice(0, 6).map((decision) => `
    <li>
      <div>
        <strong>${escapeHtml(decision.asset)} · ${escapeHtml(humanizeKey(decision.action || "watch"))}</strong>
        <p>${escapeHtml(decision.rationale)}</p>
        <small>${escapeHtml(decision.source_title || "YouTube evidence")} · ${fmtRelativeTime(decision.observed_at)}</small>
      </div>
      <span class="badge" data-tone="${decision.direction === "bearish" ? "danger" : decision.direction === "bullish" ? "positive" : "warning"}">
        ${escapeHtml(decision.direction)} · ${fmtPercent(decision.confidence || 0)}
      </span>
    </li>
  `).join("") || "<li><p>Run YouTube discovery or the managed-paper bot to populate the decision ledger.</p></li>";
}

function socialAssetExposureMarkup(trader) {
  return (trader.asset_exposure || []).slice(0, 5).map((asset) => `
    <span>
      <strong>${escapeHtml(asset.asset)}</strong>
      ${escapeHtml(asset.bias)} · ${asset.signal_count} call(s) · ${fmtSignedPercent(asset.average_return || 0)}
    </span>
  `).join("");
}

function socialRiskTone(level) {
  if (level === "low") {
    return "positive";
  }
  if (level === "high") {
    return "danger";
  }
  return "warning";
}

function socialImpactTone(label) {
  const normalized = String(label || "").toLowerCase();
  if (normalized.includes("miss") || normalized.includes("negative")) {
    return "danger";
  }
  if (normalized.includes("flat")) {
    return "warning";
  }
  return "positive";
}

function socialRunTone(status) {
  const normalized = String(status || "").toLowerCase();
  if (normalized.includes("fail")) {
    return "danger";
  }
  if (normalized.includes("warning")) {
    return "warning";
  }
  return "positive";
}

function socialSourceTone(state) {
  if (state === "live" || state === "indexed") {
    return "positive";
  }
  if (state === "connector_build_required" || state === "planned") {
    return "warning";
  }
  return "neutral";
}

function socialCreatorStageLabel(stage) {
  const labels = {
    awaiting_evidence: "Awaiting evidence",
    youtube_profile_active: "YouTube profile active",
    multi_source_profile: "Multi-source learning",
    paper_validation: "Paper validation",
  };
  return labels[stage] || humanizeKey(stage || "awaiting_evidence");
}

function socialCreatorBotMarkup(trader) {
  const bot = trader.creator_bot;
  if (!bot) {
    return "";
  }
  const sourceChips = (trader.source_coverage || []).map((source) => `
    <span data-tone="${socialSourceTone(source.state)}">
      ${escapeHtml(source.label)} · ${escapeHtml(humanizeKey(source.state))}
    </span>
  `).join("");
  const coverage = Math.max(0, Math.min(100, Number(bot.source_coverage_pct || 0) * 100));
  return `
    <div class="social-training-card">
      <div class="social-training-head">
        <div>
          <span>Creator bot</span>
          <strong>${escapeHtml(bot.bot_name)}</strong>
          <small>${escapeHtml(socialCreatorStageLabel(bot.stage))} · ${bot.dataset_events || 0} indexed item(s)</small>
        </div>
        <div class="social-training-confidence">
          <span>Evidence confidence</span>
          <strong>${fmtPercent(bot.evidence_confidence || 0)}</strong>
        </div>
      </div>
      <div class="social-training-meter" aria-label="Source coverage ${coverage.toFixed(0)} percent">
        <span style="width:${coverage}%"></span>
      </div>
      <div class="social-source-chip-row">${sourceChips}</div>
      <p>${escapeHtml(trader.performance_basis || "Content-derived proxy; validation is pending.")}</p>
    </div>
  `;
}

function renderSocialBotFactory(socialTrading) {
  const registry = document.getElementById("social-source-registry");
  const backend = document.getElementById("social-backend-map");
  if (!registry || !backend) {
    return;
  }
  const connectors = socialTrading.source_connectors || [];
  registry.innerHTML = connectors.map((connector) => `
    <article class="social-source-card" data-tone="${socialSourceTone(connector.state)}">
      <div>
        <span class="social-source-dot"></span>
        <strong>${escapeHtml(connector.label)}</strong>
        <small>${escapeHtml(humanizeKey(connector.state))}</small>
      </div>
      <p>${escapeHtml(connector.role)}</p>
      <dl>
        <div><dt>Indexed</dt><dd>${connector.indexed_items || 0}</dd></div>
        <div><dt>Bots</dt><dd>${connector.monitored_profiles || 0}</dd></div>
        <div><dt>Latest</dt><dd>${connector.last_observed_at ? fmtRelativeTime(connector.last_observed_at) : "Waiting"}</dd></div>
      </dl>
      <small>${escapeHtml(connector.next_action)}</small>
    </article>
  `).join("") || '<article class="social-source-card"><p>Source registry is loading.</p></article>';

  const runtime = socialTrading.backend_runtime || {};
  const pipeline = socialTrading.bot_factory_pipeline || [];
  backend.innerHTML = `
    <div class="social-runtime-copy">
      <p class="eyebrow">Where the backend lives</p>
      <h5>Akash API + worker, backed by Neon Postgres</h5>
      <p>${escapeHtml(runtime.api_service || "Backend runtime status is loading.")}</p>
      <p>${escapeHtml(runtime.persistence || "")}</p>
      <span>${escapeHtml(runtime.execution_boundary || "")}</span>
    </div>
    <ol class="social-pipeline">
      ${pipeline.map((step) => `<li>${escapeHtml(step)}</li>`).join("")}
    </ol>
  `;
}

function socialTraderSearchText(trader, allocation) {
  return [
    trader.display_name,
    trader.handle,
    trader.description,
    trader.strategy_profile,
    trader.current_market_view,
    trader.pnl_history_summary,
    trader.conviction_label,
    trader.copy_trade_readiness,
    trader.risk_level,
    allocation?.mode,
    ...(trader.primary_assets || []),
    ...(trader.style_tags || []),
    ...(trader.asset_exposure || []).map((item) => `${item.asset} ${item.bias}`),
  ].filter(Boolean).join(" ").toLowerCase();
}

function socialTraderMatchesMarketplace(trader, allocationByTrader) {
  const allocation = allocationByTrader.get(trader.id);
  const query = socialMarketplaceState.query.trim().toLowerCase();
  if (query && !socialTraderSearchText(trader, allocation).includes(query)) {
    return false;
  }
  if (socialMarketplaceState.asset !== "all") {
    const assets = new Set([
      ...(trader.primary_assets || []),
      ...(trader.asset_exposure || []).map((item) => item.asset),
      ...(trader.evidence || []).map((item) => item.asset),
    ].map((asset) => String(asset).toUpperCase()));
    if (!assets.has(socialMarketplaceState.asset.toUpperCase())) {
      return false;
    }
  }
  if (socialMarketplaceState.risk !== "all" && trader.risk_level !== socialMarketplaceState.risk) {
    return false;
  }
  if (socialMarketplaceState.mode === "managed_paper" && allocation?.mode !== "managed_paper") {
    return false;
  }
  if (socialMarketplaceState.mode === "signals" && allocation?.mode !== "signals") {
    return false;
  }
  if (socialMarketplaceState.mode === "ready" && trader.copy_trade_readiness !== "paper_ready") {
    return false;
  }
  if (socialMarketplaceState.mode === "not_deployed" && (allocation || trader.is_deployed)) {
    return false;
  }
  return true;
}

function socialRiskRank(level) {
  return { low: 1, medium: 2, high: 3 }[level] || 4;
}

function socialSortValue(trader, allocationByTrader) {
  const allocation = allocationByTrader.get(trader.id);
  if (socialMarketplaceState.sort === "roi") {
    return Number(trader.roi_if_followed || 0);
  }
  if (socialMarketplaceState.sort === "win_rate") {
    return Number(trader.win_rate || 0);
  }
  if (socialMarketplaceState.sort === "recent") {
    return trader.last_signal_at ? new Date(trader.last_signal_at).getTime() : 0;
  }
  if (socialMarketplaceState.sort === "delegated") {
    return Number(trader.delegated_usd || allocation?.allocation_limit_usd || 0);
  }
  return Number(trader.composite_score || 0);
}

function socialSortTraders(traders, allocationByTrader) {
  return [...traders].sort((a, b) => {
    const primary = socialSortValue(b, allocationByTrader) - socialSortValue(a, allocationByTrader);
    if (Math.abs(primary) > 0.000001) {
      return primary;
    }
    const risk = socialRiskRank(a.risk_level) - socialRiskRank(b.risk_level);
    if (risk !== 0) {
      return risk;
    }
    return String(a.display_name || "").localeCompare(String(b.display_name || ""));
  });
}

function syncSocialMarketplaceControls(traders) {
  const search = document.getElementById("social-marketplace-search");
  const risk = document.getElementById("social-risk-filter");
  const mode = document.getElementById("social-mode-filter");
  const sort = document.getElementById("social-sort-select");
  const asset = document.getElementById("social-asset-filter");
  if (search && search.value !== socialMarketplaceState.query) {
    search.value = socialMarketplaceState.query;
  }
  if (risk) {
    risk.value = socialMarketplaceState.risk;
  }
  if (mode) {
    mode.value = socialMarketplaceState.mode;
  }
  if (sort) {
    sort.value = socialMarketplaceState.sort;
  }
  if (asset) {
    const assets = [...new Set(traders.flatMap((trader) => [
      ...(trader.primary_assets || []),
      ...(trader.asset_exposure || []).map((item) => item.asset),
      ...(trader.evidence || []).map((item) => item.asset),
    ]).map((item) => String(item).toUpperCase()).filter(Boolean))].sort();
    const options = ["all", ...assets];
    const signature = options.join("|");
    if (asset.dataset.signature !== signature) {
      asset.innerHTML = options.map((value) => (
        value === "all"
          ? '<option value="all">All assets</option>'
          : `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`
      )).join("");
      asset.dataset.signature = signature;
    }
    if (!options.includes(socialMarketplaceState.asset)) {
      socialMarketplaceState.asset = "all";
    }
    asset.value = socialMarketplaceState.asset;
  }
}

function updateSocialMarketplaceStatus(visibleCount, totalCount) {
  const counter = document.getElementById("social-visible-count");
  if (!counter) {
    return;
  }
  const suffix = visibleCount === 1 ? "manager" : "managers";
  counter.textContent = `${visibleCount} of ${totalCount} ${suffix}`;
}

function renderSocialTradingFromFilters() {
  if (latestSnapshot?.social_trading) {
    renderSocialTrading(latestSnapshot.social_trading);
  }
}

function socialTraderDetailMarkup(trader, allocation, canEdit) {
  const guidance = trader.allocation_guidance || {};
  const roiWindows = socialRoiWindowsMarkup(trader) || "<div><span>ROI</span><strong>Pending</strong><small>No signal window yet</small></div>";
  const exposure = socialAssetExposureMarkup(trader) || "<span><strong>Pending</strong> Waiting for indexed evidence</span>";
  const decisions = socialDecisionFeedMarkup(trader);
  const evidence = (trader.evidence || []).slice(0, 6).map((item) => `
    <li>
      <div>
        <a href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">${escapeHtml(item.title)}</a>
        <p>${escapeHtml(item.summary || "No summary available.")}</p>
        <small>${escapeHtml(item.asset)} · ${escapeHtml(item.direction)} · ${fmtPercent(item.confidence)} confidence · ${fmtRelativeTime(item.observed_at)}</small>
      </div>
      <span class="${Number(item.derived_return || 0) >= 0 ? "profit-text" : "loss-text"}">${fmtSignedPercent(item.derived_return || 0)}</span>
    </li>
  `).join("") || "<li><p>No public evidence indexed yet. Analyze the channel or scan new videos.</p></li>";
  const riskNotes = (trader.risk_notes || []).map((note) => `<li>${escapeHtml(note)}</li>`).join("")
    || "<li>Start with signal mode or paper-only delegation until more evidence is collected.</li>";

  return `
    <div class="social-detail-head">
      <div class="social-detail-identity">
        ${socialAvatarMarkup(trader)}
        <div>
          <p class="eyebrow">${escapeHtml(humanizeKey(trader.platform))} manager · ${escapeHtml(trader.handle)}</p>
          <h3 id="social-detail-title">${escapeHtml(trader.display_name)}</h3>
          <p>${escapeHtml(trader.description)}</p>
        </div>
      </div>
      <button class="button ghost small-button" type="button" data-action="social-close-detail">Close</button>
    </div>
    <div class="social-detail-status">
      <span data-tone="${socialRiskTone(trader.risk_level)}">Risk ${escapeHtml(humanizeKey(trader.risk_level || "medium"))}</span>
      <span>${escapeHtml(humanizeKey(trader.copy_trade_readiness || "signals_only"))}</span>
      <span>${trader.is_deployed ? `Deployed · ${fmtUsd(trader.delegated_usd || allocation?.allocation_limit_usd || 0)}` : "Not deployed"}</span>
    </div>
    ${socialCreatorBotMarkup(trader)}
    <div class="social-detail-scoreboard">
      <article><span>Score</span><strong>${fmtScore(trader.composite_score)}</strong><small>Composite creator score</small></article>
      <article><span>Win rate</span><strong>${fmtPercent(trader.win_rate)}</strong><small>${trader.signal_count || 0} extracted signal(s)</small></article>
      <article><span>Proxy if-followed</span><strong>${fmtSignedPercent(trader.roi_if_followed)}</strong><small>${fmtSignedPercent(trader.max_drawdown)} modeled drawdown</small></article>
      <article><span>Delegation</span><strong>${fmtUsd(trader.delegated_usd || allocation?.allocation_limit_usd || 0)}</strong><small>${escapeHtml(humanizeKey(allocation?.mode || trader.deployment_mode || guidance.recommended_mode || "signals"))}</small></article>
    </div>
    <div class="social-detail-two-col">
      <article>
        <span>Strategy profile</span>
        <p>${escapeHtml(trader.strategy_profile || "Strategy profile pending.")}</p>
      </article>
      <article>
        <span>Current market view</span>
        <p>${escapeHtml(trader.current_market_view || "Run discovery to update the latest market view.")}</p>
      </article>
    </div>
    <div class="social-roi-strip detail-roi-strip">${roiWindows}</div>
    <div class="social-asset-exposure detail-asset-exposure">${exposure}</div>
    <div class="social-detail-manager-box">
      <div>
        <span>Suggested cap</span>
        <strong>${fmtUsd(guidance.suggested_allocation_usd || 0)}</strong>
        <small>${escapeHtml(guidance.rationale || trader.watch_mode_recommendation || "")}</small>
      </div>
      <label class="social-detail-control">
        <span>Paper allocation cap</span>
        <input type="number" min="0" max="100000" step="50" value="${allocation?.allocation_limit_usd || guidance.suggested_allocation_usd || 500}" data-social-allocation-id="${trader.id}" ${disabledAttr(!canEdit)}>
      </label>
      <label class="social-detail-control">
        <span>Max per idea</span>
        <select data-social-position-id="${trader.id}" ${disabledAttr(!canEdit)}>
          <option value="0.08">8%</option>
          <option value="0.12" selected>12%</option>
          <option value="0.18">18%</option>
        </select>
      </label>
      <div class="social-detail-actions">
        <button class="button secondary small-button" type="button" data-action="social-follow-signal" data-social-trader-id="${trader.id}" ${disabledAttr(!canEdit)}>
          ${allocation?.mode === "signals" ? "Signals active" : "Signal follow"}
        </button>
        <button class="button primary small-button" type="button" data-action="social-follow-managed" data-social-trader-id="${trader.id}" ${disabledAttr(!canEdit)}>
          ${allocation?.mode === "managed_paper" ? "Paper bot active" : "Deploy paper bot"}
        </button>
      </div>
    </div>
    <div class="social-bot-decisions detail-decision-list">
      <div class="workspace-head">
        <h5>Decision timeline</h5>
        <span class="badge">Explainable bot</span>
      </div>
      <ul>${decisions}</ul>
    </div>
    <div class="social-detail-evidence">
      <div class="workspace-head">
        <h5>Evidence trail</h5>
        <span class="badge">${(trader.evidence || []).length} item(s)</span>
      </div>
      <ul>${evidence}</ul>
    </div>
    <div class="social-detail-risk">
      <p class="eyebrow">Risk notes</p>
      <ul>${riskNotes}</ul>
    </div>
  `;
}

function renderSocialTraderDrawer(socialTrading) {
  const drawer = document.getElementById("social-detail-drawer");
  const content = document.getElementById("social-detail-content");
  if (!drawer || !content || !selectedSocialTraderId) {
    return;
  }
  const traders = socialTrading?.top_traders || [];
  const allocations = socialTrading?.allocations || [];
  const allocationByTrader = new Map(allocations.map((allocation) => [allocation.trader_id, allocation]));
  const trader = traders.find((candidate) => Number(candidate.id) === Number(selectedSocialTraderId));
  if (!trader) {
    selectedSocialTraderId = null;
    drawer.classList.add("hidden");
    return;
  }
  content.innerHTML = socialTraderDetailMarkup(trader, allocationByTrader.get(trader.id), workspaceEditable());
  drawer.classList.remove("hidden");
}

function openSocialTraderDetail(traderId) {
  selectedSocialTraderId = Number(traderId);
  renderSocialTraderDrawer(latestSnapshot?.social_trading);
  setStatus("Opened the creator manager detail drawer.");
}

function closeSocialTraderDetail() {
  selectedSocialTraderId = null;
  const drawer = document.getElementById("social-detail-drawer");
  if (drawer) {
    drawer.classList.add("hidden");
  }
}

function renderSocialTrading(socialTrading) {
  const summary = document.getElementById("social-trader-summary");
  const badge = document.getElementById("social-trader-badge");
  const kpis = document.getElementById("social-trader-kpis");
  const grid = document.getElementById("social-trader-grid");
  const allocationList = document.getElementById("social-allocation-list");
  const executionLedgerList = document.getElementById("social-execution-ledger-list");
  const discoveryRunList = document.getElementById("social-discovery-run-list");
  const safetyList = document.getElementById("social-safety-list");
  if (!summary || !badge || !kpis || !grid || !allocationList || !safetyList || !socialTrading) {
    return;
  }

  const traders = socialTrading.top_traders || [];
  const allocations = socialTrading.allocations || [];
  const allocationByTrader = new Map(allocations.map((allocation) => [allocation.trader_id, allocation]));
  syncSocialMarketplaceControls(traders);
  const visibleTraders = socialSortTraders(
    traders.filter((trader) => socialTraderMatchesMarketplace(trader, allocationByTrader)),
    allocationByTrader,
  );
  updateSocialMarketplaceStatus(visibleTraders.length, traders.length);
  const canEdit = workspaceEditable();
  const executeButton = document.getElementById("social-execute-button");
  if (executeButton) {
    executeButton.disabled = !canEdit || !allocations.some((allocation) => allocation.is_active && allocation.mode === "managed_paper");
    executeButton.title = canEdit
      ? "Runs active managed-paper allocations into the paper ledger."
      : "Sign in to run managed-paper social execution.";
  }
  const topScore = traders[0]?.composite_score || 0;
  const averageRoi = traders.length
    ? traders.reduce((total, trader) => total + Number(trader.roi_if_followed || 0), 0) / traders.length
    : 0;
  const latestRun = socialTrading.latest_discovery_run || socialTrading.discovery_runs?.[0];
  const monitoring = socialTrading.monitoring || {};
  const decisionCount = (socialTrading.decision_feed || []).length;

  summary.textContent = socialTrading.summary;
  const xConnector = (socialTrading.source_connectors || []).find((source) => source.platform === "x");
  const deliveryLabel = {
    "direct-live-origin": " · Direct live",
    "edge-fallback": " · Standby snapshot",
    "edge-snapshot": " · Standby snapshot",
    "edge-live-cache": " · Edge cached",
  }[socialTrading.delivery_mode] || "";
  badge.textContent = socialTrading.youtube_configured
    ? `YouTube live · X ${xConnector?.state === "indexed" ? "indexed" : "pending"}${deliveryLabel}`
    : `YouTube setup needed${deliveryLabel}`;
  badge.dataset.variant = socialTrading.youtube_configured && !socialTrading.delivery_mode?.includes("fallback") ? "positive" : "warning";
  renderSocialBotFactory(socialTrading);

  kpis.innerHTML = `
    <article>
      <span>Indexed profiles</span>
      <strong>${traders.length}</strong>
      <small>${socialTrading.provider_mode || "social discovery"}</small>
    </article>
    <article>
      <span>Top score</span>
      <strong>${fmtScore(topScore)}</strong>
      <small>Composite creator score</small>
    </article>
    <article>
      <span>Paper allocated</span>
      <strong>${fmtUsd(socialTrading.allocated_usd || 0)}</strong>
      <small>${fmtUsd(socialTrading.unallocated_usd || 0)} unallocated</small>
    </article>
    <article>
      <span>Avg evidence proxy</span>
      <strong>${fmtSignedPercent(averageRoi)}</strong>
      <small>Not market-validated PnL</small>
    </article>
    <article>
      <span>Last discovery</span>
      <strong>${latestRun ? fmtRelativeTime(latestRun.completed_at) : "Waiting"}</strong>
      <small>${latestRun ? `${latestRun.updated} profiles · ${latestRun.evidence_count} evidence items` : "Run YouTube discovery to create the first ledger entry"}</small>
    </article>
    <article>
      <span>Monitor cadence</span>
      <strong>${monitoring.cadence_seconds ? `${Math.round(monitoring.cadence_seconds / 60)}m` : "Manual"}</strong>
      <small>${escapeHtml(monitoring.mode || "YouTube watchlist")} · ${decisionCount} bot decision(s)</small>
    </article>
  `;

  grid.innerHTML = visibleTraders.map((trader) => {
    const allocation = allocationByTrader.get(trader.id);
    const guidance = trader.allocation_guidance || {};
    const assets = (trader.primary_assets || []).slice(0, 3);
    const delegated = trader.delegated_usd || allocation?.allocation_limit_usd || 0;
    return `
      <button class="social-trader-card social-trader-button" type="button" data-action="social-open-detail" data-social-trader-id="${trader.id}" aria-label="Explore ${escapeHtml(trader.display_name)} social trader profile">
        <span class="social-card-topline">
          <span data-tone="${socialRiskTone(trader.risk_level)}">${escapeHtml(humanizeKey(trader.risk_level || "medium"))} risk</span>
          <span>${escapeHtml(humanizeKey(trader.copy_trade_readiness || "signals_only"))}</span>
          <span>${trader.is_deployed ? "Deployed" : "Not deployed"}</span>
        </span>
        <span class="social-trader-head social-trader-head-compact">
          ${socialAvatarMarkup(trader)}
          <span>
            <span class="eyebrow">${escapeHtml(humanizeKey(trader.platform))} · ${escapeHtml(trader.handle)}</span>
            <strong>${escapeHtml(trader.display_name)}</strong>
            <small>${escapeHtml(trader.conviction_label || trader.analysis_basis || "Creator signal watchlist")}</small>
          </span>
        </span>
        <span class="social-compact-stat-row">
          <span><small>Score</small><strong>${fmtScore(trader.composite_score)}</strong></span>
          <span><small>Win</small><strong>${fmtPercent(trader.win_rate)}</strong></span>
          <span><small>Proxy ROI</small><strong class="${Number(trader.roi_if_followed || 0) >= 0 ? "profit-text" : "loss-text"}">${fmtSignedPercent(trader.roi_if_followed)}</strong></span>
        </span>
        <span class="social-tag-row social-compact-tags">
          ${assets.map((asset) => `<span>${escapeHtml(asset)}</span>`).join("")}
        </span>
        <span class="social-compact-footer">
          <span>
            <strong>${trader.signal_count || 0}</strong> signals · <strong>${(trader.evidence || []).length}</strong> evidence
          </span>
          <span>${fmtUsd(delegated)} · ${escapeHtml(humanizeKey(allocation?.mode || trader.deployment_mode || guidance.recommended_mode || "signals"))}</span>
        </span>
        <span class="social-explore-cue">Explore profile <span aria-hidden="true">&rarr;</span></span>
      </button>
    `;
  }).join("") || (
    traders.length
      ? '<article class="social-empty-card"><h4>No managers match the filters</h4><p>Reset filters or search a broader asset/style to bring more creator managers back into view.</p></article>'
      : '<article class="social-empty-card"><h4>No social traders yet</h4><p>Run YouTube discovery to populate creator scorecards.</p></article>'
  );

  allocationList.innerHTML = allocations.map((allocation) => `
    <li>
      <div>
        <strong>${escapeHtml(allocation.trader_name)}</strong>
        <p>${escapeHtml(humanizeKey(allocation.mode))} · cap ${fmtUsd(allocation.allocation_limit_usd)} · max ${fmtPercent(allocation.max_position_pct)} per idea</p>
      </div>
      <span class="badge">${allocation.is_active ? "Active" : "Paused"}</span>
    </li>
  `).join("") || "<li><p>No followed social managers yet. Sign in, then activate signal or managed-paper mode from a profile card.</p></li>";

  if (executionLedgerList) {
    executionLedgerList.innerHTML = socialExecutionLedgerMarkup(socialTrading);
  }

  if (discoveryRunList) {
    discoveryRunList.innerHTML = (socialTrading.discovery_runs || []).map((run) => {
      const warnings = (run.warnings || []).slice(0, 1).map((warning) => `<small>${escapeHtml(warning)}</small>`).join("");
      return `
        <li>
          <div>
            <strong>${escapeHtml(humanizeKey(run.provider || "social discovery"))}</strong>
            <p>${run.updated} profile(s), ${run.discovered} new, ${run.evidence_count} evidence item(s) · ${fmtRelativeTime(run.completed_at)}</p>
            ${warnings}
          </div>
          <span class="badge" data-tone="${socialRunTone(run.status)}">${escapeHtml(humanizeKey(run.status || "completed"))}</span>
        </li>
      `;
    }).join("") || "<li><p>No discovery runs are recorded yet.</p></li>";
  }

  safetyList.innerHTML = [
    monitoring.next_action,
    ...(socialTrading.portfolio_risk_notes || []),
    ...(socialTrading.safety_notes || []),
  ].filter(Boolean).map((note) => `<li>${escapeHtml(note)}</li>`).join("");
  renderSocialTraderDrawer(socialTrading);
}

const TRADER_INTELLIGENCE_PROGRESS_STEPS = [
  ["queued", "Queued"],
  ["importing", "Importing sources"],
  ["transcribing", "Fetching transcripts/content"],
  ["chunking", "Chunking knowledge base"],
  ["worldview", "Running worldview analysis"],
  ["frameworks", "Extracting frameworks"],
  ["contradictions", "Detecting contradictions"],
  ["synthesis", "Generating synthesis brief"],
  ["completed", "Completed"],
];

function traderIntelligenceProfileById(profileId) {
  return traderIntelligenceState.profiles.find((profile) => Number(profile.id) === Number(profileId));
}

function traderIntelligenceConfidenceTone(score = 0) {
  const numeric = Number(score) || 0;
  if (numeric >= 0.7) {
    return "positive";
  }
  if (numeric >= 0.45) {
    return "warning";
  }
  return "danger";
}

function traderIntelligenceStatusTone(status = "") {
  if (status === "completed") {
    return "positive";
  }
  if (status === "failed") {
    return "danger";
  }
  return "warning";
}

function traderIntelligenceInsightCount(profile = {}) {
  return [
    ...(profile.worldview?.claims || []),
    ...(profile.frameworks?.claims || []),
    ...(profile.strategy?.claims || []),
    ...(profile.synthesis?.claims || []),
    ...(profile.evolution?.claims || []),
    ...(profile.contradictions || []),
    ...(profile.vocabulary || []),
    ...(profile.decision_rules || []),
    ...(profile.risk_rules || []),
    ...(profile.recommendations || []),
  ].length;
}

function traderIntelligenceAllInsights(profiles = traderIntelligenceState.profiles) {
  const rows = [];
  const addClaims = (profile, type, claims = []) => {
    claims.forEach((claim) => rows.push({ profile, type, claim }));
  };
  profiles.forEach((profile) => {
    addClaims(profile, "belief", profile.worldview?.claims || []);
    addClaims(profile, "framework", profile.frameworks?.claims || []);
    addClaims(profile, "strategy", profile.strategy?.claims || []);
    addClaims(profile, "evolution", profile.evolution?.claims || []);
    addClaims(profile, "contradiction", profile.contradictions || []);
    addClaims(profile, "vocabulary", profile.vocabulary || []);
    addClaims(profile, "decision_rule", profile.decision_rules || []);
    addClaims(profile, "risk_rule", profile.risk_rules || []);
  });
  return rows;
}

function traderIntelligenceCitationMarkup(citations = []) {
  return citations.slice(0, 4).map((citation) => {
    const label = `${citation.title || "Source"}${citation.timestamp ? ` · ${fmtRelativeTime(citation.timestamp)}` : ""}`;
    if (citation.source_id) {
      return `<button type="button" data-action="trader-intelligence-open-source" data-source-id="${citation.source_id}" title="${escapeHtml(citation.url || label)}">${escapeHtml(label)}</button>`;
    }
    return `<a href="${escapeHtml(citation.url || "#")}" target="_blank" rel="noreferrer">${escapeHtml(label)}</a>`;
  }).join("");
}

function traderIntelligenceClaimsMarkup(claims = [], limit = 4) {
  return claims.slice(0, limit).map((claim) => `
    <li>
      <p>${escapeHtml(claim.claim || "")}</p>
      <span class="ti-confidence" data-tone="${traderIntelligenceConfidenceTone(claim.confidence)}">${fmtPercent(claim.confidence || 0)} confidence</span>
      <div class="trader-intelligence-citations">${traderIntelligenceCitationMarkup(claim.citations || [])}</div>
    </li>
  `).join("") || "<li><p>No claims generated yet.</p></li>";
}

function traderIntelligenceSelectOptions(id, values, allLabel) {
  const select = document.getElementById(id);
  if (!select) {
    return;
  }
  const previous = select.value || "all";
  select.innerHTML = [
    `<option value="all">${escapeHtml(allLabel)}</option>`,
    ...values.map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(humanizeKey(value))}</option>`),
  ].join("");
  select.value = values.includes(previous) ? previous : "all";
}

function traderIntelligenceFilteredProfiles() {
  const filters = traderIntelligenceState.filters;
  const query = filters.query.toLowerCase();
  const profileMatches = (profile) => {
    const haystack = [
      profile.display_name,
      profile.category,
      profile.source_type,
      profile.source_url,
      profile.description,
      ...(profile.tags || []),
    ].join(" ").toLowerCase();
    const confidence = Number(profile.confidence_score || 0);
    const confidenceMatch = filters.confidence === "all"
      || (filters.confidence === "high" && confidence >= 0.7)
      || (filters.confidence === "medium" && confidence >= 0.45 && confidence < 0.7)
      || (filters.confidence === "low" && confidence < 0.45);
    return (!query || haystack.includes(query))
      && (filters.category === "all" || profile.category === filters.category)
      && (filters.status === "all" || profile.status === filters.status)
      && (filters.source === "all" || profile.source_type === filters.source)
      && confidenceMatch;
  };
  const sorted = traderIntelligenceState.profiles.filter(profileMatches);
  sorted.sort((a, b) => {
    if (filters.sort === "name") {
      return String(a.display_name || "").localeCompare(String(b.display_name || ""));
    }
    if (filters.sort === "confidence") {
      return Number(b.confidence_score || 0) - Number(a.confidence_score || 0);
    }
    if (filters.sort === "source_count") {
      return Number(b.source_count || 0) - Number(a.source_count || 0);
    }
    if (filters.sort === "insights") {
      return traderIntelligenceInsightCount(b) - traderIntelligenceInsightCount(a);
    }
    return String(b.last_analyzed_at || b.updated_at || "").localeCompare(String(a.last_analyzed_at || a.updated_at || ""));
  });
  return sorted;
}

function traderIntelligenceProgressMarkup(profile = null) {
  const stage = profile?.progress_stage || profile?.latest_run?.stage || "queued";
  const progress = Number(profile?.latest_run?.progress ?? (profile?.status === "completed" ? 1 : 0.08));
  const activeIndex = profile?.status === "completed"
    ? TRADER_INTELLIGENCE_PROGRESS_STEPS.length - 1
    : Math.max(0, TRADER_INTELLIGENCE_PROGRESS_STEPS.findIndex(([key]) => key === stage));
  return `
    <div class="ti-progress-bar" aria-label="Ingestion progress"><span style="width: ${Math.round(clamp(progress, 0, 1) * 100)}%"></span></div>
    <ul class="ti-progress-list">
      ${TRADER_INTELLIGENCE_PROGRESS_STEPS.map(([key, label], index) => `
        <li class="${index < activeIndex ? "is-done" : index === activeIndex ? "is-active" : ""}">
          <span class="ti-progress-dot"></span>
          <span>${escapeHtml(label)}</span>
          <small>${index < activeIndex ? "Done" : index === activeIndex ? escapeHtml(humanizeKey(stage)) : "Waiting"}</small>
        </li>
      `).join("")}
    </ul>
  `;
}

function renderTraderIntelligenceKpis(workspace) {
  const target = document.getElementById("trader-intelligence-kpis");
  if (!target) {
    return;
  }
  const profiles = workspace?.profiles || [];
  const completed = profiles.filter((profile) => profile.status === "completed").length;
  const sources = profiles.reduce((total, profile) => total + Number(profile.source_count || 0), 0);
  const insights = traderIntelligenceAllInsights(profiles).length;
  const averageConfidence = profiles.length
    ? profiles.reduce((total, profile) => total + Number(profile.confidence_score || 0), 0) / profiles.length
    : 0;
  target.innerHTML = `
    <article><span>Expert models</span><strong>${profiles.length}</strong><small>${completed} completed research brief(s)</small></article>
    <article><span>Evidence sources</span><strong>${sources.toLocaleString(currentLocale())}</strong><small>YouTube, URLs, docs, and manual sources</small></article>
    <article><span>Extracted insights</span><strong>${insights.toLocaleString(currentLocale())}</strong><small>Beliefs, rules, frameworks, contradictions</small></article>
    <article><span>Avg confidence</span><strong>${fmtPercent(averageConfidence)}</strong><small>Citation-weighted research confidence</small></article>
  `;
}

function renderTraderIntelligenceLibrary() {
  const rows = document.getElementById("trader-intelligence-library-rows");
  if (!rows) {
    return;
  }
  const profiles = traderIntelligenceFilteredProfiles();
  if (!profiles.length) {
    rows.innerHTML = `
      <tr>
        <td colspan="8">
          <div class="ti-empty-state">
            <strong>No expert models match this view</strong>
            <span>Add an expert or clear filters to build the research library.</span>
            <button class="button primary small-button" type="button" data-action="trader-intelligence-open-add">Add Expert</button>
          </div>
        </td>
      </tr>
    `;
    return;
  }
  rows.innerHTML = profiles.map((profile) => {
    const selected = Number(profile.id) === Number(traderIntelligenceState.selectedProfileId);
    const checked = traderIntelligenceState.selectedCompareIds.has(Number(profile.id));
    const insightCount = traderIntelligenceInsightCount(profile);
    const tags = (profile.tags || []).slice(0, 4).map((tag) => `<span class="ti-tag">${escapeHtml(tag)}</span>`).join("");
    return `
      <tr class="${selected ? "is-selected" : ""}">
        <td data-label="Expert">
          <div class="ti-expert-cell">
            <strong>${escapeHtml(profile.display_name)}</strong>
            <span>${escapeHtml(profile.description || profile.source_url || "No internal description")}</span>
            <div class="ti-tag-row">${tags}</div>
          </div>
        </td>
        <td data-label="Category">${escapeHtml(humanizeKey(profile.category))}</td>
        <td data-label="Sources">
          <div class="ti-source-chip-row">
            <span class="ti-source-chip">${escapeHtml(humanizeKey(profile.source_type))}</span>
            <span class="ti-source-chip">${Number(profile.source_count || 0)} indexed</span>
          </div>
        </td>
        <td data-label="Insights">${insightCount}</td>
        <td data-label="Status"><span class="ti-status" data-tone="${traderIntelligenceStatusTone(profile.status)}">${escapeHtml(humanizeKey(profile.status))}</span></td>
        <td data-label="Confidence"><span class="ti-confidence" data-tone="${traderIntelligenceConfidenceTone(profile.confidence_score)}">${fmtPercent(profile.confidence_score || 0)}</span></td>
        <td data-label="Last analyzed">${profile.last_analyzed_at ? fmtRelativeTime(profile.last_analyzed_at) : "Not analyzed"}</td>
        <td data-label="Actions">
          <div class="ti-actions">
            <input type="checkbox" aria-label="Compare ${escapeHtml(profile.display_name)}" data-action="trader-intelligence-toggle-compare" data-profile-id="${profile.id}" ${checked ? "checked" : ""}>
            <button class="button secondary" type="button" data-action="trader-intelligence-select" data-profile-id="${profile.id}">View</button>
            <button class="button ghost" type="button" data-action="trader-intelligence-rerun" data-profile-id="${profile.id}" ${disabledAttr(!workspaceEditable())}>Rerun</button>
            <button class="button ghost" type="button" data-action="trader-intelligence-delete" data-profile-id="${profile.id}" ${disabledAttr(!workspaceEditable())}>Delete</button>
          </div>
        </td>
      </tr>
    `;
  }).join("");
}

function traderIntelligenceProfileTabs() {
  const tabs = [
    ["overview", "Overview"],
    ["worldview", "Worldview"],
    ["frameworks", "Frameworks"],
    ["strategy", "Strategy"],
    ["contradictions", "Contradictions"],
    ["evolution", "Evolution"],
    ["sources", "Sources"],
    ["ask", "Ask"],
  ];
  return `
    <div class="ti-profile-tabs" role="tablist" aria-label="Expert profile sections">
      ${tabs.map(([key, label]) => `
        <button class="${traderIntelligenceState.profileTab === key ? "active" : ""}" type="button" role="tab" aria-selected="${traderIntelligenceState.profileTab === key}" data-action="trader-intelligence-profile-tab" data-ti-profile-tab="${key}">${label}</button>
      `).join("")}
    </div>
  `;
}

function traderIntelligenceInsightCard(title, summary, claims = [], limit = 4) {
  return `
    <article class="ti-insight-card">
      <span class="ti-card-label">${escapeHtml(title)}</span>
      <p>${escapeHtml(summary || "No summary generated yet.")}</p>
      <ul>${traderIntelligenceClaimsMarkup(claims, limit)}</ul>
    </article>
  `;
}

function renderTraderIntelligenceProfile() {
  const shell = document.getElementById("trader-intelligence-profile-shell");
  if (!shell) {
    return;
  }
  const selected = traderIntelligenceProfileById(traderIntelligenceState.selectedProfileId);
  if (!selected) {
    shell.innerHTML = `
      <div class="ti-empty-state">
        <strong>No expert selected</strong>
        <span>Select an expert from the library or add a new model.</span>
        <button class="button primary small-button" type="button" data-action="trader-intelligence-open-add">Add Expert</button>
      </div>
    `;
    return;
  }
  const answer = traderIntelligenceState.askAnswers.get(Number(selected.id));
  const header = `
    <div class="ti-profile-header">
      <div>
        <p class="eyebrow">${escapeHtml(humanizeKey(selected.category))} model</p>
        <h4>${escapeHtml(selected.display_name)}</h4>
        <p class="panel-note">${escapeHtml(selected.description || selected.synthesis?.summary || "Research profile generated from public content.")}</p>
        <div class="ti-tag-row">${(selected.tags || []).map((tag) => `<span class="ti-tag">${escapeHtml(tag)}</span>`).join("")}</div>
      </div>
      <div class="ti-profile-metrics">
        <article><span class="ti-metric-label">Status</span><strong>${escapeHtml(humanizeKey(selected.status))}</strong><small>${escapeHtml(humanizeKey(selected.progress_stage))}</small></article>
        <article><span class="ti-metric-label">Confidence</span><strong>${fmtPercent(selected.confidence_score || 0)}</strong><small>Citation-backed</small></article>
        <article><span class="ti-metric-label">Sources</span><strong>${selected.source_count}</strong><small>${escapeHtml(humanizeKey(selected.source_type))}</small></article>
        <article><span class="ti-metric-label">Insights</span><strong>${traderIntelligenceInsightCount(selected)}</strong><small>Extracted claims</small></article>
      </div>
    </div>
  `;
  const sidePanel = `
    <aside class="ti-progress-panel">
      <span class="ti-card-label">Ingestion progress</span>
      ${traderIntelligenceProgressMarkup(selected)}
      <span class="ti-card-label">Source context</span>
      <div class="ti-source-chip-row">
        ${(selected.sources || []).slice(0, 5).map((source) => `<button class="ti-source-chip" type="button" data-action="trader-intelligence-open-source" data-source-id="${source.id}">${escapeHtml(source.title)}</button>`).join("") || "<span class=\"ti-source-chip\">No sources indexed</span>"}
      </div>
      ${(selected.warnings || []).slice(0, 4).map((warning) => `<p>${escapeHtml(warning)}</p>`).join("")}
    </aside>
  `;
  const tab = traderIntelligenceState.profileTab;
  let content = "";
  if (tab === "worldview") {
    content = `<div class="ti-insight-grid">${traderIntelligenceInsightCard("Strongest beliefs", selected.worldview?.summary, selected.worldview?.claims)}${traderIntelligenceInsightCard("Belief changes", selected.evolution?.summary, selected.evolution?.claims)}</div>`;
  } else if (tab === "frameworks") {
    content = `<div class="ti-insight-grid">${traderIntelligenceInsightCard("Recurring frameworks", selected.frameworks?.summary, selected.frameworks?.claims)}${traderIntelligenceInsightCard("Decision rules", "Rules and heuristics extracted from the indexed source set.", selected.decision_rules)}${traderIntelligenceInsightCard("Risk rules", "Risk management patterns detected in the source set.", selected.risk_rules)}${traderIntelligenceInsightCard("Vocabulary map", "Repeated terms and conceptual vocabulary.", selected.vocabulary, 6)}</div>`;
  } else if (tab === "strategy") {
    content = `<div class="ti-insight-grid">${traderIntelligenceInsightCard("Strategy style", selected.strategy?.summary, selected.strategy?.claims)}${traderIntelligenceInsightCard("Recommendations", "Research actions before trusting or paper-following this expert.", selected.recommendations)}${traderIntelligenceInsightCard("Synthesis", selected.synthesis?.summary, selected.synthesis?.claims)}${traderIntelligenceInsightCard("Conflicts and monetization", "Promotions, sponsorships, and visible conflicts should be reviewed manually.", selected.strategy?.claims || [])}</div>`;
  } else if (tab === "contradictions") {
    content = `<div class="ti-insight-grid">${traderIntelligenceInsightCard("Contradictory statements", "Detected contradictions or current absence of direct contradictions.", selected.contradictions, 8)}${traderIntelligenceInsightCard("Interpretation", "Contradictions become research prompts, not trade instructions.", selected.risk_rules)}</div>`;
  } else if (tab === "evolution") {
    content = `<div class="ti-insight-grid">${traderIntelligenceInsightCard("Evolution timeline", selected.evolution?.summary, selected.evolution?.claims)}${traderIntelligenceInsightCard("Latest synthesis", selected.synthesis?.summary, selected.synthesis?.claims)}</div>`;
  } else if (tab === "sources") {
    content = `
      <article class="ti-source-table-card">
        <span class="ti-card-label">Source library</span>
        <div class="trader-intelligence-table-wrap">
          <table class="trader-intelligence-table">
            <thead><tr><th>Source</th><th>Type</th><th>Transcript</th><th>Imported</th><th>Action</th></tr></thead>
            <tbody>
              ${(selected.sources || []).map((source) => `
                <tr>
                  <td data-label="Source"><strong>${escapeHtml(source.title)}</strong><br><span>${escapeHtml(source.summary || "")}</span></td>
                  <td data-label="Type">${escapeHtml(humanizeKey(source.source_type))}</td>
                  <td data-label="Transcript">${source.transcript_available ? "Available" : "Missing"}</td>
                  <td data-label="Imported">${fmtRelativeTime(source.created_at)}</td>
                  <td data-label="Action"><button class="button secondary small-button" type="button" data-action="trader-intelligence-open-source" data-source-id="${source.id}">Open source</button></td>
                </tr>
              `).join("") || "<tr><td colspan=\"5\">No sources indexed yet.</td></tr>"}
            </tbody>
          </table>
        </div>
      </article>
    `;
  } else if (tab === "ask") {
    content = `
      <article class="ti-ask-panel">
        <span class="ti-card-label">Ask this expert</span>
        <form id="trader-intelligence-ask-form" class="trader-intelligence-ask-form">
          <input id="trader-intelligence-ask-input" type="search" maxlength="800" placeholder="What would this trader likely say about Bitcoin risk right now?">
          <button class="button primary small-button" type="submit">Ask</button>
        </form>
        <p>Answers are AI-generated from indexed public evidence and citations. They are research outputs, not financial advice.</p>
        ${answer ? `
          <div class="ti-ask-answer">
            <strong>${escapeHtml(answer.question)}</strong>
            <p>${escapeHtml(answer.answer)}</p>
            <span class="ti-confidence" data-tone="${traderIntelligenceConfidenceTone(answer.confidence)}">${fmtPercent(answer.confidence || 0)} confidence</span>
            <div class="trader-intelligence-citations">${traderIntelligenceCitationMarkup(answer.citations || [])}</div>
            ${(answer.warnings || []).map((warning) => `<p>${escapeHtml(warning)}</p>`).join("")}
          </div>
        ` : ""}
      </article>
    `;
  } else {
    content = `
      <div class="ti-insight-grid">
        ${traderIntelligenceInsightCard("One-page synthesis", selected.synthesis?.summary, selected.synthesis?.claims)}
        ${traderIntelligenceInsightCard("Strongest opinions", selected.worldview?.summary, selected.worldview?.claims)}
        ${traderIntelligenceInsightCard("Top decision rules", "Rules and heuristics extracted from the indexed source set.", selected.decision_rules)}
        ${traderIntelligenceInsightCard("Risk philosophy", "Risk posture and live-execution boundaries.", selected.risk_rules)}
        ${traderIntelligenceInsightCard("Source recommendations", "Best sources to inspect before trusting the brief.", selected.recommendations)}
        ${traderIntelligenceInsightCard("Hidden insights", selected.synthesis?.summary, (selected.synthesis?.claims || []).slice(1))}
      </div>
    `;
  }
  shell.innerHTML = `
    <div class="ti-profile-shell">
      ${header}
      ${traderIntelligenceProfileTabs()}
      <div class="ti-profile-grid">
        <main>${content}</main>
        ${sidePanel}
      </div>
    </div>
  `;
  const askForm = document.getElementById("trader-intelligence-ask-form");
  if (askForm) {
    askForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const question = document.getElementById("trader-intelligence-ask-input")?.value?.trim();
      if (!question) {
        setStatus("Ask-this-expert needs a question.");
        return;
      }
      await askTraderIntelligence(question);
    });
  }
}

function renderTraderIntelligenceCompare() {
  const selector = document.getElementById("trader-intelligence-compare-selector");
  const output = document.getElementById("trader-intelligence-compare-output");
  if (!selector || !output) {
    return;
  }
  selector.innerHTML = `
    <div class="ti-compare-selector">
      ${traderIntelligenceState.profiles.map((profile) => `
        <label>
          <input type="checkbox" data-action="trader-intelligence-toggle-compare" data-profile-id="${profile.id}" ${traderIntelligenceState.selectedCompareIds.has(Number(profile.id)) ? "checked" : ""}>
          <span>${escapeHtml(profile.display_name)} · ${fmtPercent(profile.confidence_score || 0)}</span>
        </label>
      `).join("") || "<p class=\"panel-note\">Add at least two experts before running a comparison.</p>"}
    </div>
  `;
  const comparison = traderIntelligenceState.comparison;
  if (!comparison) {
    output.innerHTML = `
      <div class="ti-empty-state">
        <strong>No comparison run yet</strong>
        <span>Select 2 to 5 experts and run a comparison.</span>
      </div>
    `;
    return;
  }
  output.innerHTML = `
    <div class="ti-compare-shell">
      <p class="panel-note">${escapeHtml(comparison.summary || "")}</p>
      <div class="ti-compare-grid">
        <article class="ti-compare-card"><h5>Agreements</h5><ul>${traderIntelligenceClaimsMarkup(comparison.agreement_points || [], 5)}</ul></article>
        <article class="ti-compare-card"><h5>Disagreements</h5><ul>${traderIntelligenceClaimsMarkup(comparison.disagreement_points || [], 5)}</ul></article>
        <article class="ti-compare-card"><h5>Unique frameworks</h5><ul>${traderIntelligenceClaimsMarkup(comparison.unique_edges || [], 5)}</ul></article>
        <article class="ti-compare-card"><h5>Research gaps</h5><ul>${traderIntelligenceClaimsMarkup(comparison.opportunity_gaps || [], 5)}</ul></article>
      </div>
      ${(comparison.warnings || []).map((warning) => `<p>${escapeHtml(warning)}</p>`).join("")}
    </div>
  `;
}

function renderTraderIntelligenceInsights() {
  const rows = document.getElementById("trader-intelligence-insight-rows");
  if (!rows) {
    return;
  }
  const filters = traderIntelligenceState.filters;
  const query = filters.insightQuery.toLowerCase();
  const visible = traderIntelligenceAllInsights().filter(({ profile, type, claim }) => {
    const confidence = Number(claim.confidence || 0);
    const confidenceMatch = filters.insightConfidence === "all"
      || (filters.insightConfidence === "high" && confidence >= 0.7)
      || (filters.insightConfidence === "medium" && confidence >= 0.45 && confidence < 0.7)
      || (filters.insightConfidence === "low" && confidence < 0.45);
    const haystack = `${profile.display_name} ${profile.category} ${type} ${claim.claim}`.toLowerCase();
    return (!query || haystack.includes(query))
      && (filters.insightType === "all" || type === filters.insightType)
      && confidenceMatch;
  });
  rows.innerHTML = visible.map(({ profile, type, claim }) => `
    <tr>
      <td data-label="Insight"><strong>${escapeHtml(claim.claim || "")}</strong></td>
      <td data-label="Expert">${escapeHtml(profile.display_name)}</td>
      <td data-label="Type">${escapeHtml(humanizeKey(type))}</td>
      <td data-label="Confidence"><span class="ti-confidence" data-tone="${traderIntelligenceConfidenceTone(claim.confidence)}">${fmtPercent(claim.confidence || 0)}</span></td>
      <td data-label="Citations"><div class="trader-intelligence-citations">${traderIntelligenceCitationMarkup(claim.citations || [])}</div></td>
    </tr>
  `).join("") || `
    <tr><td colspan="5"><div class="ti-empty-state"><strong>No insights found</strong><span>Change filters or add more expert models.</span></div></td></tr>
  `;
}

function renderTraderIntelligenceTabs() {
  document.querySelectorAll("[data-action='trader-intelligence-main-tab']").forEach((button) => {
    const active = button.dataset.tiTab === traderIntelligenceState.activeTab;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
  });
  ["library", "profile", "compare", "insights"].forEach((tab) => {
    const view = document.getElementById(`trader-intelligence-${tab}-view`);
    if (view) {
      view.classList.toggle("hidden", traderIntelligenceState.activeTab !== tab);
    }
  });
}

function renderTraderIntelligence(workspace) {
  const section = document.getElementById("trader-intelligence-section");
  const badge = document.getElementById("trader-intelligence-badge");
  const summary = document.getElementById("trader-intelligence-summary");
  if (!section || !workspace) {
    return;
  }
  const profiles = workspace.profiles || [];
  traderIntelligenceState.workspace = workspace;
  traderIntelligenceState.profiles = profiles;
  if (!traderIntelligenceState.selectedProfileId && profiles.length) {
    traderIntelligenceState.selectedProfileId = profiles[0].id;
  }
  if (traderIntelligenceState.selectedProfileId && !profiles.some((profile) => Number(profile.id) === Number(traderIntelligenceState.selectedProfileId))) {
    traderIntelligenceState.selectedProfileId = profiles[0]?.id || null;
  }
  const completed = profiles.filter((profile) => profile.status === "completed").length;
  if (badge) {
    badge.textContent = `${profiles.length} model${profiles.length === 1 ? "" : "s"} · ${completed} complete`;
    badge.dataset.variant = completed ? "positive" : "warning";
  }
  if (summary) {
    summary.textContent = workspace.summary || "Trader Intelligence is ready.";
  }
  traderIntelligenceSelectOptions(
    "trader-intelligence-filter-category",
    [...new Set(profiles.map((profile) => profile.category).filter(Boolean))].sort(),
    "All categories",
  );
  traderIntelligenceSelectOptions(
    "trader-intelligence-filter-source",
    [...new Set(profiles.map((profile) => profile.source_type).filter(Boolean))].sort(),
    "All source types",
  );
  renderTraderIntelligenceKpis(workspace);
  renderTraderIntelligenceTabs();
  renderTraderIntelligenceLibrary();
  renderTraderIntelligenceProfile();
  renderTraderIntelligenceCompare();
  renderTraderIntelligenceInsights();
}

async function loadTraderIntelligence() {
  if (!document.getElementById("trader-intelligence-section")) {
    return;
  }
  try {
    const workspace = await fetchJson("/api/me/trader-intelligence");
    renderTraderIntelligence(workspace);
  } catch (error) {
    const summary = document.getElementById("trader-intelligence-summary");
    if (summary) {
      summary.textContent = error.message;
    }
  }
}

function openTraderIntelligenceAddModal() {
  const modal = document.getElementById("trader-intelligence-add-modal");
  if (modal) {
    modal.classList.remove("hidden");
    document.getElementById("trader-intelligence-name")?.focus({ preventScroll: true });
  }
}

function closeTraderIntelligenceAddModal() {
  document.getElementById("trader-intelligence-add-modal")?.classList.add("hidden");
}

function openTraderIntelligenceSourceDrawer(sourceId) {
  const source = traderIntelligenceState.profiles
    .flatMap((profile) => profile.sources || [])
    .find((item) => Number(item.id) === Number(sourceId));
  const drawer = document.getElementById("trader-intelligence-source-drawer");
  const content = document.getElementById("trader-intelligence-source-content");
  if (!drawer || !content || !source) {
    return;
  }
  content.innerHTML = `
    <div class="ti-source-head">
      <div>
        <p class="eyebrow">${escapeHtml(humanizeKey(source.source_type))}</p>
        <h3 id="trader-intelligence-source-title">${escapeHtml(source.title)}</h3>
        <p>${escapeHtml(source.summary || "No source summary available.")}</p>
      </div>
      <button class="button ghost small-button" type="button" data-action="trader-intelligence-close-source">Close</button>
    </div>
    <div class="ti-profile-metrics">
      <article><span class="ti-metric-label">Transcript</span><strong>${source.transcript_available ? "Available" : "Missing"}</strong><small>Content extraction status</small></article>
      <article><span class="ti-metric-label">Imported</span><strong>${fmtRelativeTime(source.created_at)}</strong><small>${escapeHtml(source.observed_at || "")}</small></article>
    </div>
    <div class="ti-source-chip-row">
      <span class="ti-source-chip">${escapeHtml(source.author || "Unknown author")}</span>
      <span class="ti-source-chip">${escapeHtml(source.external_id || "source")}</span>
      ${source.url ? `<a class="ti-source-chip" href="${escapeHtml(source.url)}" target="_blank" rel="noreferrer">Open original</a>` : ""}
    </div>
    <pre class="ti-source-json">${escapeHtml(JSON.stringify(source.metadata || {}, null, 2))}</pre>
  `;
  drawer.classList.remove("hidden");
}

function closeTraderIntelligenceSourceDrawer() {
  document.getElementById("trader-intelligence-source-drawer")?.classList.add("hidden");
}

async function createTraderIntelligenceProfile(form) {
  if (!requireEditable()) {
    return;
  }
  const name = document.getElementById("trader-intelligence-name")?.value?.trim();
  const category = document.getElementById("trader-intelligence-category")?.value || "trader";
  const sourceType = document.getElementById("trader-intelligence-source-type")?.value || "youtube_channel";
  const sourceUrl = document.getElementById("trader-intelligence-source-url")?.value?.trim();
  const description = document.getElementById("trader-intelligence-description")?.value?.trim();
  const tags = (document.getElementById("trader-intelligence-tags")?.value || "")
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean);
  const maxSources = Number(document.getElementById("trader-intelligence-max-sources")?.value || 12);
  if (!name || !sourceUrl) {
    setStatus("Add an expert name and source before extracting the expert model.");
    return;
  }
  const progress = document.getElementById("trader-intelligence-progress");
  if (progress) {
    progress.innerHTML = traderIntelligenceProgressMarkup({ progress_stage: "importing", latest_run: { progress: 0.22 } });
  }
  setStatus(`Extracting expert model for ${name}...`);
  const profile = await fetchJson("/api/me/trader-intelligence", {
    method: "POST",
    body: JSON.stringify({
      name,
      category,
      source_type: sourceType,
      source_url: sourceUrl,
      description,
      tags,
      max_sources: maxSources,
    }),
  });
  traderIntelligenceState.selectedProfileId = profile.id;
  traderIntelligenceState.selectedCompareIds.add(Number(profile.id));
  traderIntelligenceState.activeTab = "profile";
  traderIntelligenceState.profileTab = "overview";
  form?.reset();
  closeTraderIntelligenceAddModal();
  await loadTraderIntelligence();
  setStatus(`Trader Intelligence brief completed for ${profile.display_name}.`);
}

async function rerunTraderIntelligence(profileId) {
  if (!requireEditable()) {
    return;
  }
  const profile = traderIntelligenceProfileById(profileId);
  const confirmed = window.confirm(`Rerun analysis for ${profile?.display_name || "this expert"}? Existing brief fields will be refreshed from indexed sources.`);
  if (!confirmed) {
    return;
  }
  setStatus("Rerunning the four-pass expert analysis...");
  const updated = await fetchJson(`/api/me/trader-intelligence/${profileId}/rerun`, { method: "POST" });
  traderIntelligenceState.selectedProfileId = updated.id;
  traderIntelligenceState.activeTab = "profile";
  await loadTraderIntelligence();
  setStatus(`Updated expert model: ${updated.display_name}.`);
}

async function deleteTraderIntelligenceProfile(profileId) {
  if (!requireEditable()) {
    return;
  }
  const profile = traderIntelligenceProfileById(profileId);
  const confirmed = window.confirm(`Delete ${profile?.display_name || "this expert model"} and its indexed sources?`);
  if (!confirmed) {
    return;
  }
  await fetchJson(`/api/me/trader-intelligence/${profileId}`, { method: "DELETE" });
  traderIntelligenceState.selectedCompareIds.delete(Number(profileId));
  traderIntelligenceState.selectedProfileId = null;
  await loadTraderIntelligence();
  setStatus("Expert model deleted.");
}

async function askTraderIntelligence(question) {
  if (!requireEditable()) {
    return;
  }
  const profileId = traderIntelligenceState.selectedProfileId;
  if (!profileId) {
    setStatus("Select an expert model first.");
    return;
  }
  setStatus("Generating cited expert answer...");
  const answer = await fetchJson(`/api/me/trader-intelligence/${profileId}/ask`, {
    method: "POST",
    body: JSON.stringify({ question }),
  });
  traderIntelligenceState.askAnswers.set(Number(profileId), answer);
  traderIntelligenceState.profileTab = "ask";
  renderTraderIntelligence(traderIntelligenceState.workspace);
  setStatus("Ask-this-expert answer generated with citations.");
}

async function compareTraderIntelligence() {
  if (!requireEditable()) {
    return;
  }
  const profileIds = [...traderIntelligenceState.selectedCompareIds].slice(0, 5);
  if (profileIds.length < 2) {
    setStatus("Select 2 to 5 expert models for comparison.");
    return;
  }
  setStatus("Running expert comparison...");
  const comparison = await fetchJson("/api/me/trader-intelligence/compare", {
    method: "POST",
    body: JSON.stringify({ profile_ids: profileIds }),
  });
  traderIntelligenceState.comparison = comparison;
  traderIntelligenceState.activeTab = "compare";
  renderTraderIntelligence(traderIntelligenceState.workspace);
  setStatus("Expert comparison completed.");
}

function renderSimulationMultiSeriesChart(targetId, primaryPoints, secondaryPoints, options = {}) {
  const container = document.getElementById(targetId);
  if (!container || !window.LightweightCharts) {
    return;
  }
  destroyChart(targetId);
  container.innerHTML = "";

  const primaryData = normalizeChartPoints(primaryPoints || []);
  const secondaryData = normalizeChartPoints(secondaryPoints || []);
  if (!primaryData.length) {
    container.innerHTML = '<p class="panel-note">No simulation chart data is available yet.</p>';
    return;
  }

  const chart = window.LightweightCharts.createChart(container, {
    width: Math.max(container.clientWidth, 320),
    height: options.height || 320,
    layout: {
      background: { color: "transparent" },
      textColor: "#5a6a75",
      fontFamily: '"Avenir Next", "Franklin Gothic Book", "Trebuchet MS", sans-serif',
    },
    grid: {
      vertLines: { color: "rgba(16, 38, 54, 0.08)" },
      horzLines: { color: "rgba(16, 38, 54, 0.08)" },
    },
    rightPriceScale: {
      borderColor: "rgba(16, 38, 54, 0.12)",
    },
    timeScale: {
      borderColor: "rgba(16, 38, 54, 0.12)",
      timeVisible: true,
      secondsVisible: false,
    },
  });

  const primarySeries = chart.addSeries(window.LightweightCharts.LineSeries, {
    color: options.primaryColor || "#1f7a78",
    lineWidth: 3,
    priceLineVisible: false,
  });
  primarySeries.setData(primaryData);

  if (secondaryData.length) {
    const secondarySeries = chart.addSeries(window.LightweightCharts.LineSeries, {
      color: options.secondaryColor || "#c46a37",
      lineWidth: 2,
      priceLineVisible: false,
    });
    secondarySeries.setData(secondaryData);
  }

  chart.timeScale().fitContent();
  chartInstances.set(targetId, chart);
}

function renderSimulationChart(result) {
  if (!result?.selected_result) {
    return;
  }
  renderSimulationMultiSeriesChart(
    "simulation-equity-chart",
    result.selected_result.equity_curve,
    result.benchmark_curve,
    {
      primaryColor: "#1f7a78",
      secondaryColor: "#c46a37",
      height: 340,
    },
  );
  renderSimulationMultiSeriesChart(
    "simulation-drawdown-chart",
    result.selected_result.drawdown_curve,
    [],
    {
      primaryColor: "#18354a",
      height: 240,
    },
  );
}

function renderWalletIntelligence(snapshot, targetId = "wallet-intelligence-list", summaryId = "wallet-intelligence-summary") {
  const container = document.getElementById(targetId);
  const summary = document.getElementById(summaryId);
  if (summary) {
    summary.textContent = snapshot?.summary || "Wallet intelligence is waiting on the next refresh window.";
  }
  if (!container) {
    return;
  }
  if (!snapshot?.wallets?.length) {
    container.innerHTML = '<p class="panel-note">No wallet intelligence is available yet.</p>';
    return;
  }
  container.innerHTML = snapshot.wallets.map((wallet, index) => `
    <article class="wallet-watch-card ${wallet.smart_money_score >= 0.75 ? "tone-high" : (wallet.smart_money_score >= 0.6 ? "tone-mid" : "tone-low")}">
      <div class="wallet-watch-head">
        <div>
          <span class="wallet-rank">Wallet ${index + 1}</span>
          <h4>${wallet.display_name}</h4>
        </div>
        <span class="badge">${wallet.primary_asset || "Multi-asset"}</span>
      </div>
      <p>${wallet.bio || "Public trader profile observed through venue activity and recent closed positions."}</p>
      <div class="wallet-stat-row">
        <div>
          <span>Smart money</span>
          <strong>${fmtPercent(wallet.smart_money_score)}</strong>
        </div>
        <div>
          <span>Conviction</span>
          <strong>${fmtPercent(wallet.conviction_score)}</strong>
        </div>
        <div>
          <span>Bias</span>
          <strong>${wallet.net_bias >= 0 ? "Net buyer" : "Net seller"}</strong>
        </div>
      </div>
      <div class="wallet-stat-row">
        <div>
          <span>Portfolio</span>
          <strong>${fmtCompactNumber(wallet.portfolio_value)}</strong>
        </div>
        <div>
          <span>30d P&L</span>
          <strong>${wallet.realized_pnl_30d >= 0 ? "+" : ""}${fmtCompactNumber(wallet.realized_pnl_30d)}</strong>
        </div>
        <div>
          <span>Win rate</span>
          <strong>${fmtPercent(wallet.win_rate)}</strong>
        </div>
      </div>
      <div class="asset-meter-group">
        <div>
          <span>Buy ratio</span>
          <div class="asset-meter"><i style="width:${(clamp(wallet.buy_ratio, 0, 1) * 100).toFixed(2)}%"></i></div>
        </div>
      </div>
      <ul class="wallet-market-list">
        ${(wallet.recent_markets || []).slice(0, 3).map((market) => `<li>${market}</li>`).join("") || "<li>No recent market labels available</li>"}
      </ul>
    </article>
  `).join("");
}

function renderEdgeSnapshot(snapshot, targetId = "edge-opportunity-list", summaryId = "edge-summary") {
  const container = document.getElementById(targetId);
  const summary = document.getElementById(summaryId);
  if (summary) {
    summary.textContent = snapshot?.summary || "Edge surfaces are waiting on the next refresh window.";
  }
  if (!container) {
    return;
  }
  if (!snapshot?.opportunities?.length) {
    container.innerHTML = '<p class="panel-note">No market edge opportunities are available yet.</p>';
    return;
  }
  container.innerHTML = snapshot.opportunities.map((opportunity) => `
    <article class="edge-card ${Math.abs(opportunity.edge_bps) >= 120 ? "tone-high" : "tone-mid"}">
      <div class="edge-card-head">
        <div>
          <span>${opportunity.market_source}</span>
          <h4>${opportunity.asset}</h4>
        </div>
        <span class="confidence-chip stance-${opportunity.stance}">${opportunity.stance}</span>
      </div>
      <p>${opportunity.market_label}</p>
      <div class="edge-kpis">
        <div>
          <span>Implied</span>
          <strong>${fmtPercent(opportunity.implied_probability, 1)}</strong>
        </div>
        <div>
          <span>Fair</span>
          <strong>${fmtPercent(opportunity.fair_probability, 1)}</strong>
        </div>
        <div>
          <span>Edge</span>
          <strong>${fmtBps(opportunity.edge_bps)}</strong>
        </div>
      </div>
      <div class="edge-kpis edge-kpis-secondary">
        <div>
          <span>Confidence</span>
          <strong>${fmtPercent(opportunity.confidence)}</strong>
        </div>
        <div>
          <span>Liquidity</span>
          <strong>${fmtCompactNumber(opportunity.liquidity)}</strong>
        </div>
        <div>
          <span>24h volume</span>
          <strong>${fmtCompactNumber(opportunity.volume_24h)}</strong>
        </div>
      </div>
      <ul class="edge-signal-list">
        ${(opportunity.supporting_signals || []).map((item) => `<li>${item}</li>`).join("")}
      </ul>
      <small>Updated ${fmtRelativeTime(opportunity.updated_at)}</small>
    </article>
  `).join("");
}

function renderSimulationContext(asset, edgeSnapshot, walletSnapshot) {
  const edgeCard = document.getElementById("simulation-edge-card");
  const walletCard = document.getElementById("simulation-wallet-card");
  const summary = document.getElementById("simulation-edge-summary");
  const edge = edgeSnapshot?.opportunities?.find((item) => item.asset === asset);
  const wallets = (walletSnapshot?.wallets || []).filter((wallet) => wallet.primary_asset === asset);

  if (summary) {
    summary.textContent = edge
      ? `${asset} is currently showing ${fmtBps(edge.edge_bps)} of modeled dislocation versus venue pricing with ${wallets.length} relevant smart-wallet profiles.`
      : `${asset} does not have a direct edge surface match right now, but the wallet and macro overlays are still available.`;
  }

  if (edgeCard) {
    edgeCard.innerHTML = edge ? `
      <article class="context-card ${Math.abs(edge.edge_bps) >= 120 ? "tone-high" : "tone-mid"}">
        <span>Edge surface</span>
        <h4>${edge.market_label}</h4>
        <p>${edge.market_source} · ${fmtBps(edge.edge_bps)} · confidence ${fmtPercent(edge.confidence)}</p>
        <div class="edge-kpis">
          <div><span>Implied</span><strong>${fmtPercent(edge.implied_probability, 1)}</strong></div>
          <div><span>Fair</span><strong>${fmtPercent(edge.fair_probability, 1)}</strong></div>
          <div><span>Stance</span><strong>${edge.stance}</strong></div>
        </div>
        <ul class="edge-signal-list">
          ${(edge.supporting_signals || []).map((item) => `<li>${item}</li>`).join("")}
        </ul>
      </article>
    ` : `
      <article class="context-card">
        <span>Edge surface</span>
        <h4>No direct market dislocation</h4>
        <p>There is no active pricing mismatch for ${asset} in the current research layer.</p>
      </article>
    `;
  }

  if (walletCard) {
    walletCard.innerHTML = wallets.length ? wallets.slice(0, 2).map((wallet) => `
      <article class="context-card ${wallet.smart_money_score >= 0.75 ? "tone-high" : "tone-mid"}">
        <span>Wallet overlay</span>
        <h4>${wallet.display_name}</h4>
        <p>${fmtPercent(wallet.smart_money_score)} smart-money score · ${wallet.net_bias >= 0 ? "buyer" : "seller"} bias · ${fmtPercent(wallet.win_rate)} win rate</p>
        <ul class="wallet-market-list">
          ${(wallet.recent_markets || []).slice(0, 3).map((market) => `<li>${market}</li>`).join("")}
        </ul>
      </article>
    `).join("") : `
      <article class="context-card">
        <span>Wallet overlay</span>
        <h4>No asset-specific wallet profile</h4>
        <p>The current wallet watchlist does not include a primary ${asset} profile yet.</p>
      </article>
    `;
  }
}

function renderAdvancedExport(exportBundle) {
  const summary = document.getElementById("advanced-export-summary");
  const card = document.getElementById("advanced-export-card");
  const preview = document.getElementById("advanced-export-preview");
  latestAdvancedExport = exportBundle;

  if (!exportBundle) {
    if (summary) {
      summary.textContent = "Generate an export bundle to package the simulation, edge model, and wallet context together.";
    }
    if (card) {
      card.innerHTML = "";
    }
    if (preview) {
      preview.textContent = "No export generated yet.";
    }
    return;
  }

  if (summary) {
    summary.textContent = exportBundle.summary;
  }
  if (card) {
    const storageState = exportBundle.saved_to_disk ? "Saved artifact" : "Preview only";
    const storageNote = exportBundle.saved_to_disk
      ? "Artifact saved to disk and added to the recent export history."
      : "Artifact is available only in the current preview session.";
    card.innerHTML = `
      <div><span>File</span><strong>${exportBundle.filename}</strong></div>
      <div><span>Engine</span><strong>${exportBundle.engine_target}</strong></div>
      <div><span>Generated</span><strong>${fmtDateTime(exportBundle.generated_at)}</strong></div>
      <div><span>Status</span><strong>${storageState}</strong></div>
      ${exportBundle.filesystem_path ? `<div><span>Saved path</span><strong class="advanced-export-path">${exportBundle.filesystem_path}</strong></div>` : ""}
      <footer class="advanced-export-actions">
        ${exportBundle.download_url ? `<a class="button secondary" href="${exportBundle.download_url}" download>Download JSON</a>` : ""}
        ${exportBundle.package_download_url ? `<a class="button secondary" href="${exportBundle.package_download_url}" download>Download Adapter Pack</a>` : ""}
        <p class="panel-note">${storageNote}</p>
      </footer>
    `;
  }
  if (preview) {
    preview.textContent = JSON.stringify(exportBundle.payload, null, 2);
  }
}

function renderSimulationExportHistory(artifacts) {
  const historyList = document.getElementById("simulation-export-history");
  if (!historyList) {
    return;
  }

  if (!artifacts?.length) {
    historyList.innerHTML = `
      <li>
        <div>
          <strong>No saved exports yet</strong>
          <p>Generate an advanced export to create a reusable Strategy Lab artifact.</p>
        </div>
      </li>
    `;
    return;
  }

  historyList.innerHTML = artifacts.map((artifact) => `
    <li>
      <div>
        <strong>${artifact.asset} · ${artifact.strategy_id}</strong>
        <p>${artifact.filename}</p>
        <small>${artifact.lookback_years}y window · ${artifact.engine_target} · ${fmtFileSize(artifact.size_bytes)} · ${fmtRelativeTime(artifact.generated_at)}</small>
      </div>
      <div class="workspace-actions export-history-actions">
        <span>${fmtDateTime(artifact.generated_at)}</span>
        <div class="export-link-stack">
          <a class="text-link" href="${artifact.download_url}" download>Download JSON</a>
          ${artifact.package_download_url ? `<a class="text-link" href="${artifact.package_download_url}" download>Adapter pack</a>` : ""}
        </div>
      </div>
    </li>
  `).join("");
}

function populateSimulationForm(config) {
  const assetSelect = document.getElementById("simulation-asset-input");
  const yearsSelect = document.getElementById("simulation-years-input");
  const sourceSelect = document.getElementById("simulation-source-input");
  const strategySelect = document.getElementById("simulation-strategy-input");
  const capitalInput = document.getElementById("simulation-capital-input");
  const feeInput = document.getElementById("simulation-fee-input");
  const note = document.getElementById("simulation-config-note");

  if (assetSelect) {
    assetSelect.innerHTML = (config.available_assets || []).map((asset) => `<option value="${asset}">${asset}</option>`).join("");
  }
  if (yearsSelect) {
    yearsSelect.innerHTML = (config.lookback_year_options || []).map((years) => `<option value="${years}">${years} year${years === 1 ? "" : "s"}</option>`).join("");
    yearsSelect.value = String(config.default_lookback_years);
  }
  if (sourceSelect) {
    sourceSelect.innerHTML = (config.data_source_options || []).map((source) => `
      <option value="${source.mode}">${source.label}</option>
    `).join("");
    sourceSelect.value = config.default_history_source_mode || "auto";
  }
  if (strategySelect) {
    strategySelect.innerHTML = (config.strategy_presets || []).map((preset) => `
      <option value="${preset.strategy_id}">${preset.label}</option>
    `).join("");
    strategySelect.value = config.default_strategy_id;
  }
  if (capitalInput) {
    capitalInput.value = String(config.default_starting_capital);
  }
  if (feeInput) {
    feeInput.value = String(config.default_fee_bps);
  }
  if (note) {
    note.textContent = config.note;
  }
  syncStrategyCreatorPanel();
}

function currentSimulationPayload() {
  return {
    asset: document.getElementById("simulation-asset-input")?.value || "BTC",
    lookback_years: Number(document.getElementById("simulation-years-input")?.value || 5),
    history_source_mode: document.getElementById("simulation-source-input")?.value || "auto",
    strategy_id: document.getElementById("simulation-strategy-input")?.value || "custom_creator",
    starting_capital: Number(document.getElementById("simulation-capital-input")?.value || 10000),
    fee_bps: Number(document.getElementById("simulation-fee-input")?.value || 10),
    fast_window: Number(document.getElementById("simulation-fast-input")?.value || 20),
    slow_window: Number(document.getElementById("simulation-slow-input")?.value || 50),
    mean_window: Number(document.getElementById("simulation-mean-input")?.value || 20),
    breakout_window: Number(document.getElementById("simulation-breakout-input")?.value || 55),
    custom_strategy_name: document.getElementById("simulation-custom-name-input")?.value || "Creator Blend",
    creator_trend_weight: Number(document.getElementById("simulation-trend-weight-input")?.value || 1),
    creator_mean_reversion_weight: Number(document.getElementById("simulation-mean-weight-input")?.value || 0.7),
    creator_breakout_weight: Number(document.getElementById("simulation-breakout-weight-input")?.value || 0.8),
    creator_entry_score: Number(document.getElementById("simulation-entry-score-input")?.value || 0.58),
    creator_exit_score: Number(document.getElementById("simulation-exit-score-input")?.value || 0.34),
    creator_max_exposure: Number(document.getElementById("simulation-max-exposure-input")?.value || 1),
    creator_pullback_entry_pct: Number(document.getElementById("simulation-pullback-input")?.value || 0.035),
    creator_stop_loss_pct: Number(document.getElementById("simulation-stop-loss-input")?.value || 0.12),
    creator_take_profit_pct: Number(document.getElementById("simulation-take-profit-input")?.value || 0.35),
  };
}

function setSimulationField(id, value) {
  const input = document.getElementById(id);
  if (!input || value === undefined || value === null) {
    return;
  }
  input.value = String(value);
}

function applySimulationPayload(payload) {
  if (!payload) {
    return;
  }
  setSimulationField("simulation-asset-input", payload.asset);
  setSimulationField("simulation-years-input", payload.lookback_years);
  setSimulationField("simulation-source-input", payload.history_source_mode);
  setSimulationField("simulation-strategy-input", payload.strategy_id);
  setSimulationField("simulation-capital-input", payload.starting_capital);
  setSimulationField("simulation-fee-input", payload.fee_bps);
  setSimulationField("simulation-fast-input", payload.fast_window);
  setSimulationField("simulation-slow-input", payload.slow_window);
  setSimulationField("simulation-mean-input", payload.mean_window);
  setSimulationField("simulation-breakout-input", payload.breakout_window);
  setSimulationField("simulation-custom-name-input", payload.custom_strategy_name);
  setSimulationField("simulation-trend-weight-input", payload.creator_trend_weight);
  setSimulationField("simulation-mean-weight-input", payload.creator_mean_reversion_weight);
  setSimulationField("simulation-breakout-weight-input", payload.creator_breakout_weight);
  setSimulationField("simulation-entry-score-input", payload.creator_entry_score);
  setSimulationField("simulation-exit-score-input", payload.creator_exit_score);
  setSimulationField("simulation-max-exposure-input", payload.creator_max_exposure);
  setSimulationField("simulation-pullback-input", payload.creator_pullback_entry_pct);
  setSimulationField("simulation-stop-loss-input", payload.creator_stop_loss_pct);
  setSimulationField("simulation-take-profit-input", payload.creator_take_profit_pct);
  syncStrategyCreatorPanel();
}

function syncStrategyCreatorPanel() {
  const strategySelect = document.getElementById("simulation-strategy-input");
  const panel = document.getElementById("strategy-creator-panel");
  const badge = document.getElementById("strategy-creator-badge");
  if (!strategySelect || !panel) {
    return;
  }
  const active = strategySelect.value === "custom_creator";
  panel.dataset.active = active ? "true" : "false";
  if (badge) {
    badge.textContent = active ? "Creator active" : "Preview only";
  }
}

function renderSimulationOptimizationBrief(result) {
  const panel = document.getElementById("simulation-optimization-panel");
  const badge = document.getElementById("simulation-optimization-badge");
  const summary = document.getElementById("simulation-optimization-summary");
  const list = document.getElementById("simulation-optimization-list");
  if (!panel || !badge || !summary || !list || !result) {
    return;
  }

  const selected = result.selected_result;
  const drawdown = Math.abs(Number(selected.max_drawdown || 0));
  const beatBenchmark = Boolean(selected.beat_buy_hold);
  const best = result.leaderboard?.[0];
  const recommendations = [];

  if (!beatBenchmark) {
    recommendations.push({
      label: "Improve edge filter",
      detail: "Raise the entry score or increase trend weight so the strategy avoids weak signals that lag buy-and-hold.",
    });
  }
  if (drawdown > 0.22) {
    recommendations.push({
      label: "Reduce pain profile",
      detail: "Lower max exposure or tighten stop loss; this setup is spending too much capital during adverse regimes.",
    });
  }
  if (Number(selected.trade_count || 0) < 4 && selected.strategy_id !== "buy_hold") {
    recommendations.push({
      label: "Increase sample size",
      detail: "Shorten the breakout or moving-average windows slightly so the test creates enough trades to trust the statistics.",
    });
  }
  if (Number(selected.win_rate || 0) < 0.48 && Number(selected.trade_count || 0) >= 4) {
    recommendations.push({
      label: "Improve exits",
      detail: "Raise the exit score or reduce take-profit distance so weaker reversals are cut before they erode the curve.",
    });
  }
  if (Number(selected.sharpe_ratio || 0) < 0.7) {
    recommendations.push({
      label: "Stabilize return path",
      detail: "Compare the same recipe on ETH and SOL, then prefer parameter sets that keep Sharpe above 0.70 across assets.",
    });
  }
  if (!recommendations.length) {
    recommendations.push({
      label: "Promote candidate",
      detail: "Save this strategy to the vault, rerun it on a 10-year window, and compare it against the same settings on other assets.",
    });
  }

  const bestNote = best && best.strategy_id !== selected.strategy_id
    ? ` Current leaderboard winner is ${best.label}, so use it as the next comparison target.`
    : " This setup is currently leading the selected comparison window.";
  badge.textContent = beatBenchmark ? "Candidate strong" : "Needs tuning";
  badge.dataset.variant = beatBenchmark ? "positive" : "warning";
  summary.textContent = `${selected.label} returned ${fmtSignedPercent(selected.total_return)} vs benchmark ${fmtSignedPercent(result.benchmark_total_return)} with ${fmtSignedPercent(selected.max_drawdown)} max drawdown.${bestNote}`;
  list.innerHTML = recommendations.slice(0, 4).map((item, index) => `
    <article>
      <span>${String(index + 1).padStart(2, "0")}</span>
      <div>
        <strong>${escapeHtml(item.label)}</strong>
        <p>${escapeHtml(item.detail)}</p>
      </div>
    </article>
  `).join("");
}

function renderSimulationResult(result) {
  latestSimulationResult = result;
  renderAdvancedExport(null);
  const headline = document.getElementById("simulation-headline");
  const submeta = document.getElementById("simulation-submeta");
  const summary = document.getElementById("simulation-summary-grid");
  const leaderboard = document.getElementById("simulation-leaderboard-body");
  const trades = document.getElementById("simulation-trade-list");
  const note = document.getElementById("simulation-history-note");

  if (headline) {
    headline.textContent = `${result.selected_result.label} on ${result.asset} over ${result.actual_years_covered.toFixed(2)} years`;
  }
  if (submeta) {
    const best = result.leaderboard?.[0];
    submeta.textContent = `Data source: ${result.data_source} · ${result.history_points} daily points · best in window ${best?.label || "n/a"} · benchmark ${fmtSignedPercent(result.benchmark_total_return)}`;
  }
  if (note) {
    note.textContent = result.history_note || "Historical coverage matches the requested backtest window.";
  }
  if (summary) {
    const selectedRank = (result.leaderboard || []).findIndex((entry) => entry.strategy_id === result.selected_result.strategy_id) + 1;
    const bestEntry = result.leaderboard?.[0];
    summary.innerHTML = `
      <article class="pulse-metric-card metric-live">
        <span>Final equity</span>
        <strong>${fmtPrice(result.selected_result.final_equity)}</strong>
        <small>${result.selected_result.label}</small>
      </article>
      <article class="pulse-metric-card ${result.selected_result.total_return >= result.benchmark_total_return ? "tone-high" : "tone-mid"}">
        <span>Total return</span>
        <strong>${fmtSignedPercent(result.selected_result.total_return)}</strong>
        <small>Benchmark ${fmtSignedPercent(result.benchmark_total_return)}</small>
      </article>
      <article class="pulse-metric-card">
        <span>CAGR</span>
        <strong>${fmtSignedPercent(result.selected_result.cagr)}</strong>
        <small>Annualized growth across the tested window</small>
      </article>
      <article class="pulse-metric-card ${result.selected_result.max_drawdown >= -0.2 ? "tone-high" : "tone-low"}">
        <span>Max drawdown</span>
        <strong>${fmtSignedPercent(result.selected_result.max_drawdown)}</strong>
        <small>Worst equity pullback</small>
      </article>
      <article class="pulse-metric-card">
        <span>Sharpe</span>
        <strong>${Number(result.selected_result.sharpe_ratio).toFixed(2)}</strong>
        <small>Risk-adjusted daily return</small>
      </article>
      <article class="pulse-metric-card">
        <span>Trades</span>
        <strong>${result.selected_result.trade_count}</strong>
        <small>${fmtPercent(result.selected_result.win_rate)} win rate · ${fmtPercent(result.selected_result.exposure_ratio)} exposure</small>
      </article>
      <article class="pulse-metric-card ${selectedRank === 1 ? "tone-high" : "tone-mid"}">
        <span>Rank</span>
        <strong>${selectedRank || "n/a"} / ${(result.leaderboard || []).length}</strong>
        <small>${selectedRank === 1 ? "Current setup is best in this window" : `Best: ${bestEntry?.label || "n/a"}`}</small>
      </article>
      <article class="pulse-metric-card">
        <span>Algorithm recipe</span>
        <strong>${result.selected_result.strategy_id === "custom_creator" ? "Editable" : "Preset"}</strong>
        <small>${result.selected_result.summary}</small>
      </article>
    `;
  }

  if (leaderboard) {
    leaderboard.innerHTML = (result.leaderboard || []).map((entry, index) => `
      <tr class="${entry.strategy_id === result.selected_result.strategy_id ? "row-up" : ""}">
        <td>${index + 1}</td>
        <td>${entry.label}</td>
        <td>${fmtSignedPercent(entry.total_return)}</td>
        <td>${fmtSignedPercent(entry.cagr)}</td>
        <td>${fmtSignedPercent(entry.max_drawdown)}</td>
        <td>${Number(entry.sharpe_ratio).toFixed(2)}</td>
        <td>${entry.trade_count}</td>
        <td>${entry.beat_buy_hold ? "Yes" : "No"}</td>
      </tr>
    `).join("");
  }

  if (trades) {
    trades.innerHTML = (result.selected_result.trades || []).map((trade) => `
      <li>
        <div>
          <strong>${fmtDateTime(trade.opened_at)} to ${fmtDateTime(trade.closed_at)}</strong>
          <p>Entry ${fmtPrice(trade.entry_price)} · Exit ${fmtPrice(trade.exit_price)}</p>
        </div>
        <div class="workspace-actions">
          <span>${fmtSignedPercent(trade.return_pct)}</span>
          <span>${trade.holding_days} days</span>
        </div>
      </li>
    `).join("") || "<li><p>No closed trades were generated for the selected setup yet.</p></li>";
  }

  renderSimulationChart(result);
  renderSimulationOptimizationBrief(result);
}

async function refreshSimulationContext(asset) {
  const [edgeSnapshot, walletSnapshot] = await Promise.all([
    fetchJson("/api/edge"),
    fetchJson("/api/wallet-intelligence"),
  ]);
  renderSimulationContext(asset, edgeSnapshot, walletSnapshot);
}

async function loadSimulationExports() {
  const historyList = document.getElementById("simulation-export-history");
  if (historyList) {
    historyList.innerHTML = `
      <li>
        <div>
          <strong>Loading artifacts</strong>
          <p>Hydrating the latest Strategy Lab export history.</p>
        </div>
      </li>
    `;
  }

  try {
    const artifacts = await fetchJson("/api/simulation/exports");
    renderSimulationExportHistory(artifacts);
  } catch (error) {
    if (historyList) {
      historyList.innerHTML = `
        <li>
          <div>
            <strong>Artifact history unavailable</strong>
            <p>${error.message}</p>
          </div>
        </li>
      `;
    }
  }
}

function renderSavedStrategies(strategies) {
  const list = document.getElementById("saved-strategy-list");
  if (!list) {
    return;
  }
  if (!strategies?.length) {
    list.innerHTML = `
      <li>
        <div>
          <strong>No saved strategies yet</strong>
          <p>Shape an algorithm above, then save it to build a reusable research vault.</p>
        </div>
      </li>
    `;
    return;
  }

  list.innerHTML = strategies.map((strategy) => {
    const config = strategy.config || {};
    const description = strategy.description || `${config.asset || "Asset"} ${config.strategy_id || "strategy"} research candidate`;
    return `
      <li class="strategy-vault-item">
        <div>
          <strong>${escapeHtml(strategy.name)}</strong>
          <p>${escapeHtml(description)}</p>
          <small>${escapeHtml(config.asset)} · ${config.lookback_years || "n/a"}y · ${escapeHtml(config.history_source_mode || "auto")} · updated ${fmtRelativeTime(strategy.updated_at)}</small>
        </div>
        <div class="workspace-actions strategy-vault-actions">
          <button class="button secondary small-button" type="button" data-load-strategy-id="${strategy.id}">Load</button>
          <button class="button primary small-button" type="button" data-run-strategy-id="${strategy.id}">Backtest</button>
        </div>
      </li>
    `;
  }).join("");
}

function renderSavedBacktests(runs) {
  const list = document.getElementById("saved-backtest-list");
  if (!list) {
    return;
  }
  if (!runs?.length) {
    list.innerHTML = `
      <li>
        <div>
          <strong>No stored backtests</strong>
          <p>Run a saved strategy to record performance, rank, and source provenance here.</p>
        </div>
      </li>
    `;
    return;
  }

  list.innerHTML = runs.map((run) => {
    const summary = run.summary || {};
    const returnValue = summary.total_return === undefined ? "n/a" : fmtSignedPercent(summary.total_return);
    const sharpe = summary.sharpe_ratio === undefined ? "n/a" : Number(summary.sharpe_ratio).toFixed(2);
    const rank = summary.rank ? `Rank #${summary.rank}` : run.status;
    return `
      <li class="strategy-backtest-item">
        <div>
          <strong>${escapeHtml(summary.strategy_name || `Strategy #${run.strategy_id}`)}</strong>
          <p>${escapeHtml(run.asset)} · ${escapeHtml(run.strategy_key)} · ${returnValue}</p>
          <small>${rank} · Sharpe ${sharpe} · ${fmtRelativeTime(run.completed_at || run.started_at)}</small>
        </div>
        <div class="workspace-actions">
          <span>${escapeHtml(run.status)}</span>
          <span>${run.lookback_years}y</span>
        </div>
      </li>
    `;
  }).join("");
}

async function loadSavedStrategies() {
  const list = document.getElementById("saved-strategy-list");
  if (list) {
    list.innerHTML = `
      <li>
        <div>
          <strong>Loading strategy vault</strong>
          <p>Checking your authenticated workspace for saved algorithms.</p>
        </div>
      </li>
    `;
  }
  try {
    savedStrategies = await fetchJson("/api/v1/strategies");
    renderSavedStrategies(savedStrategies);
  } catch (error) {
    if (list) {
      list.innerHTML = `
        <li>
          <div>
            <strong>Sign in to save strategies</strong>
            <p>${escapeHtml(error.message)}</p>
          </div>
        </li>
      `;
    }
  }
}

async function loadSavedBacktests() {
  const list = document.getElementById("saved-backtest-list");
  if (list) {
    list.innerHTML = `
      <li>
        <div>
          <strong>Loading backtest ledger</strong>
          <p>Retrieving recent stored runs.</p>
        </div>
      </li>
    `;
  }
  try {
    savedBacktestRuns = await fetchJson("/api/v1/strategies/backtests?limit=8");
    renderSavedBacktests(savedBacktestRuns);
  } catch (error) {
    if (list) {
      list.innerHTML = `
        <li>
          <div>
            <strong>Backtest ledger unavailable</strong>
            <p>${escapeHtml(error.message)}</p>
          </div>
        </li>
      `;
    }
  }
}

async function saveCurrentStrategy() {
  const button = document.getElementById("save-current-strategy-button");
  if (button) {
    button.disabled = true;
  }
  const config = currentSimulationPayload();
  const name = (config.custom_strategy_name || `${config.asset} Strategy`).trim();
  try {
    const strategy = await fetchJson("/api/v1/strategies", {
      method: "POST",
      body: JSON.stringify({
        name,
        description: `${config.asset} ${config.lookback_years}y ${config.strategy_id} candidate saved from Strategy Lab.`,
        config,
      }),
    });
    await loadSavedStrategies();
    setStatus(`Saved strategy "${strategy.name}" to your vault.`);
  } catch (error) {
    setStatus(`Strategy save failed: ${error.message}`);
  } finally {
    if (button) {
      button.disabled = false;
    }
  }
}

async function runSavedStrategyBacktest(strategyId) {
  const button = document.querySelector(`[data-run-strategy-id="${strategyId}"]`);
  if (button) {
    button.disabled = true;
  }
  try {
    const run = await fetchJson(`/api/v1/strategies/${strategyId}/backtest`, {
      method: "POST",
      body: JSON.stringify({}),
    });
    if (run.result) {
      renderSimulationResult(run.result);
      await refreshSimulationContext(run.result.asset);
    }
    await loadSavedBacktests();
    setStatus(`Stored backtest #${run.id} completed for ${run.asset}: ${run.summary?.total_return === undefined ? "n/a" : fmtSignedPercent(run.summary.total_return)}.`);
  } catch (error) {
    setStatus(`Saved strategy backtest failed: ${error.message}`);
  } finally {
    if (button) {
      button.disabled = false;
    }
  }
}

function loadSavedStrategyIntoForm(strategyId) {
  const strategy = savedStrategies.find((item) => String(item.id) === String(strategyId));
  if (!strategy) {
    setStatus("Saved strategy not found in the current vault. Refresh and try again.");
    return;
  }
  applySimulationPayload(strategy.config);
  setStatus(`Loaded "${strategy.name}" into the Strategy Lab controls.`);
}

async function generateAdvancedExport() {
  const button = document.getElementById("generate-advanced-export-button");
  if (button) {
    button.disabled = true;
  }
  try {
    const exportBundle = await fetchJson("/api/simulation/advanced-export", {
      method: "POST",
      body: JSON.stringify(currentSimulationPayload()),
    });
    renderAdvancedExport(exportBundle);
    await loadSimulationExports();
    setStatus(`Advanced export ready: ${exportBundle.filename}.`);
  } catch (error) {
    setStatus(`Advanced export failed: ${error.message}`);
  } finally {
    if (button) {
      button.disabled = false;
    }
  }
}

async function runSimulation() {
  const button = document.getElementById("run-simulation-button");
  if (button) {
    button.disabled = true;
  }
  try {
    const result = await fetchJson("/api/simulation/run", {
      method: "POST",
      body: JSON.stringify(currentSimulationPayload()),
    });
    renderSimulationResult(result);
    await refreshSimulationContext(result.asset);
    setStatus(`Simulation completed for ${result.asset}. ${result.selected_result.label} finished at ${fmtPrice(result.selected_result.final_equity)}.`);
  } catch (error) {
    setStatus(`Simulation failed: ${error.message}`);
  } finally {
    if (button) {
      button.disabled = false;
    }
  }
}

async function loadSimulationPage() {
  simulationConfig = await fetchJson("/api/simulation/config");
  populateSimulationForm(simulationConfig);
  renderAdvancedExport(null);
  await Promise.all([loadSimulationExports(), loadSavedStrategies(), loadSavedBacktests(), runSimulation()]);
}

function renderPulseMetrics(systemPulse, targetId) {
  const container = document.getElementById(targetId);
  if (!container || !systemPulse) {
    return;
  }
  container.innerHTML = `
    <article class="pulse-metric-card">
      <span>Live providers</span>
      <strong>${systemPulse.live_provider_count}</strong>
      <small>Market, signal, wallet, and venue feeds currently live-capable</small>
    </article>
    <article class="pulse-metric-card">
      <span>Recent signals</span>
      <strong>${systemPulse.total_recent_signals}</strong>
      <small>Fresh signal records included in the current pulse window</small>
    </article>
    <article class="pulse-metric-card ${qualityCardClass(systemPulse.average_signal_quality)}">
      <span>Average quality</span>
      <strong>${fmtPercent(systemPulse.average_signal_quality)}</strong>
      <div class="mini-meter"><i style="width:${(clamp(systemPulse.average_signal_quality, 0, 1) * 100).toFixed(2)}%"></i></div>
      <small>${qualityLabel(systemPulse.average_signal_quality)}</small>
    </article>
    <article class="pulse-metric-card ${qualityCardClass(systemPulse.average_signal_freshness)}">
      <span>Average freshness</span>
      <strong>${fmtPercent(systemPulse.average_signal_freshness)}</strong>
      <div class="mini-meter"><i style="width:${(clamp(systemPulse.average_signal_freshness, 0, 1) * 100).toFixed(2)}%"></i></div>
      <small>${freshnessLabel(systemPulse.average_signal_freshness)}</small>
    </article>
    <article class="pulse-metric-card">
      <span>Queue pressure</span>
      <strong>${systemPulse.pending_predictions} / ${systemPulse.retry_queue_depth}</strong>
      <small>Pending predictions / queued notification retries</small>
    </article>
  `;
}

function renderSignalMix(signalMix, targetId) {
  const container = document.getElementById(targetId);
  if (!container) {
    return;
  }
  if (!signalMix?.length) {
    container.innerHTML = '<p class="panel-note">No recent signal mix is available yet.</p>';
    return;
  }
  container.innerHTML = signalMix.map((item) => `
    <article class="signal-mix-card ${qualityCardClass(item.average_quality)}">
      <div class="signal-mix-head">
        <div>
          <span>${item.label}</span>
          <strong>${fmtPercent(item.share)}</strong>
        </div>
        <span class="badge">${item.count} signals</span>
      </div>
      <div class="mini-meter"><i style="width:${(clamp(item.average_quality, 0, 1) * 100).toFixed(2)}%"></i></div>
      <p>Average quality ${fmtPercent(item.average_quality)} · ${qualityLabel(item.average_quality)}</p>
    </article>
  `).join("");
}

function renderVenuePulse(venuePulse, targetId) {
  const container = document.getElementById(targetId);
  if (!container) {
    return;
  }
  if (!venuePulse?.length) {
    container.innerHTML = '<p class="panel-note">No venue surfaces are active in the current pulse window.</p>';
    return;
  }
  container.innerHTML = venuePulse.map((item) => `
    <article class="venue-card ${qualityCardClass(item.average_quality)}">
      <div class="venue-card-head">
        <div>
          <span class="venue-card-label">${item.source}</span>
          <h4>${item.label}</h4>
        </div>
        <span class="badge">${item.signal_count} items</span>
      </div>
      <p>${item.latest_title || "Awaiting the next venue event."}</p>
      <div class="venue-kpis">
        <div>
          <span>Quality</span>
          <strong>${fmtPercent(item.average_quality)}</strong>
        </div>
        <div>
          <span>Freshness</span>
          <strong>${fmtPercent(item.average_freshness)}</strong>
        </div>
        <div>
          <span>Bias</span>
          <strong>${sentimentLabel(item.average_sentiment)}</strong>
        </div>
      </div>
      <div class="mini-meter"><i style="width:${(clamp(item.average_quality, 0, 1) * 100).toFixed(2)}%"></i></div>
      <div class="venue-assets">
        ${item.assets.map((asset) => `<span class="venue-asset">${asset}</span>`).join("") || '<span class="venue-asset">n/a</span>'}
      </div>
      <small>${item.latest_at ? `Updated ${fmtRelativeTime(item.latest_at)}` : "Waiting for fresh venue updates"}</small>
    </article>
  `).join("");
}

function renderLandingPulse(snapshot) {
  renderPulseMetrics(snapshot.system_pulse, "landing-pulse-metrics");
  renderSignalMix(snapshot.system_pulse?.signal_mix, "landing-signal-mix");
  renderVenuePulse(snapshot.system_pulse?.venue_pulse, "landing-venue-pulse");
  const badge = document.getElementById("landing-pulse-badge");
  if (badge) {
    badge.textContent = providerState(snapshot.provider_status).label;
  }
}

function renderDashboardPulse(snapshot) {
  renderPulseMetrics(snapshot.system_pulse, "dashboard-pulse-metrics");
  renderSignalMix(snapshot.system_pulse?.signal_mix, "dashboard-signal-mix");
  renderVenuePulse(snapshot.system_pulse?.venue_pulse, "dashboard-venue-pulse");
}

function renderLandingPortfolio(snapshot) {
  const metrics = document.getElementById("portfolio-metric-grid");
  const categories = document.getElementById("portfolio-category-grid");
  const markets = document.getElementById("portfolio-market-extremes");
  const positions = document.getElementById("portfolio-position-table");
  const activeBot = document.getElementById("portfolio-active-bot");
  const topBot = snapshot.leaderboard?.[0];
  const totalVolume = (snapshot.assets || []).reduce((sum, asset) => sum + Number(asset.volume_24h || 0), 0);
  const bestMove = [...(snapshot.assets || [])].sort((a, b) => Number(b.change_24h) - Number(a.change_24h))[0];
  const worstMove = [...(snapshot.assets || [])].sort((a, b) => Number(a.change_24h) - Number(b.change_24h))[0];
  const mostActive = [...(snapshot.assets || [])].sort((a, b) => Number(b.volume_24h) - Number(a.volume_24h))[0];

  if (activeBot) {
    activeBot.textContent = topBot ? `${topBot.name} | ${fmtScore(topBot.score)} score` : "No analyst selected";
  }

  if (metrics) {
    const compactSite = metrics.classList.contains("strategy-metric-grid");
    const metricItems = compactSite
      ? [
          ["Market Volume", `$${fmtCompactNumber(totalVolume)}`, "Tracked 24h public market context"],
          ["Scored Calls", snapshot.summary.scored_predictions, `${snapshot.summary.pending_predictions} open prediction windows`],
          ["Avg Bot Score", fmtScore(snapshot.summary.average_bot_score), "Composite model quality"],
          ["Top Win Rate", fmtPercent(topBot?.hit_rate || 0), topBot ? topBot.name : "Waiting for ranked bot"],
        ]
      : [
          ["Model PNL", fmtSignedPercent(topBot?.average_strategy_return || 0), "Top bot avg strategy return"],
          ["Total Volume", `$${fmtCompactNumber(totalVolume)}`, "Tracked 24h market volume"],
          ["Total Calls", snapshot.summary.total_predictions, `${snapshot.summary.scored_predictions} scored`],
          ["Age", snapshot.summary.last_cycle_at ? fmtRelativeTime(snapshot.summary.last_cycle_at) : "Bootstrap", "Latest research cycle"],
          ["Avg Score", fmtScore(snapshot.summary.average_bot_score), "Network composite"],
          ["Active Calls", snapshot.summary.pending_predictions, "Open scoring windows"],
          ["Win Rate", fmtPercent(topBot?.hit_rate || 0), "Current leader"],
        ];
    metrics.innerHTML = metricItems.map(([label, value, note]) => `
      <article><span>${label}</span><strong>${value}</strong><small>${note}</small></article>
    `).join("");
  }

  if (categories) {
    const signalMix = snapshot.system_pulse?.signal_mix || [];
    categories.innerHTML = signalMix.length ? signalMix.slice(0, 4).map((item) => `
      <article>
        <span>${item.label}</span>
        <strong>${fmtPercent(item.share)}</strong>
        <small>${item.count} signals | quality ${fmtPercent(item.average_quality)}</small>
        <div class="mini-meter"><i style="width:${(clamp(item.average_quality, 0, 1) * 100).toFixed(2)}%"></i></div>
      </article>
    `).join("") : '<p class="panel-note">No category performance yet.</p>';
  }

  if (markets) {
    const items = [
      { label: "Best move", asset: bestMove, value: bestMove ? fmtSignedPercent(bestMove.change_24h) : "n/a" },
      { label: "Worst move", asset: worstMove, value: worstMove ? fmtSignedPercent(worstMove.change_24h) : "n/a" },
      { label: "Highest volume", asset: mostActive, value: mostActive ? `$${fmtCompactNumber(mostActive.volume_24h)}` : "n/a" },
    ];
    markets.innerHTML = items.map((item) => `
      <article>
        <span>${item.label}</span>
        <strong>${item.asset?.asset || "n/a"}</strong>
        <small>${item.value}</small>
      </article>
    `).join("");
  }

  if (positions) {
    positions.innerHTML = `
      <div class="portfolio-table-row portfolio-table-head">
        <span>Bot</span><span>Score</span><span>Hit</span><span>Return</span>
      </div>
      ${(snapshot.leaderboard || []).slice(0, 6).map((bot) => `
        <div class="portfolio-table-row">
          <span>${bot.name}<small>${bot.latest_asset || "multi"} | ${bot.archetype}</small></span>
          <strong>${fmtScore(bot.score)}</strong>
          <strong>${fmtPercent(bot.hit_rate)}</strong>
          <strong>${fmtSignedPercent(bot.average_strategy_return)}</strong>
        </div>
      `).join("")}
    `;
  }
}

function renderBusinessModel(strategy) {
  if (!strategy) {
    return;
  }

  const source = document.getElementById("business-model-source");
  const summary = document.getElementById("business-model-summary");
  const wedge = document.getElementById("business-model-wedge");
  const workflow = document.getElementById("business-model-workflow");
  const products = document.getElementById("business-products-grid");
  const revenue = document.getElementById("business-revenue-grid");
  const moat = document.getElementById("business-moat-loop");
  const strategies = document.getElementById("business-strategy-grid");
  const milestones = document.getElementById("business-milestone-grid");

  if (source) {
    source.textContent = strategy.source_deck || "Investor strategy";
  }

  if (summary) {
    summary.textContent = strategy.thesis;
  }

  if (wedge) {
    wedge.textContent = strategy.wedge;
  }

  if (workflow) {
    const labels = ["Ingest", "Score", "Simulate", "Deploy", "Retune"];
    workflow.innerHTML = (strategy.engine_workflow || []).map((step, index) => `
      <article>
        <span>${index + 1}</span>
        <strong>${labels[index] || "Loop"}</strong>
        <small>${step}</small>
      </article>
    `).join("");
  }

  if (products) {
    products.innerHTML = (strategy.products || []).map((product) => `
      <article>
        <span>${product.segment}</span>
        <strong>${product.name}</strong>
        <small>${product.pricing_model}</small>
        <p>${product.positioning}</p>
        <div class="business-chip-row">
          ${(product.core_capabilities || []).slice(0, 5).map((item) => `<i>${item}</i>`).join("")}
        </div>
      </article>
    `).join("");
  }

  if (revenue) {
    revenue.innerHTML = (strategy.revenue_streams || []).slice(0, 4).map((stream) => `
      <article>
        <span>${stream.priority}</span>
        <strong>${stream.label}</strong>
        <small>${stream.model}</small>
        <p>${stream.detail}</p>
      </article>
    `).join("");
  }

  if (moat) {
    moat.innerHTML = (strategy.moat_loop || []).map((step, index) => `
      <article>
        <span>${String(index + 1).padStart(2, "0")}</span>
        <div>
          <strong>${step.label}</strong>
          <p>${step.description}</p>
          <small>${step.output}</small>
        </div>
      </article>
    `).join("");
  }

  if (strategies) {
    strategies.innerHTML = (strategy.strategy_families || []).map((family) => `
      <article>
        <span>${family.monetization_role}</span>
        <strong>${family.label}</strong>
        <p>${family.description}</p>
        <small>Data: ${(family.required_data || []).slice(0, 3).join(" | ")}</small>
      </article>
    `).join("");
  }

  if (milestones) {
    milestones.innerHTML = (strategy.milestones || []).map((milestone) => `
      <article>
        <span>${milestone.horizon}</span>
        <strong>${milestone.label}</strong>
        <ul>
          ${(milestone.target_metrics || []).slice(0, 4).map((item) => `<li>${item}</li>`).join("")}
        </ul>
        <small>${milestone.capital_use}</small>
      </article>
    `).join("");
  }
}

function buildActivityItems(snapshot) {
  const latestPrediction = snapshot.recent_predictions?.[0];
  const latestSignal = snapshot.recent_signals?.[0];
  const latestAlert = snapshot.user_profile?.recent_alerts?.[0];
  const latestOperation = snapshot.latest_operation;
  const leadWallet = snapshot.wallet_intelligence?.wallets?.[0];
  const topEdge = snapshot.edge_snapshot?.opportunities?.[0];
  return [
    {
      label: "Market monitor",
      title: `${snapshot.provider_status.market_provider_source} is tracking ${snapshot.assets.length} assets`,
      detail: `${snapshot.summary.tracked_assets} tracked assets across ${snapshot.provider_status.environment_name} environment`,
      meta: snapshot.provider_status.market_provider_live_capable ? "live-capable" : "demo-safe",
      tone: "teal",
    },
    {
      label: "Macro regime",
      title: snapshot.macro_snapshot?.posture || "Macro context loading",
      detail: snapshot.macro_snapshot?.summary || "Waiting for macro observations to hydrate.",
      meta: `${snapshot.macro_snapshot?.series?.length || 0} series active`,
      tone: "ink",
    },
    {
      label: "Signal intake",
      title: latestSignal ? `${latestSignal.asset} signal from ${latestSignal.source}` : "Signal queue is idle",
      detail: latestSignal ? `${qualityLabel(latestSignal.source_quality_score)} · ${fmtRelativeTime(latestSignal.observed_at)} · ${latestSignal.title}` : "Waiting for fresh provider input",
      meta: `${snapshot.summary.signals_last_24h} signals in last 24h`,
      tone: "copper",
    },
    {
      label: "Wallet watch",
      title: leadWallet ? `${leadWallet.display_name} is ${leadWallet.net_bias >= 0 ? "accumulating" : "de-risking"} ${leadWallet.primary_asset || "risk"}` : "Wallet watchlist is warming up",
      detail: snapshot.wallet_intelligence?.summary || "Waiting for public wallet profiles to hydrate.",
      meta: `${snapshot.wallet_intelligence?.wallets?.length || 0} tracked wallet profiles`,
      tone: "teal",
    },
    {
      label: "Market edge",
      title: topEdge ? `${topEdge.asset} ${topEdge.stance} ${fmtBps(topEdge.edge_bps)}` : "No edge dislocation highlighted",
      detail: topEdge ? `${topEdge.market_label} · confidence ${fmtPercent(topEdge.confidence)}.` : "Waiting for fair value and venue pricing to diverge.",
      meta: topEdge ? fmtRelativeTime(topEdge.updated_at) : "idle",
      tone: "gold",
    },
    {
      label: "Bot publication",
      title: latestPrediction ? `${latestPrediction.bot_name} issued ${latestPrediction.direction} ${latestPrediction.asset}` : "No recent prediction published",
      detail: latestPrediction ? `${latestPrediction.horizon_label} horizon · ${fmtPercent(latestPrediction.confidence)} confidence` : "Prediction archive is waiting on the next cycle",
      meta: `${snapshot.summary.pending_predictions} pending calls`,
      tone: "gold",
    },
    {
      label: "Operations",
      title: latestOperation ? `${latestOperation.cycle_type} ${latestOperation.status}` : "Pipeline has not run yet",
      detail: latestOperation ? `${latestOperation.message}` : "Waiting for first operation window",
      meta: latestOperation ? fmtRelativeTime(latestOperation.completed_at || latestOperation.started_at) : "idle",
      tone: "ink",
    },
    {
      label: "Alerting",
      title: latestAlert ? latestAlert.title : "No alerts published yet",
      detail: latestAlert ? `${latestAlert.message}` : "Alert inbox is clear right now",
      meta: `${snapshot.user_profile.unread_alert_count} unread · ${snapshot.notification_health.retry_queue_depth} retries queued`,
      tone: "teal",
    },
  ];
}

function renderActivityFeed(snapshot) {
  const feed = document.getElementById("activity-feed");
  if (!feed) {
    return;
  }
  const items = buildActivityItems(snapshot);
  feed.innerHTML = items.map((item) => `
    <li class="activity-item activity-${item.tone}">
      <div class="activity-bullet"></div>
      <div class="activity-copy">
        <p class="activity-label">${item.label}</p>
        <strong>${item.title}</strong>
        <p>${item.detail}</p>
      </div>
      <span class="activity-meta">${item.meta}</span>
    </li>
  `).join("");
}

function updateRefreshCountdown() {
  const nextValue = document.getElementById("refresh-next-value");
  const nextSubtitle = document.getElementById("refresh-next-subtitle");
  const progressBar = document.getElementById("refresh-progress-bar");
  const toggle = document.getElementById("auto-refresh-button");

  if (toggle) {
    toggle.textContent = autoRefreshEnabled ? "Auto Refresh On" : "Auto Refresh Off";
  }

  if (!nextValue || !nextSubtitle || !progressBar) {
    return;
  }

  if (!autoRefreshEnabled || !nextDashboardRefreshAt || !lastDashboardRefreshAt) {
    nextValue.textContent = autoRefreshEnabled ? "Queued" : "Paused";
    nextSubtitle.textContent = autoRefreshEnabled ? "Waiting for the next refresh window" : "Refresh cadence paused";
    progressBar.style.width = autoRefreshEnabled ? "18%" : "0%";
    return;
  }

  const remainingMs = nextDashboardRefreshAt - Date.now();
  const totalMs = nextDashboardRefreshAt - lastDashboardRefreshAt.getTime();
  const progress = clamp(1 - (remainingMs / totalMs), 0, 1);

  if (remainingMs <= 0) {
    nextValue.textContent = "Refreshing";
    nextSubtitle.textContent = "Pulling the next dashboard snapshot";
    progressBar.style.width = "100%";
    return;
  }

  nextValue.textContent = `${Math.ceil(remainingMs / 1000)}s`;
  nextSubtitle.textContent = `Auto-refresh in ${Math.ceil(remainingMs / 1000)} seconds`;
  progressBar.style.width = `${(progress * 100).toFixed(2)}%`;
}

function clearRefreshTimers() {
  if (autoRefreshTimer) {
    clearInterval(autoRefreshTimer);
    autoRefreshTimer = null;
  }
  if (statusPageTimer) {
    clearInterval(statusPageTimer);
    statusPageTimer = null;
  }
  if (countdownTimer) {
    clearInterval(countdownTimer);
    countdownTimer = null;
  }
}

function startAutoRefresh() {
  clearRefreshTimers();
  if (!autoRefreshEnabled || !document.getElementById("dashboard-metrics")) {
    updateRefreshCountdown();
    return;
  }
  nextDashboardRefreshAt = Date.now() + AUTO_REFRESH_MS;
  countdownTimer = window.setInterval(updateRefreshCountdown, 1000);
  autoRefreshTimer = window.setInterval(() => {
    loadDashboard({ silent: true });
  }, AUTO_REFRESH_MS);
  updateRefreshCountdown();
}

function setRunCycleStageAnimation(active) {
  if (runCycleStageTimer) {
    clearInterval(runCycleStageTimer);
    runCycleStageTimer = null;
  }
  if (!active) {
    updateRefreshCountdown();
    return;
  }
  setLiveBadge("Cycle Running", "warning");
  let stageIndex = 0;
  setStatus(`${RUN_CYCLE_STAGES[stageIndex]}...`);
  runCycleStageTimer = window.setInterval(() => {
    stageIndex = (stageIndex + 1) % RUN_CYCLE_STAGES.length;
    setStatus(`${RUN_CYCLE_STAGES[stageIndex]}...`);
  }, 1200);
}

function renderLanding(snapshot) {
  latestLandingSnapshot = snapshot;
  const stats = document.getElementById("summary-stats");
  const mini = document.getElementById("leaderboard-mini");
  const botGrid = document.getElementById("launch-bots");
  const assets = document.getElementById("asset-grid");
  const signals = document.getElementById("landing-signals");
  const providerBadge = document.getElementById("landing-provider-badge");
  const providerNote = document.getElementById("landing-provider-note");

  if (stats) {
    stats.innerHTML = `
      <li><strong>${snapshot.summary.active_bots}</strong><span>active bots</span></li>
      <li><strong>${snapshot.summary.scored_predictions}</strong><span>scored predictions</span></li>
      <li><strong>${snapshot.summary.tracked_assets}</strong><span>tracked assets</span></li>
    `;
  }

  if (mini) {
    mini.innerHTML = snapshot.leaderboard.map((bot) => `
      <div><span>${bot.name}</span><strong>${fmtScore(bot.score)}</strong></div>
    `).join("");
  }

  if (providerBadge) {
    providerBadge.textContent = snapshot.provider_status.market_provider_source;
  }

  if (providerNote) {
    providerNote.textContent = `${snapshot.provider_status.environment_name} environment · ${snapshot.system_pulse.live_provider_count} live-capable providers · market ${snapshot.provider_status.market_provider_source} · signal ${snapshot.provider_status.signal_provider_source} · average quality ${fmtPercent(snapshot.system_pulse.average_signal_quality)}.`;
  }

  renderLandingPortfolio(snapshot);
  renderBusinessModel(snapshot.business_model);

  if (botGrid) {
    const accents = ["accent-copper", "accent-teal", "accent-gold", "accent-ink"];
    botGrid.innerHTML = snapshot.leaderboard.map((bot, index) => `
      <article class="bot-card ${accents[index % accents.length]}">
        <h4>${bot.name}</h4>
        <p>${bot.thesis}</p>
        <span>${bot.archetype} | Horizon: ${bot.horizon_label}</span>
      </article>
    `).join("");
  }

  if (assets) {
    assets.innerHTML = snapshot.assets.map((asset) => `
      <article class="asset-card">
        <div class="asset-head">
          <h4>${asset.asset}</h4>
          <span class="badge ${asset.change_24h >= 0 ? "badge-up" : "badge-down"}">${fmtSignedPercent(asset.change_24h)}</span>
        </div>
        <p class="asset-price">${fmtPrice(asset.price)}</p>
        <dl>
          <div><dt>Trend</dt><dd>${asset.trend_score.toFixed(2)}</dd></div>
          <div><dt>Signal Bias</dt><dd>${asset.signal_bias.toFixed(2)}</dd></div>
          <div><dt>Volatility</dt><dd>${fmtPercent(asset.volatility, 1)}</dd></div>
        </dl>
      </article>
    `).join("");
  }

  if (signals) {
    signals.innerHTML = snapshot.recent_signals.map((signal) => `
      <li>
        <div>
          <strong>${signal.asset} · ${signal.title}</strong>
          <p>${signal.summary}</p>
          <p class="panel-note">${qualityLabel(signal.source_quality_score)} · quality ${fmtPercent(signal.source_quality_score)}</p>
        </div>
        <span>${signal.source} · ${fmtPercent(signal.relevance)} · freshness ${fmtPercent(signal.freshness_score)}</span>
      </li>
    `).join("");
  }

  renderLandingPulse(snapshot);
  renderMacroCards(snapshot.macro_snapshot, "landing-macro-grid", "landing-macro-posture", "landing-macro-summary");
  renderLandingMarketChart(snapshot.assets).catch((error) => console.error(error));
}

function renderMetrics(summary) {
  const metrics = document.getElementById("dashboard-metrics");
  if (!metrics || !summary) {
    return;
  }
  metrics.innerHTML = `
    <article class="metric-card metric-live">
      <span>Active bots</span>
      <strong>${summary.active_bots}</strong>
      <small>${summary.average_bot_score.toFixed(1)} avg composite</small>
    </article>
    <article class="metric-card metric-live">
      <span>Tracked assets</span>
      <strong>${summary.tracked_assets}</strong>
      <small>${summary.signals_last_24h} fresh signals last 24h</small>
    </article>
    <article class="metric-card metric-live">
      <span>Scored predictions</span>
      <strong>${summary.scored_predictions}</strong>
      <small>${summary.total_predictions} total archived calls</small>
    </article>
    <article class="metric-card metric-live">
      <span>Pending predictions</span>
      <strong>${summary.pending_predictions}</strong>
      <small>${summary.last_cycle_status || "idle"} cycle state</small>
    </article>
  `;
}

function renderAssets(assets, targetId = "dashboard-assets") {
  const container = document.getElementById(targetId);
  if (!container) {
    return;
  }
  container.innerHTML = assets.map((asset) => `
    <article class="asset-card compact-card">
      <div class="asset-head">
        <h4>${asset.asset}</h4>
        <span class="badge ${asset.change_24h >= 0 ? "badge-up" : "badge-down"}">${fmtSignedPercent(asset.change_24h)}</span>
      </div>
      <p class="asset-price">${fmtPrice(asset.price)}</p>
      <dl>
        <div><dt>Trend</dt><dd>${asset.trend_score.toFixed(2)}</dd></div>
        <div><dt>Bias</dt><dd>${asset.signal_bias.toFixed(2)}</dd></div>
        <div><dt>Volatility</dt><dd>${fmtPercent(asset.volatility, 1)}</dd></div>
      </dl>
      <div class="asset-meter-group">
        <div>
          <span>Trend</span>
          <div class="asset-meter"><i style="width:${(clamp((asset.trend_score + 1) / 2, 0, 1) * 100).toFixed(2)}%"></i></div>
        </div>
        <div>
          <span>Bias</span>
          <div class="asset-meter"><i style="width:${(clamp((asset.signal_bias + 1) / 2, 0, 1) * 100).toFixed(2)}%"></i></div>
        </div>
      </div>
    </article>
  `).join("");
}

function renderOperation(operation, targetId = "operation-card") {
  const card = document.getElementById(targetId);
  if (!card) {
    return;
  }
  if (!operation) {
    card.innerHTML = "<p>No pipeline runs recorded yet.</p>";
    return;
  }
  card.innerHTML = `
    <div class="operation-hero">
      <span class="status-pill" data-variant="${operation.status === "completed" ? "positive" : "warning"}">${operation.status}</span>
      <strong>${operation.cycle_type}</strong>
      <small>${fmtRelativeTime(operation.completed_at || operation.started_at)}</small>
    </div>
    <div class="operation-grid">
      <p><strong>Signals ingested:</strong> ${operation.ingested_signals}</p>
      <p><strong>Predictions created:</strong> ${operation.generated_predictions}</p>
      <p><strong>Predictions scored:</strong> ${operation.scored_predictions}</p>
      <p><strong>Completed:</strong> ${fmtDateTime(operation.completed_at || operation.started_at)}</p>
    </div>
    <p>${operation.message}</p>
  `;
}

function renderProviderStatus(providerStatus, targetId = "provider-card") {
  const card = document.getElementById(targetId);
  if (!card || !providerStatus) {
    return;
  }
  const rssFeeds = providerStatus.rss_feed_urls?.length
    ? providerStatus.rss_feed_urls.map((feed) => `<li>${feed}</li>`).join("")
    : "<li>No RSS feeds configured</li>";
  const redditFeeds = providerStatus.reddit_subreddits?.length
    ? providerStatus.reddit_subreddits.map((subreddit) => `<li>r/${subreddit}</li>`).join("")
    : "<li>No subreddits configured</li>";
  const venueProviders = providerStatus.venue_signal_providers?.length
    ? providerStatus.venue_signal_providers.map((provider) => `
        <li>
          <strong>${provider.mode}</strong> · ${provider.source}
          <span class="panel-note">${provider.ready ? "ready" : "attention"} · ${provider.live_capable ? "live" : "demo-safe"}</span>
          ${provider.warning ? `<div class="error-text">${provider.warning}</div>` : ""}
        </li>
      `).join("")
    : "<li>No venue providers configured</li>";
  const trackedWallets = providerStatus.tracked_wallets?.length
    ? providerStatus.tracked_wallets.map((wallet) => `<li>${wallet}</li>`).join("")
    : "<li>No tracked wallets configured</li>";
  const youtubeQueries = providerStatus.youtube_discovery_queries?.length
    ? providerStatus.youtube_discovery_queries.map((query) => `<li>${query}</li>`).join("")
    : "<li>No YouTube discovery queries configured</li>";
  const youtubeChannels = providerStatus.youtube_channel_ids?.length
    ? providerStatus.youtube_channel_ids.map((channel) => `<li>${channel}</li>`).join("")
    : "<li>No fixed YouTube channels configured</li>";
  card.innerHTML = `
    <p><strong>Environment:</strong> ${providerStatus.environment_name}</p>
    <p><strong>Deployment:</strong> ${providerStatus.deployment_target}</p>
    <p><strong>Database:</strong> ${providerStatus.database_backend} · ${providerStatus.database_target}</p>
    <p><strong>Market mode:</strong> ${providerStatus.market_provider_mode}</p>
    <p><strong>Market source:</strong> ${providerStatus.market_provider_source}</p>
    <p><strong>Market configured:</strong> ${providerStatus.market_provider_configured ? "yes" : "no"}</p>
    <p><strong>Market live capable:</strong> ${providerStatus.market_provider_live_capable ? "yes" : "no"}</p>
    <p><strong>Market ready:</strong> ${providerStatus.market_provider_ready ? "yes" : "no"}</p>
    ${providerStatus.market_provider_warning ? `<p class="error-text">${providerStatus.market_provider_warning}</p>` : ""}
    <p><strong>Signal mode:</strong> ${providerStatus.signal_provider_mode}</p>
    <p><strong>Signal source:</strong> ${providerStatus.signal_provider_source}</p>
    <p><strong>Signal configured:</strong> ${providerStatus.signal_provider_configured ? "yes" : "no"}</p>
    <p><strong>Signal live capable:</strong> ${providerStatus.signal_provider_live_capable ? "yes" : "no"}</p>
    <p><strong>Signal ready:</strong> ${providerStatus.signal_provider_ready ? "yes" : "no"}</p>
    ${providerStatus.signal_provider_warning ? `<p class="error-text">${providerStatus.signal_provider_warning}</p>` : ""}
    <p><strong>Macro mode:</strong> ${providerStatus.macro_provider_mode}</p>
    <p><strong>Macro source:</strong> ${providerStatus.macro_provider_source}</p>
    <p><strong>Macro configured:</strong> ${providerStatus.macro_provider_configured ? "yes" : "no"}</p>
    <p><strong>Macro live capable:</strong> ${providerStatus.macro_provider_live_capable ? "yes" : "no"}</p>
    <p><strong>Macro ready:</strong> ${providerStatus.macro_provider_ready ? "yes" : "no"}</p>
    ${providerStatus.macro_provider_warning ? `<p class="error-text">${providerStatus.macro_provider_warning}</p>` : ""}
    <p><strong>Wallet mode:</strong> ${providerStatus.wallet_provider_mode}</p>
    <p><strong>Wallet source:</strong> ${providerStatus.wallet_provider_source}</p>
    <p><strong>Wallet configured:</strong> ${providerStatus.wallet_provider_configured ? "yes" : "no"}</p>
    <p><strong>Wallet live capable:</strong> ${providerStatus.wallet_provider_live_capable ? "yes" : "no"}</p>
    <p><strong>Wallet ready:</strong> ${providerStatus.wallet_provider_ready ? "yes" : "no"}</p>
    ${providerStatus.wallet_provider_warning ? `<p class="error-text">${providerStatus.wallet_provider_warning}</p>` : ""}
    <p><strong>Social discovery mode:</strong> ${providerStatus.social_discovery_provider_mode}</p>
    <p><strong>Social discovery source:</strong> ${providerStatus.social_discovery_provider_source}</p>
    <p><strong>Social discovery configured:</strong> ${providerStatus.social_discovery_configured ? "yes" : "no"}</p>
    <p><strong>Social discovery live capable:</strong> ${providerStatus.social_discovery_live_capable ? "yes" : "no"}</p>
    <p><strong>Social discovery ready:</strong> ${providerStatus.social_discovery_ready ? "yes" : "no"}</p>
    ${providerStatus.social_discovery_warning ? `<p class="error-text">${providerStatus.social_discovery_warning}</p>` : ""}
    <p><strong>Tracked coins:</strong> ${providerStatus.tracked_coin_ids.join(", ")}</p>
    <p><strong>Macro series:</strong> ${providerStatus.fred_series_ids.join(", ")}</p>
    <p><strong>Market fallback:</strong> ${providerStatus.market_fallback_active ? "yes" : "no"}</p>
    <p><strong>Signal fallback:</strong> ${providerStatus.signal_fallback_active ? "yes" : "no"}</p>
    <p><strong>Macro fallback:</strong> ${providerStatus.macro_fallback_active ? "yes" : "no"}</p>
    <p><strong>Wallet fallback:</strong> ${providerStatus.wallet_fallback_active ? "yes" : "no"}</p>
    <p><strong>Social fallback:</strong> ${providerStatus.social_discovery_fallback_active ? "yes" : "no"}</p>
    <div class="provider-feed-list">
      <strong>RSS feeds</strong>
      <ul>${rssFeeds}</ul>
    </div>
    <div class="provider-feed-list">
      <strong>Reddit subreddits</strong>
      <ul>${redditFeeds}</ul>
    </div>
    <div class="provider-feed-list">
      <strong>Venue providers</strong>
      <ul>${venueProviders}</ul>
    </div>
    <div class="provider-feed-list">
      <strong>YouTube discovery queries</strong>
      <ul>${youtubeQueries}</ul>
    </div>
    <div class="provider-feed-list">
      <strong>YouTube channel IDs</strong>
      <ul>${youtubeChannels}</ul>
    </div>
    <div class="provider-feed-list">
      <strong>Tracked wallets</strong>
      <ul>${trackedWallets}</ul>
    </div>
  `;
}

function renderStatusPage(landing, systemPulse, providerStatus, operation) {
  const badge = document.getElementById("status-badge");
  const heroTitle = document.getElementById("status-hero-title");
  const heroCopy = document.getElementById("status-hero-copy");
  const heroMetrics = document.getElementById("status-hero-metrics");
  const providerNote = document.getElementById("status-provider-note");
  const state = providerState(providerStatus);

  if (badge) {
    badge.textContent = state.label;
  }

  if (heroTitle) {
    heroTitle.textContent = state.label === "Nominal"
      ? "Bot Society Markets is online and ingesting live market context."
      : (state.label === "Fallback active"
        ? "Bot Society Markets is online with managed fallback systems active."
        : "Bot Society Markets is online, with one or more providers needing attention.");
  }

  if (heroCopy) {
    heroCopy.textContent = `${systemPulse.total_recent_signals} recent signals across ${systemPulse.signal_mix.length} input types, ${systemPulse.pending_predictions} pending predictions waiting on score windows, and ${systemPulse.retry_queue_depth} queued notification retries.`;
  }

  if (heroMetrics) {
    heroMetrics.innerHTML = `
      <div><span>Live providers</span><strong>${systemPulse.live_provider_count}</strong></div>
      <div><span>Signal quality</span><strong>${fmtPercent(systemPulse.average_signal_quality)}</strong></div>
      <div><span>Freshness</span><strong>${fmtPercent(systemPulse.average_signal_freshness)}</strong></div>
      <div><span>Last cycle</span><strong>${operation ? fmtRelativeTime(operation.completed_at || operation.started_at) : "n/a"}</strong></div>
    `;
  }

  if (providerNote) {
    providerNote.textContent = `${providerStatus.environment_name} environment · market ${providerStatus.market_provider_source} · signal ${providerStatus.signal_provider_source} · macro ${providerStatus.macro_provider_source} · wallet ${providerStatus.wallet_provider_source} · pulse updated ${fmtRelativeTime(systemPulse.generated_at)}.`;
  }

  renderPulseMetrics(systemPulse, "status-pulse-metrics");
  renderSignalMix(systemPulse.signal_mix, "status-signal-mix");
  renderVenuePulse(systemPulse.venue_pulse, "status-venue-pulse");
  renderProviderStatus(providerStatus, "status-provider-card");
  renderOperation(operation, "status-operation-card");
  renderAssets(landing.assets, "status-assets");
}

function renderLeaderboard(leaderboard, profile) {
  const body = document.getElementById("leaderboard-body");
  const spotlight = document.getElementById("alert-spotlight");
  const summary = document.getElementById("leaderboard-summary");
  if (!body) {
    return;
  }
  const scoreSnapshot = new Map();
  body.innerHTML = leaderboard.map((bot, index) => `
    <tr class="clickable-row ${leaderboardDeltaClass(bot)}" data-bot-slug="${bot.slug}">
      <td>
        <button class="text-button leaderboard-button" type="button" data-bot-slug="${bot.slug}">
          <span class="leaderboard-rank">${index + 1}</span>
          <span class="leaderboard-label">
            <span>${bot.name}${bot.is_followed ? " · Following" : ""}</span>
            <small class="leaderboard-meta">${escapeHtml(bot.focus)} · ${provenanceLabel(bot.provenance_score)}</small>
          </span>
        </button>
      </td>
      <td>${fmtScore(bot.score)}</td>
      <td>${fmtPercent(bot.hit_rate)}</td>
      <td>${bot.calibration.toFixed(2)}</td>
      <td>${fmtPercent(bot.provenance_score)}</td>
      <td>${fmtSignedPercent(bot.average_strategy_return)}</td>
      <td>${bot.predictions}</td>
    </tr>
  `).join("");

  leaderboard.forEach((bot) => {
    scoreSnapshot.set(bot.slug, bot.score);
  });
  previousLeaderboardScores = scoreSnapshot;

  if (summary) {
    const leader = leaderboard[0];
    const averageProvenance = leaderboard.length
      ? leaderboard.reduce((total, bot) => total + Number(bot.provenance_score || 0), 0) / leaderboard.length
      : 0;
    const strongEvidenceCount = leaderboard.filter((bot) => Number(bot.provenance_score || 0) >= 0.68).length;
    summary.textContent = leader
      ? `${leader.name} leads with ${fmtScore(leader.score)} composite and ${fmtPercent(leader.provenance_score)} provenance. ${strongEvidenceCount} ranked bots currently sit above the strong-evidence threshold, with board-wide provenance averaging ${fmtPercent(averageProvenance)}.`
      : "No leaderboard data is available yet.";
  }

  if (spotlight) {
    const unreadCount = profile?.unread_alert_count || 0;
    const latestAlert = profile?.recent_alerts?.[0];
    spotlight.innerHTML = `
      <p><strong>Unread alerts:</strong> ${unreadCount}</p>
      <p><strong>Inbox coverage:</strong> ${profile?.recent_alerts?.length || 0} recent events</p>
      <p><strong>Pending archive:</strong> ${latestSnapshot?.summary?.pending_predictions || 0} calls waiting on score windows</p>
      ${latestAlert ? `<p><strong>Latest:</strong> ${latestAlert.title}</p><p>${latestAlert.message}</p>` : "<p>No alert deliveries yet.</p>"}
    `;
  }
}

function leaderboardDeltaClass(bot) {
  if (!previousLeaderboardScores.has(bot.slug)) {
    return "";
  }
  const prior = previousLeaderboardScores.get(bot.slug);
  if (Math.abs(prior - bot.score) < 0.05) {
    return "";
  }
  return bot.score > prior ? "row-up" : "row-down";
}

function renderPredictions(predictions, targetId = "prediction-list") {
  const container = document.getElementById(targetId);
  if (!container) {
    return;
  }
  container.innerHTML = predictions.map((prediction) => `
    <li class="${qualityCardClass(prediction.provenance_score ?? prediction.top_signal_quality ?? 0.55)}">
      <div class="prediction-main">
        <strong>${prediction.bot_name} · ${prediction.asset} · ${prediction.direction}</strong>
        <p>${prediction.thesis}</p>
        <p class="panel-note">${fmtRelativeTime(prediction.published_at)} · ${fmtPercent(prediction.confidence)} confidence</p>
        <div class="prediction-provenance">
          ${prediction.provenance_score !== null ? `<span class="prediction-pill ${qualityCardClass(prediction.provenance_score)}">${provenanceLabel(prediction.provenance_score)} · ${fmtPercent(prediction.provenance_score)}</span>` : '<span class="prediction-pill tone-low">Evidence pending</span>'}
          ${prediction.top_signal_quality !== null ? `<span class="prediction-pill">${qualityLabel(prediction.top_signal_quality)}</span>` : ""}
          ${prediction.venue_support_share !== null ? `<span class="prediction-pill">${fmtPercent(prediction.venue_support_share)} venue-backed</span>` : ""}
        </div>
        ${(prediction.provider_mix?.length || prediction.source_mix?.length) ? `
          <div class="prediction-chip-row">
            ${(prediction.provider_mix || []).map((provider) => `<span class="provider-chip">${escapeHtml(humanizeKey(provider))}</span>`).join("")}
            ${(prediction.source_mix || []).map((source) => `<span class="provider-chip provider-chip-muted">${escapeHtml(sourceTypeLabel(source))}</span>`).join("")}
          </div>
        ` : ""}
      </div>
      <div class="prediction-side">
        <span>${prediction.horizon_label} · ${prediction.status}${prediction.score !== null ? ` · ${fmtScore(prediction.score)}` : ""}</span>
        <small>${prediction.source_signal_count ? `${prediction.source_signal_count} linked signals` : "No linked signals"}${prediction.calibration_score !== null ? ` · calibration ${prediction.calibration_score.toFixed(2)}` : ""}</small>
      </div>
    </li>
  `).join("");
}

function renderSignals(signals, targetId = "signal-list") {
  const container = document.getElementById(targetId);
  if (!container) {
    return;
  }
  container.innerHTML = signals.map((signal) => `
    <li>
      <div>
        <strong>${signal.asset} · ${signal.title}</strong>
        <p>${signal.summary}</p>
        <p class="panel-note">${signal.provider_name}${signal.author_handle ? ` · ${signal.author_handle}` : ""}</p>
        <p class="panel-note">${qualityLabel(signal.source_quality_score)} · trust ${fmtPercent(signal.provider_trust_score)} · freshness ${fmtPercent(signal.freshness_score)} · ${fmtRelativeTime(signal.observed_at)}</p>
      </div>
      <span>${signal.source_type} · ${signal.source} · quality ${fmtPercent(signal.source_quality_score)}${signal.engagement_score !== null ? ` · engagement ${fmtPercent(signal.engagement_score)}` : ""}</span>
    </li>
  `).join("");
}

function renderAuthPanel(authSession, profile) {
  const badge = document.getElementById("auth-status-badge");
  const note = document.getElementById("auth-note");
  const sessionCard = document.getElementById("auth-session-card");
  const actions = document.getElementById("auth-actions");
  const loginCard = document.getElementById("login-card");
  const registerCard = document.getElementById("register-card");

  if (!badge || !note || !sessionCard || !actions || !loginCard || !registerCard) {
    return;
  }

  if (authSession?.authenticated && authSession.user) {
    const mfaState = profile?.security?.mfa_enabled ? "Enabled" : "Disabled";
    const onboardingStage = profile?.onboarding?.stage ? humanizeKey(profile.onboarding.stage) : "Identity";
    badge.textContent = "Signed in";
    note.textContent = `You are working in the ${authSession.user.display_name} workspace.`;
    sessionCard.innerHTML = `
      <dl class="detail-stats compact-detail-stats">
        <div><dt>Name</dt><dd>${authSession.user.display_name}</dd></div>
        <div><dt>Email</dt><dd>${authSession.user.email}</dd></div>
        <div><dt>Tier</dt><dd>${authSession.user.tier}</dd></div>
        <div><dt>Workspace</dt><dd>${profile.slug}</dd></div>
        <div><dt>MFA</dt><dd>${mfaState}</dd></div>
        <div><dt>Onboarding</dt><dd>${onboardingStage}</dd></div>
      </dl>
    `;
    actions.innerHTML = '<button class="button tertiary" type="button" data-action="logout">Sign Out</button>';
    loginCard.hidden = true;
    registerCard.hidden = true;
    return;
  }

  badge.textContent = "Demo mode";
  note.textContent = "You are viewing the seeded demo workspace. Sign in to get a personal workspace with private follows, channels, and alerts.";
  sessionCard.innerHTML = `
    <dl class="detail-stats compact-detail-stats">
      <div><dt>Workspace</dt><dd>${profile.display_name}</dd></div>
      <div><dt>Tier</dt><dd>${profile.tier}</dd></div>
      <div><dt>Email</dt><dd>${profile.email}</dd></div>
      <div><dt>Mode</dt><dd>Shared demo</dd></div>
      <div><dt>MFA</dt><dd>Sign in required</dd></div>
      <div><dt>Onboarding</dt><dd>Sign in required</dd></div>
    </dl>
  `;
  actions.innerHTML = "";
  loginCard.hidden = false;
  registerCard.hidden = false;
}

function renderOnboardingPanel(authSession, profile) {
  const form = document.getElementById("onboarding-form");
  const summary = document.getElementById("onboarding-summary");
  const stagePill = document.getElementById("onboarding-stage-pill");
  if (!form || !summary || !stagePill) {
    return;
  }

  const stageInput = document.getElementById("onboarding-stage");
  const riskInput = document.getElementById("onboarding-risk");
  const suitabilityInput = document.getElementById("onboarding-suitability-score");
  const kycInput = document.getElementById("onboarding-kyc-status");
  const languageInput = document.getElementById("onboarding-language");
  const themeInput = document.getElementById("onboarding-theme");
  const workspaceModeInput = document.getElementById("onboarding-workspace-mode");
  const timezoneInput = document.getElementById("onboarding-timezone");
  const completeInput = document.getElementById("onboarding-complete");

  const signedIn = Boolean(authSession?.authenticated && authSession?.user);
  const onboarding = profile?.onboarding || null;

  if (!signedIn || !onboarding) {
    stagePill.textContent = "Demo";
    summary.textContent = "Sign in to complete identity, risk, suitability, and KYC onboarding gates.";
    form.querySelectorAll("input, select, button").forEach((field) => {
      field.disabled = true;
    });
    return;
  }

  form.querySelectorAll("input, select, button").forEach((field) => {
    field.disabled = false;
  });
  stagePill.textContent = onboarding.completed
    ? "Complete"
    : humanizeKey(onboarding.stage || "identity");
  summary.textContent = onboarding.recommended_next_step
    || `Stage: ${humanizeKey(onboarding.stage || "identity")}`;

  if (stageInput) {
    stageInput.value = onboarding.stage || "identity";
  }
  if (riskInput) {
    riskInput.checked = Boolean(onboarding.risk_disclosure_accepted_at);
  }
  if (suitabilityInput) {
    suitabilityInput.value = onboarding.suitability_score ?? "";
  }
  if (kycInput) {
    kycInput.value = onboarding.kyc_status || "not_started";
  }
  if (languageInput) {
    languageInput.value = onboarding.preferred_language || "en";
  }
  if (themeInput) {
    themeInput.value = onboarding.preferred_theme || "day";
  }
  if (workspaceModeInput) {
    workspaceModeInput.value = onboarding.preferred_workspace_mode || "pro";
  }
  if (timezoneInput) {
    timezoneInput.value = onboarding.timezone || "UTC";
  }
  if (completeInput) {
    completeInput.checked = Boolean(onboarding.completed);
  }
}

function renderMfaPanel(authSession, profile) {
  const summary = document.getElementById("mfa-summary");
  const statusPill = document.getElementById("mfa-status-pill");
  const setupButton = document.getElementById("mfa-start-setup-button");
  const setupCard = document.getElementById("mfa-setup-card");
  const uriElement = document.getElementById("mfa-otpauth-uri");
  const enableForm = document.getElementById("mfa-enable-form");
  const disableForm = document.getElementById("mfa-disable-form");
  if (!summary || !statusPill || !setupButton || !setupCard || !uriElement || !enableForm || !disableForm) {
    return;
  }

  const signedIn = Boolean(authSession?.authenticated && authSession?.user);
  const security = profile?.security || {};
  const mfaEnabled = Boolean(security.mfa_enabled);

  if (!signedIn) {
    statusPill.textContent = "Locked";
    summary.textContent = "Sign in to configure MFA.";
    setupCard.classList.add("hidden");
    [setupButton, ...enableForm.querySelectorAll("input, button"), ...disableForm.querySelectorAll("input, button")].forEach((node) => {
      node.disabled = true;
    });
    return;
  }

  [setupButton, ...enableForm.querySelectorAll("input, button"), ...disableForm.querySelectorAll("input, button")].forEach((node) => {
    node.disabled = false;
  });

  statusPill.textContent = mfaEnabled ? "Enabled" : (security.mfa_pending_setup ? "Pending setup" : "Not enabled");
  summary.textContent = mfaEnabled
    ? `MFA enrolled${security.mfa_enrolled_at ? ` ${fmtRelativeTime(security.mfa_enrolled_at)}` : ""}.`
    : "Protect this workspace with authenticator-based two-factor login.";

  if (security.mfa_pending_setup) {
    setupCard.classList.remove("hidden");
    if (!uriElement.textContent) {
      uriElement.textContent = "Pending setup is active. Click Start setup to regenerate the provisioning URI.";
    }
  } else {
    setupCard.classList.add("hidden");
    uriElement.textContent = "";
  }
}

function renderBillingPanel(billing, authSession) {
  const badge = document.getElementById("billing-status-badge");
  const summary = document.getElementById("billing-summary");
  const planGrid = document.getElementById("billing-plan-grid");
  const actions = document.getElementById("billing-actions");
  const warningList = document.getElementById("billing-warning-list");

  if (!badge || !summary || !planGrid || !actions || !warningList || !billing) {
    return;
  }

  const signedIn = Boolean(authSession?.authenticated && authSession?.user);
  const variant = billing.has_active_subscription ? "positive" : (billing.checkout_ready ? "warning" : "neutral");
  const statusLabel = billing.has_active_subscription
    ? `${billing.plan_label || "Paid"} active`
    : (billing.checkout_ready ? "Checkout ready" : (signedIn ? "Needs setup" : "Sign in required"));

  badge.textContent = statusLabel;
  badge.dataset.variant = variant;

  const subscriptionMeta = [];
  if (billing.subscription_status) {
    subscriptionMeta.push(`status ${billing.subscription_status}`);
  }
  if (billing.current_period_end) {
    subscriptionMeta.push(`renews ${fmtDateTime(billing.current_period_end)}`);
  }
  if (billing.cancel_at_period_end) {
    subscriptionMeta.push("set to cancel at period end");
  }
  summary.textContent = subscriptionMeta.length ? `${billing.summary} ${subscriptionMeta.join(" · ")}.` : billing.summary;

  planGrid.innerHTML = (billing.available_plans || []).map((plan) => {
    const currentPlan = billing.plan_key === plan.key;
    const actionLabel = currentPlan && billing.has_active_subscription
      ? "Active plan"
      : (plan.configured ? `Choose ${plan.label}` : "Pending setup");
    return `
      <article class="billing-plan-card ${plan.configured ? "is-configured" : ""} ${currentPlan ? "is-current" : ""}">
        <div class="workspace-head">
          <div>
            <h5>${plan.label}${plan.recommended ? " · Recommended" : ""}</h5>
            <p class="panel-note">${plan.headline}</p>
          </div>
          <span class="badge">${plan.configured ? "Configured" : "Waiting"}</span>
        </div>
        <ul class="launch-track-list billing-feature-list">
          ${(plan.features || []).map((feature) => `<li>${feature}</li>`).join("")}
        </ul>
        <button
          class="button tertiary small-button"
          type="button"
          data-action="start-checkout"
          data-plan-key="${plan.key}"
          ${disabledAttr(!billing.can_manage || !billing.checkout_ready || !plan.configured || (currentPlan && billing.has_active_subscription))}
        >
          ${actionLabel}
        </button>
      </article>
    `;
  }).join("");

  warningList.innerHTML = (billing.warnings || []).map((warning) => `<li>${warning}</li>`).join("")
    || "<li>No billing blockers are recorded right now.</li>";

  actions.innerHTML = `
    <button class="button primary" type="button" data-action="start-checkout" data-plan-key="${billing.available_plans?.find((plan) => plan.recommended && plan.configured)?.key || "basic"}" ${disabledAttr(!billing.can_manage || !billing.checkout_ready)}>
      ${billing.has_active_subscription ? "Change Plan" : "Launch Checkout"}
    </button>
    <button class="button secondary" type="button" data-action="open-billing-portal" ${disabledAttr(!billing.can_manage || !billing.portal_ready)}>
      Open Billing Portal
    </button>
  `;
}

function renderWalletConnections(profile, authSession) {
  const summary = document.getElementById("wallet-connect-summary");
  const statusPill = document.getElementById("wallet-connect-status");
  const list = document.getElementById("wallet-connect-list");
  const form = document.getElementById("wallet-connect-form");
  if (!summary || !statusPill || !list) {
    return;
  }

  const signedIn = Boolean(authSession?.authenticated && authSession?.user);
  const canEdit = workspaceEditable({ auth_session: authSession, user_profile: profile });
  const connected = profile?.wallet_connections || [];
  statusPill.textContent = signedIn ? (connected.length ? `${connected.length} connected` : "Ready") : "Locked";
  summary.textContent = signedIn
    ? "Connect a wallet address for non-custodial workspace context and upcoming execution connectors."
    : "Sign in to connect wallets. Demo mode keeps wallet management disabled.";

  if (form) {
    form.querySelectorAll("input, select, button").forEach((field) => {
      field.disabled = !canEdit;
    });
  }

  list.innerHTML = connected.map((wallet) => `
    <li>
      <div>
        <strong>${wallet.label ? `${escapeHtml(wallet.label)} · ` : ""}${wallet.chain.toUpperCase()} · ${escapeHtml(wallet.provider)}</strong>
        <p><code>${escapeHtml(wallet.address)}</code></p>
      </div>
      <button class="button tertiary small-button" type="button" data-action="delete-wallet" data-wallet-id="${wallet.id}" ${disabledAttr(!canEdit)}>Disconnect</button>
    </li>
  `).join("") || "<li><p>No wallets connected yet.</p></li>";
}

function renderNotificationChannels(profile, notificationHealth) {
  const list = document.getElementById("notification-channel-list");
  const badge = document.getElementById("channel-count-badge");
  if (!list || !badge) {
    return;
  }

  const canEdit = workspaceEditable();
  const healthMap = new Map((notificationHealth?.channels || []).map((channel) => [channel.channel_id, channel]));
  badge.textContent = `${profile.notification_channels.length} channel${profile.notification_channels.length === 1 ? "" : "s"}`;

  list.innerHTML = profile.notification_channels.map((channel) => {
    const health = healthMap.get(channel.id);
    const status = health?.retry_scheduled_count ? `${health.retry_scheduled_count} pending retries` : (channel.last_delivered_at ? `Delivered ${fmtDateTime(channel.last_delivered_at)}` : "No successful deliveries yet");
    return `
      <li>
        <div>
          <strong>${channel.channel_type.toUpperCase()} · ${channel.target}</strong>
          <p>${status}${channel.last_error ? ` · Last error: ${channel.last_error}` : ""}</p>
        </div>
        <button class="button tertiary small-button" type="button" data-action="delete-channel" data-channel-id="${channel.id}" ${disabledAttr(!canEdit)}>Remove</button>
      </li>
    `;
  }).join("") || "<li><p>No notification channels configured yet.</p></li>";
}

function renderNotificationHealth(notificationHealth) {
  const card = document.getElementById("notification-health-card");
  const list = document.getElementById("notification-health-list");
  if (!card || !list || !notificationHealth) {
    return;
  }

  card.innerHTML = `
    <p><strong>Active channels:</strong> ${notificationHealth.active_channels}</p>
    <p><strong>Delivered in last 24h:</strong> ${notificationHealth.delivered_last_24h}</p>
    <p><strong>Retry queue:</strong> ${notificationHealth.retry_queue_depth}</p>
    <p><strong>Exhausted deliveries:</strong> ${notificationHealth.exhausted_deliveries}</p>
    <p><strong>Last external delivery:</strong> ${fmtDateTime(notificationHealth.last_delivery_at)}</p>
  `;

  list.innerHTML = notificationHealth.channels.map((channel) => `
    <li>
      <div>
        <strong>${channel.channel_type.toUpperCase()} · ${channel.target}</strong>
        <p>${channel.delivered_count} delivered · ${channel.retry_scheduled_count} queued · ${channel.exhausted_count} exhausted</p>
      </div>
      <div class="workspace-actions">
        <span>${channel.last_delivered_at ? `Last ok ${fmtDateTime(channel.last_delivered_at)}` : "Awaiting first delivery"}</span>
        ${channel.last_error ? `<span class="error-text">${channel.last_error}</span>` : "<span class=\"badge\">Healthy</span>"}
      </div>
    </li>
  `).join("") || "<li><p>No external channels configured yet.</p></li>";
}

function renderAlertInbox(profile) {
  const summary = document.getElementById("alert-inbox-summary");
  const list = document.getElementById("alert-inbox-list");
  if (!summary || !list) {
    return;
  }

  const canEdit = workspaceEditable();
  summary.textContent = `${profile.unread_alert_count} unread alert${profile.unread_alert_count === 1 ? "" : "s"}`;
  list.innerHTML = profile.recent_alerts.map((alert) => `
    <li class="${alert.is_read ? "" : "is-unread"}">
      <div>
        <strong>${alert.title}</strong>
        <p>${alert.message}</p>
        ${alert.error_detail ? `<p class="error-text">Delivery error: ${alert.error_detail}</p>` : ""}
        ${alert.next_attempt_at ? `<p class="panel-note">Next retry ${fmtDateTime(alert.next_attempt_at)}</p>` : ""}
      </div>
      <div class="workspace-actions">
        <span>${fmtPercent(alert.confidence)} · ${alert.asset} · ${alert.delivery_status}</span>
        ${alert.is_read ? "<span class=\"badge\">Read</span>" : `<button class="button tertiary small-button" type="button" data-action="mark-alert-read" data-alert-id="${alert.id}" ${disabledAttr(!canEdit)}>Mark read</button>`}
      </div>
    </li>
  `).join("") || "<li><p>No alert deliveries yet.</p></li>";
}

function renderUserProfile(profile, notificationHealth, authSession) {
  const tier = document.getElementById("workspace-tier");
  const followList = document.getElementById("follow-list");
  const watchlist = document.getElementById("watchlist-list");
  const alertRules = document.getElementById("alert-rule-list");

  const canEdit = workspaceEditable({ auth_session: authSession, user_profile: profile });

  if (tier) {
    tier.textContent = `${profile.display_name} · ${profile.tier}${canEdit ? "" : " · demo read-only"}`;
  }

  if (followList) {
    followList.innerHTML = profile.follows.map((follow) => `
      <li>
        <div>
          <strong>${follow.name}</strong>
          <p>Score ${fmtScore(follow.score)}</p>
        </div>
        <button class="button tertiary small-button" type="button" data-action="unfollow" data-bot-slug="${follow.bot_slug}" ${disabledAttr(!canEdit)}>Remove</button>
      </li>
    `).join("") || "<li><p>No followed bots yet.</p></li>";
  }

  if (watchlist) {
    watchlist.innerHTML = profile.watchlist.map((item) => `
      <li>
        <div>
          <strong>${item.asset}</strong>
          <p>${item.latest_price !== null ? fmtPrice(item.latest_price) : "No price"}${item.change_24h !== null ? ` · ${fmtSignedPercent(item.change_24h)}` : ""}</p>
        </div>
        <button class="button tertiary small-button" type="button" data-action="remove-watch" data-asset="${item.asset}" ${disabledAttr(!canEdit)}>Remove</button>
      </li>
    `).join("") || "<li><p>No watchlist assets yet.</p></li>";
  }

  if (alertRules) {
    alertRules.innerHTML = profile.alert_rules.map((rule) => `
      <li>
        <div>
          <strong>${rule.bot_slug || rule.asset || "Rule"}</strong>
          <p>Min confidence ${fmtPercent(rule.min_confidence)}${rule.asset ? ` · ${rule.asset}` : ""}</p>
        </div>
        <button class="button tertiary small-button" type="button" data-action="delete-alert-rule" data-rule-id="${rule.id}" ${disabledAttr(!canEdit)}>Remove</button>
      </li>
    `).join("") || "<li><p>No alert rules yet.</p></li>";
  }

  renderWalletConnections(profile, authSession);
  renderNotificationChannels(profile, notificationHealth);
  renderAlertInbox(profile);
}

async function renderBotDetail(slug) {
  const detail = document.getElementById("bot-detail-card");
  if (!detail || !slug) {
    return;
  }
  let bot;
  try {
    bot = await fetchJson(`/api/bots/${slug}`);
  } catch (error) {
    const fallback = latestSnapshot?.leaderboard?.find((candidate) => candidate.slug === slug);
    if (!fallback) {
      throw error;
    }
    bot = {
      ...fallback,
      calibration: Number(fallback.calibration || 0),
      provenance_score: Number(fallback.provenance_score || 0),
      asset_universe: fallback.asset_universe || [fallback.latest_asset || "BTC"],
      recent_predictions: [],
    };
  }
  const canEdit = workspaceEditable();
  const latestPrediction = bot.recent_predictions?.[0];
  const evidenceProviders = (latestPrediction?.provider_mix || []).map((provider) => humanizeKey(provider)).join(", ") || "Awaiting linked sources";
  const evidenceSources = (latestPrediction?.source_mix || []).map((source) => sourceTypeLabel(source)).join(", ") || "No source mix yet";
  selectedBotSlug = slug;
  detail.innerHTML = `
    <p class="eyebrow">${bot.archetype}</p>
    <h3>${bot.name}</h3>
    <p>${bot.thesis}</p>
    ${canEdit ? "" : '<p class="panel-note">Sign in to follow bots, manage watchlists, and create alert rules.</p>'}
    <div class="hero-actions compact-actions detail-actions">
      <button class="button tertiary" type="button" data-action="${bot.is_followed ? "unfollow" : "follow"}" data-bot-slug="${bot.slug}" ${disabledAttr(!canEdit)}>${bot.is_followed ? "Unfollow Bot" : "Follow Bot"}</button>
      <button class="button tertiary" type="button" data-action="add-watch" data-asset="${bot.latest_asset || bot.asset_universe[0]}" ${disabledAttr(!canEdit)}>Watch ${bot.latest_asset || bot.asset_universe[0]}</button>
      <button class="button tertiary" type="button" data-action="add-alert-rule" data-asset="${bot.latest_asset || bot.asset_universe[0]}" data-confidence="0.68" ${disabledAttr(!canEdit)}>Alert on ${bot.latest_asset || bot.asset_universe[0]}</button>
    </div>
    <dl class="detail-stats">
      <div><dt>Composite</dt><dd>${fmtScore(bot.score)}</dd></div>
      <div><dt>Hit rate</dt><dd>${fmtPercent(bot.hit_rate)}</dd></div>
      <div><dt>Calibration</dt><dd>${bot.calibration.toFixed(2)}</dd></div>
      <div><dt>Provenance</dt><dd>${fmtPercent(bot.provenance_score)}</dd></div>
      <div><dt>Last call</dt><dd>${bot.last_published_at ? fmtRelativeTime(bot.last_published_at) : "No archive yet"}</dd></div>
      <div><dt>Focus</dt><dd>${bot.focus}</dd></div>
      <div><dt>Risk style</dt><dd>${bot.risk_style}</dd></div>
      <div><dt>Universe</dt><dd>${bot.asset_universe.join(", ")}</dd></div>
    </dl>
    <div class="detail-evidence-grid">
      <article class="detail-evidence-card ${qualityCardClass(bot.provenance_score)}">
        <span>Evidence posture</span>
        <strong>${provenanceLabel(bot.provenance_score)}</strong>
        <p>${bot.name} is currently ranking on ${fmtPercent(bot.provenance_score)} provenance across its tracked archive.</p>
      </article>
      <article class="detail-evidence-card">
        <span>Latest source stack</span>
        <strong>${evidenceProviders}</strong>
        <p>${latestPrediction?.source_signal_count ? `${latestPrediction.source_signal_count} linked signals across ${evidenceSources}.` : "Recent calls have not been linked to source signals yet."}</p>
      </article>
      <article class="detail-evidence-card">
        <span>Latest call quality</span>
        <strong>${latestPrediction?.top_signal_quality !== null && latestPrediction?.top_signal_quality !== undefined ? qualityLabel(latestPrediction.top_signal_quality) : "Pending"}</strong>
        <p>${latestPrediction?.top_signal_quality !== null && latestPrediction?.top_signal_quality !== undefined ? `Strongest linked source scored ${fmtPercent(latestPrediction.top_signal_quality)} with ${latestPrediction.venue_support_share !== null && latestPrediction.venue_support_share !== undefined ? `${fmtPercent(latestPrediction.venue_support_share)} venue backing.` : "no venue backing yet."}` : "Run more linked signal intake to strengthen this bot's evidence trail."}</p>
      </article>
    </div>
  `;
  renderPredictions(bot.recent_predictions, "bot-detail-predictions");
}

async function resolvePublicSocialReadOrigin() {
  if (publicSocialReadOrigin !== null) {
    return publicSocialReadOrigin;
  }
  try {
    const runtime = await fetchJson("/api/runtime/public-origin");
    publicSocialReadOrigin = runtime?.social_read_origin || "";
  } catch (error) {
    console.warn("Public social origin discovery is temporarily unavailable.", error);
    publicSocialReadOrigin = "";
  }
  return publicSocialReadOrigin;
}

async function requestSocialTradingEnvelope(path) {
  if (!workspaceEditable()) {
    const publicOrigin = await resolvePublicSocialReadOrigin();
    if (publicOrigin) {
      try {
        const directResponse = await fetch(`${publicOrigin}${path}`, {
          credentials: "omit",
          headers: { "Content-Type": "application/json" },
        });
        if (directResponse.ok) {
          return {
            envelope: await directResponse.json(),
            deliveryMode: "direct-live-origin",
          };
        }
      } catch (error) {
        console.warn("Direct live social hydration failed; requesting the edge fallback.", error);
      }
    }
  }
  const edgeResponse = await fetch(path, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
  });
  if (!edgeResponse.ok) {
    throw new Error(`Failed to load ${path}`);
  }
  return {
    envelope: await edgeResponse.json(),
    deliveryMode: edgeResponse.headers.get("X-BITprivat-Data-Mode") || "live-origin",
  };
}

async function hydrateLiveSocialTrading({ fresh = false } = {}) {
  if (socialTradingLoadInFlight || !latestSnapshot) {
    return;
  }
  socialTradingLoadInFlight = true;
  try {
    const path = fresh ? `/api/social-trading?fresh=1&v=${Date.now()}` : "/api/social-trading";
    const { envelope, deliveryMode } = await requestSocialTradingEnvelope(path);
    if (!envelope?.social_trading) {
      return;
    }
    latestSnapshot.social_trading = {
      ...envelope.social_trading,
      delivery_mode: deliveryMode,
    };
    renderOperatorStrip(latestSnapshot);
    renderSocialTrading(latestSnapshot.social_trading);
    if (socialTradingRetryTimer) {
      clearTimeout(socialTradingRetryTimer);
      socialTradingRetryTimer = null;
    }
    if (["edge-fallback", "edge-snapshot"].includes(latestSnapshot.social_trading.delivery_mode)) {
      socialTradingRetryTimer = window.setTimeout(() => {
        void hydrateLiveSocialTrading();
      }, 2500);
    }
  } catch (error) {
    if (fresh) {
      throw error;
    }
    console.warn("Live social trader hydration is temporarily unavailable.", error);
  } finally {
    socialTradingLoadInFlight = false;
  }
}

async function loadDashboard(options = {}) {
  if (dashboardLoadInFlight) {
    return;
  }
  dashboardLoadInFlight = true;
  try {
    const snapshot = await fetchJson("/api/dashboard");
    latestSnapshot = snapshot;
    lastDashboardRefreshAt = new Date();
    nextDashboardRefreshAt = autoRefreshEnabled ? Date.now() + AUTO_REFRESH_MS : null;
    renderOperatorStrip(snapshot);
    renderHeroMeta(snapshot);
    renderRibbon(snapshot);
    renderLaunchReadiness(snapshot.launch_readiness);
    renderConnectorControl(snapshot.connector_control);
    renderInfrastructureReadiness(snapshot.infrastructure_readiness);
    renderProductionCutover(snapshot.production_cutover);
    renderMetrics(snapshot.summary);
    renderAssets(snapshot.assets);
    renderMarketTape(snapshot.assets);
    renderMarketConsole(snapshot);
    renderDashboardPulse(snapshot);
    renderMacroCards(snapshot.macro_snapshot, "dashboard-macro-grid", null, "dashboard-macro-summary");
    renderMacroChart(snapshot.macro_snapshot);
    renderWalletIntelligence(snapshot.wallet_intelligence);
    renderEdgeSnapshot(snapshot.edge_snapshot);
    renderPaperTrading(snapshot.paper_trading);
    renderPaperVenues(snapshot.paper_venues);
    renderSocialTrading(snapshot.social_trading);
    if (options.refreshSocial) {
      await hydrateLiveSocialTrading({ fresh: true });
    } else {
      void hydrateLiveSocialTrading();
    }
    void loadTraderIntelligence();
    await renderDashboardMarketChart(snapshot.assets);
    renderActivityFeed(snapshot);
    renderOperation(snapshot.latest_operation);
    renderProviderStatus(snapshot.provider_status);
    renderLeaderboard(snapshot.leaderboard, snapshot.user_profile);
    renderPredictions(snapshot.recent_predictions);
    renderSignals(snapshot.recent_signals);
    renderAuthPanel(snapshot.auth_session, snapshot.user_profile);
    renderOnboardingPanel(snapshot.auth_session, snapshot.user_profile);
    renderMfaPanel(snapshot.auth_session, snapshot.user_profile);
    renderBillingPanel(snapshot.user_profile?.billing, snapshot.auth_session);
    renderNotificationHealth(snapshot.notification_health);
    renderUserProfile(snapshot.user_profile, snapshot.notification_health, snapshot.auth_session);
    applyWorkspaceMode(snapshot);
    updateRefreshCountdown();
    if (document.getElementById("dashboard-metrics")) {
      startAutoRefresh();
    }

    const preferredSlug = selectedBotSlug || snapshot.leaderboard[0]?.slug;
    if (preferredSlug) {
      try {
        await renderBotDetail(preferredSlug);
      } catch (error) {
        console.warn("Bot detail is temporarily unavailable; the dashboard remains active.", error);
      }
    }
    if (!options.silent) {
      setStatus(`Dashboard synced ${fmtRelativeTime(lastDashboardRefreshAt)}. ${snapshot.summary.pending_predictions} predictions are still waiting for score windows.`);
    }
    applyBillingQueryStatus();
  } finally {
    dashboardLoadInFlight = false;
  }
}

async function loadStatusPage() {
  if (statusPageLoadInFlight) {
    return;
  }
  statusPageLoadInFlight = true;
  try {
    const [landing, providerEnvelope, pulseEnvelope, latestOperation] = await Promise.all([
      fetchJson("/api/landing"),
      fetchJson("/api/system/providers"),
      fetchJson("/api/system/pulse"),
      fetchJson("/api/operations/latest"),
    ]);
    renderStatusPage(
      landing,
      pulseEnvelope.system_pulse || landing.system_pulse,
      providerEnvelope.provider_status,
      latestOperation,
    );
  } finally {
    statusPageLoadInFlight = false;
  }
}

async function runCycle() {
  const button = document.getElementById("run-cycle-button");
  setRunCycleStageAnimation(true);
  if (button) {
    button.disabled = true;
  }
  try {
    const result = await fetchJson("/api/admin/run-cycle", { method: "POST" });
    await loadDashboard({ silent: true });
    if (result.cycle_started === false) {
      setStatus(result.cycle_message || "Production cycle control is protected. Latest operation snapshot refreshed.");
    } else {
      setStatus(`Pipeline cycle completed. ${result.alert_inbox.unread_count} unread alerts currently in inbox.`);
    }
  } catch (error) {
    setStatus(`Pipeline cycle failed: ${error.message}`);
  } finally {
    setRunCycleStageAnimation(false);
    if (button) {
      button.disabled = false;
    }
  }
}

async function retryNotifications() {
  const button = document.getElementById("retry-notifications-button");
  setStatus("Retrying failed external notifications...");
  if (button) {
    button.disabled = true;
  }
  try {
    const result = await fetchJson("/api/admin/retry-notifications", { method: "POST" });
    await loadDashboard({ silent: true });
    setStatus(`Retry pass finished. Scanned ${result.scanned_events}, delivered ${result.delivered}, rescheduled ${result.rescheduled}, exhausted ${result.exhausted}.`);
  } catch (error) {
    setStatus(`Retry pass failed: ${error.message}`);
  } finally {
    if (button) {
      button.disabled = false;
    }
  }
}

async function simulatePaperTrading() {
  const button = document.getElementById("simulate-paper-trading-button");
  setStatus("Simulating paper positions from the highest-conviction unresolved bot calls...");
  if (button) {
    button.disabled = true;
  }
  try {
    const endpoint = workspaceEditable() ? "/api/me/paper-trading/simulate" : "/api/admin/simulate-paper-trading";
    const result = await fetchJson(endpoint, { method: "POST" });
    await loadDashboard({ silent: true });
    setStatus(`Paper trading updated. Created ${result.created_positions} positions and closed ${result.closed_positions} resolved positions.`);
  } catch (error) {
    setStatus(`Paper trading simulation failed: ${error.message}`);
  } finally {
    if (button) {
      button.disabled = false;
    }
  }
}

async function followBot(botSlug) {
  await fetchJson("/api/me/follows", {
    method: "POST",
    body: JSON.stringify({ bot_slug: botSlug }),
  });
  await loadDashboard();
}

async function unfollowBot(botSlug) {
  await fetchJson(`/api/me/follows/${botSlug}`, { method: "DELETE" });
  await loadDashboard();
}

async function runSocialDiscovery(button = null) {
  if (button) {
    button.disabled = true;
  }
  setStatus("Running YouTube-first social trader discovery...");
  try {
    const result = await fetchJson("/api/social-traders/discover", { method: "POST" });
    await loadDashboard({ silent: true, refreshSocial: true });
    const warning = result.warnings?.length ? ` ${result.warnings[0]}` : "";
    setStatus(`Social discovery updated ${result.updated} profile(s), ${result.discovered} new.${warning}`);
  } catch (error) {
    setStatus(`Social discovery failed: ${error.message}`);
  } finally {
    if (button) {
      button.disabled = false;
    }
  }
}

async function analyzeSocialTraderTarget(form = null) {
  const activeForm = form || document.getElementById("social-analyze-form");
  const input = document.getElementById("social-analyze-input");
  const limitSelect = document.getElementById("social-analyze-limit");
  const button = document.getElementById("social-analyze-button");
  const query = input?.value?.trim() || "";
  const videoLimit = Number(limitSelect?.value || 12);
  if (query.length < 2) {
    setStatus("Add a YouTube trader name, @handle, channel URL, or video URL to build a creator bot.");
    input?.focus();
    return;
  }
  if (button) {
    button.disabled = true;
    button.textContent = "Building bot...";
  }
  if (activeForm) {
    activeForm.classList.add("is-running");
  }
  setStatus(`Building the YouTube evidence profile for creator bot: ${query}`);
  try {
    const result = await fetchJson("/api/social-traders/analyze", {
      method: "POST",
      body: JSON.stringify({ query, video_limit: videoLimit }),
    });
    await loadDashboard({ silent: true, refreshSocial: true });
    const analyzedNames = (result.traders || []).slice(0, 2).map((trader) => trader.display_name).filter(Boolean);
    const warning = result.warnings?.length ? ` ${result.warnings[0]}` : "";
    if (input) {
      input.value = "";
    }
    setStatus(`Creator bot dataset updated ${result.updated} profile(s), ${result.discovered} new${analyzedNames.length ? `: ${analyzedNames.join(", ")}` : ""}.${warning}`);
  } catch (error) {
    setStatus(`Creator bot build failed: ${error.message}`);
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = "Build Creator Bot";
    }
    if (activeForm) {
      activeForm.classList.remove("is-running");
    }
  }
}

async function configureSocialTrader(traderId, mode) {
  const allocationInput = document.querySelector(`[data-social-allocation-id="${traderId}"]`);
  const positionSelect = document.querySelector(`[data-social-position-id="${traderId}"]`);
  const allocationLimit = Number(allocationInput?.value || 500);
  const maxPositionPct = Number(positionSelect?.value || 0.12);
  setStatus(`Activating ${mode === "managed_paper" ? "managed paper" : "signal"} follow for social trader #${traderId}...`);
  await fetchJson("/api/me/social-traders/follow", {
    method: "POST",
    body: JSON.stringify({
      trader_id: Number(traderId),
      mode,
      allocation_limit_usd: allocationLimit,
      max_position_pct: maxPositionPct,
      auto_rebalance: true,
    }),
  });
  await loadDashboard({ silent: true, refreshSocial: true });
  setStatus(mode === "managed_paper"
    ? "Managed paper allocation is active. Live-money execution remains legally gated."
    : "Signal follow is active. Alerts and evidence are now tracked for this trader.");
}

async function diversifySocialPortfolio(button = null) {
  if (button) {
    button.disabled = true;
  }
  setStatus("Building diversified managed-paper allocation across top social traders...");
  try {
    await fetchJson("/api/me/social-traders/diversify", {
      method: "POST",
      body: JSON.stringify({
        budget_usd: 1500,
        mode: "managed_paper",
        trader_count: 3,
        max_position_pct: 0.12,
      }),
    });
    await loadDashboard({ silent: true, refreshSocial: true });
    setStatus("Diversified managed-paper allocation created across the top social trader scorecards.");
  } catch (error) {
    setStatus(`Diversification failed: ${error.message}`);
  } finally {
    if (button) {
      button.disabled = false;
    }
  }
}

async function executeSocialManagedPaper(button = null) {
  if (button) {
    button.disabled = true;
    button.textContent = "Running...";
  }
  setStatus("Executing managed-paper social trader signals through the paper ledger...");
  try {
    const result = await fetchJson("/api/me/social-traders/execute", {
      method: "POST",
      body: JSON.stringify({
        max_positions: 3,
        min_confidence: 0.55,
      }),
    });
    latestSocialExecution = result;
    await loadDashboard({ silent: true, refreshSocial: true });
    const headline = result.created_positions
      ? `Opened ${result.created_positions} managed-paper position(s) from ${result.created_predictions} social prediction(s).`
      : "No new managed-paper positions were opened.";
    const firstDecision = result.decisions?.[0];
    const detail = firstDecision
      ? ` Latest decision: ${humanizeKey(firstDecision.action)} ${firstDecision.asset} because ${firstDecision.reason}`
      : result.messages?.length ? ` ${result.messages[0]}` : "";
    setStatus(`${headline}${detail}`);
  } catch (error) {
    setStatus(`Managed-paper execution failed: ${error.message}`);
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = "Run Managed Paper Bot";
    }
  }
}

async function addWatchlist(asset) {
  await fetchJson("/api/me/watchlist", {
    method: "POST",
    body: JSON.stringify({ asset }),
  });
  await loadDashboard();
}

async function removeWatchlist(asset) {
  await fetchJson(`/api/me/watchlist/${asset}`, { method: "DELETE" });
  await loadDashboard();
}

async function addAlertRule(asset, confidence = 0.68) {
  await fetchJson("/api/me/alert-rules", {
    method: "POST",
    body: JSON.stringify({ asset, min_confidence: Number(confidence) }),
  });
  await loadDashboard();
}

async function deleteAlertRule(ruleId) {
  await fetchJson(`/api/me/alert-rules/${ruleId}`, { method: "DELETE" });
  await loadDashboard();
}

async function markAlertRead(alertId) {
  await fetchJson(`/api/me/alerts/${alertId}/read`, { method: "POST" });
  await loadDashboard();
}

async function markAllAlertsRead() {
  await fetchJson("/api/me/alerts/read-all", { method: "POST" });
  await loadDashboard();
}

async function addNotificationChannel(channelType, target, secret) {
  await fetchJson("/api/me/notification-channels", {
    method: "POST",
    body: JSON.stringify({
      channel_type: channelType,
      target,
      secret: secret || null,
    }),
  });
  await loadDashboard();
}

async function deleteNotificationChannel(channelId) {
  await fetchJson(`/api/me/notification-channels/${channelId}`, { method: "DELETE" });
  await loadDashboard();
}

function isEvmWalletChain(chain) {
  return new Set(["ethereum", "arbitrum", "base", "polygon", "optimism", "bsc", "avalanche"]).has(String(chain || "").toLowerCase());
}

async function requestEvmWalletAddress(preferredAddress = "") {
  const provider = window.ethereum;
  if (!provider || typeof provider.request !== "function") {
    throw new Error("No EVM wallet detected. Install MetaMask, Rabby, or Coinbase Wallet.");
  }
  const accounts = await provider.request({ method: "eth_requestAccounts" });
  if (!Array.isArray(accounts) || accounts.length === 0) {
    throw new Error("Wallet did not expose any account.");
  }
  const normalizedPreferred = String(preferredAddress || "").trim().toLowerCase();
  if (!normalizedPreferred) {
    return String(accounts[0]).toLowerCase();
  }
  const matched = accounts.find((account) => String(account).toLowerCase() === normalizedPreferred);
  if (!matched) {
    throw new Error("Selected wallet address does not match the connected wallet account.");
  }
  return String(matched).toLowerCase();
}

async function signEvmChallengeMessage(message, address) {
  const provider = window.ethereum;
  if (!provider || typeof provider.request !== "function") {
    throw new Error("No EVM wallet provider available for message signing.");
  }
  try {
    return await provider.request({
      method: "personal_sign",
      params: [message, address],
    });
  } catch (primaryError) {
    try {
      return await provider.request({
        method: "personal_sign",
        params: [address, message],
      });
    } catch {
      throw primaryError;
    }
  }
}

async function connectWallet(chain, provider, address, label) {
  const normalizedChain = String(chain || "ethereum").toLowerCase();
  if (isEvmWalletChain(normalizedChain)) {
    const verifiedAddress = await requestEvmWalletAddress(address);
    const challenge = await fetchJson("/api/me/wallets/challenge", {
      method: "POST",
      body: JSON.stringify({
        chain: normalizedChain,
        provider,
        address: verifiedAddress,
        label: label || null,
      }),
    });
    const signature = await signEvmChallengeMessage(challenge.message, verifiedAddress);
    await fetchJson("/api/me/wallets/verify", {
      method: "POST",
      body: JSON.stringify({
        challenge_id: challenge.challenge_id,
        signature,
      }),
    });
  } else {
    await fetchJson("/api/me/wallets", {
      method: "POST",
      body: JSON.stringify({
        chain: normalizedChain,
        provider,
        address,
        label: label || null,
      }),
    });
  }
  await loadDashboard();
}

async function disconnectWallet(walletId) {
  await fetchJson(`/api/me/wallets/${walletId}`, { method: "DELETE" });
  await loadDashboard();
}

async function startBillingCheckout(planKey) {
  const payload = await fetchJson("/api/me/billing/checkout-session", {
    method: "POST",
    body: JSON.stringify({
      plan_key: planKey || "basic",
      success_path: "/dashboard?billing=success",
      cancel_path: "/dashboard?billing=cancelled",
    }),
  });
  window.location.assign(payload.url);
}

async function openBillingPortal() {
  const payload = await fetchJson("/api/me/billing/portal-session", {
    method: "POST",
    body: JSON.stringify({
      return_path: "/dashboard#account-section",
    }),
  });
  window.location.assign(payload.url);
}

async function loginUser(email, password, otpCode = "") {
  const payload = {
    email,
    password,
  };
  const normalizedOtp = String(otpCode || "").trim();
  if (normalizedOtp) {
    payload.otp_code = normalizedOtp;
  }
  await fetchJson("/api/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  await loadDashboard();
  setStatus("Signed in successfully.");
}

async function registerUser(displayName, email, password) {
  await fetchJson("/api/auth/register", {
    method: "POST",
    body: JSON.stringify({ display_name: displayName, email, password }),
  });
  await loadDashboard();
  setStatus("Account created and signed in.");
}

async function logoutUser() {
  await fetchJson("/api/auth/logout", { method: "POST" });
  await loadDashboard();
  setStatus("Signed out. You are back in demo mode.");
}

async function forgotPassword(email) {
  const payload = await fetchJson("/api/auth/forgot-password", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
  if (payload?.debug_reset_token) {
    const tokenField = document.getElementById("reset-token");
    if (tokenField) {
      tokenField.value = payload.debug_reset_token;
    }
    setStatus(`Recovery token generated for testing: ${payload.debug_reset_token}`);
  } else {
    setStatus(payload?.message || "If that email exists, reset instructions were generated.");
  }
}

async function resetPassword(token, newPassword) {
  await fetchJson("/api/auth/reset-password", {
    method: "POST",
    body: JSON.stringify({ token, new_password: newPassword }),
  });
  await loadDashboard();
  setStatus("Password reset complete. You are now signed in.");
}

function renderMfaSetupPayload(payload) {
  const setupCard = document.getElementById("mfa-setup-card");
  const uriElement = document.getElementById("mfa-otpauth-uri");
  if (!setupCard || !uriElement) {
    return;
  }
  if (payload?.otpauth_uri) {
    setupCard.classList.remove("hidden");
    uriElement.textContent = payload.otpauth_uri;
  } else {
    setupCard.classList.add("hidden");
    uriElement.textContent = "";
  }
}

async function startMfaSetup() {
  const payload = await fetchJson("/api/auth/mfa/setup", {
    method: "POST",
  });
  renderMfaSetupPayload(payload);
  await loadDashboard({ silent: true });
  setStatus(payload?.pending_setup ? "MFA setup initialized. Scan the URI and confirm with your code." : "MFA is already enabled.");
}

async function enableMfa(code) {
  await fetchJson("/api/auth/mfa/enable", {
    method: "POST",
    body: JSON.stringify({ code }),
  });
  const setupCard = document.getElementById("mfa-setup-card");
  const uriElement = document.getElementById("mfa-otpauth-uri");
  if (setupCard) {
    setupCard.classList.add("hidden");
  }
  if (uriElement) {
    uriElement.textContent = "";
  }
  await loadDashboard({ silent: true });
  setStatus("MFA enabled for this workspace.");
}

async function disableMfa(code) {
  await fetchJson("/api/auth/mfa/disable", {
    method: "POST",
    body: JSON.stringify({ code }),
  });
  await loadDashboard({ silent: true });
  setStatus("MFA disabled.");
}

async function saveOnboardingProfile(payload) {
  await fetchJson("/api/auth/onboarding", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  await loadDashboard({ silent: true });
  setStatus("Onboarding profile saved.");
}

function bindForms() {
  const simulationForm = document.getElementById("simulation-form");
  const watchlistForm = document.getElementById("watchlist-form");
  const alertRuleForm = document.getElementById("alert-rule-form");
  const loginForm = document.getElementById("login-form");
  const registerForm = document.getElementById("register-form");
  const forgotPasswordForm = document.getElementById("forgot-password-form");
  const resetPasswordForm = document.getElementById("reset-password-form");
  const mfaStartButton = document.getElementById("mfa-start-setup-button");
  const mfaEnableForm = document.getElementById("mfa-enable-form");
  const mfaDisableForm = document.getElementById("mfa-disable-form");
  const onboardingForm = document.getElementById("onboarding-form");
  const notificationChannelForm = document.getElementById("notification-channel-form");
  const walletConnectForm = document.getElementById("wallet-connect-form");
  const socialAnalyzeForm = document.getElementById("social-analyze-form");
  const traderIntelligenceForm = document.getElementById("trader-intelligence-form");

  if (simulationForm) {
    simulationForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      await runSimulation();
    });
  }
  const saveStrategyButton = document.getElementById("save-current-strategy-button");
  if (saveStrategyButton) {
    saveStrategyButton.addEventListener("click", saveCurrentStrategy);
  }
  const refreshStrategiesButton = document.getElementById("refresh-strategies-button");
  if (refreshStrategiesButton) {
    refreshStrategiesButton.addEventListener("click", async () => {
      await Promise.all([loadSavedStrategies(), loadSavedBacktests()]);
      setStatus("Strategy vault refreshed.");
    });
  }
  const savedStrategyList = document.getElementById("saved-strategy-list");
  if (savedStrategyList) {
    savedStrategyList.addEventListener("click", async (event) => {
      if (!(event.target instanceof Element)) {
        return;
      }
      const loadButton = event.target.closest("[data-load-strategy-id]");
      const runButton = event.target.closest("[data-run-strategy-id]");
      if (loadButton) {
        loadSavedStrategyIntoForm(loadButton.dataset.loadStrategyId);
      }
      if (runButton) {
        await runSavedStrategyBacktest(runButton.dataset.runStrategyId);
      }
    });
  }
  const simulationStrategyInput = document.getElementById("simulation-strategy-input");
  if (simulationStrategyInput) {
    simulationStrategyInput.addEventListener("change", syncStrategyCreatorPanel);
  }

  if (socialAnalyzeForm) {
    socialAnalyzeForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      await analyzeSocialTraderTarget(socialAnalyzeForm);
    });
  }

  if (traderIntelligenceForm) {
    traderIntelligenceForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      await createTraderIntelligenceProfile(traderIntelligenceForm);
    });
  }

  const traderIntelligenceCompareButton = document.getElementById("trader-intelligence-compare-button");
  if (traderIntelligenceCompareButton) {
    traderIntelligenceCompareButton.addEventListener("click", compareTraderIntelligence);
  }
  const traderIntelligenceAddButton = document.getElementById("trader-intelligence-add-button");
  if (traderIntelligenceAddButton) {
    traderIntelligenceAddButton.addEventListener("click", openTraderIntelligenceAddModal);
  }
  const traderIntelligenceRefreshButton = document.getElementById("trader-intelligence-refresh-button");
  if (traderIntelligenceRefreshButton) {
    traderIntelligenceRefreshButton.addEventListener("click", async () => {
      await loadTraderIntelligence();
      setStatus("Trader Intelligence workspace refreshed.");
    });
  }
  [
    ["trader-intelligence-search", "query", "input"],
    ["trader-intelligence-filter-category", "category", "change"],
    ["trader-intelligence-filter-status", "status", "change"],
    ["trader-intelligence-filter-source", "source", "change"],
    ["trader-intelligence-filter-confidence", "confidence", "change"],
    ["trader-intelligence-sort", "sort", "change"],
    ["trader-intelligence-insight-search", "insightQuery", "input"],
    ["trader-intelligence-insight-type", "insightType", "change"],
    ["trader-intelligence-insight-confidence", "insightConfidence", "change"],
  ].forEach(([id, key, eventName]) => {
    const control = document.getElementById(id);
    if (control) {
      control.addEventListener(eventName, () => {
        traderIntelligenceState.filters[key] = control.value || "";
        renderTraderIntelligence(traderIntelligenceState.workspace);
      });
    }
  });

  const socialSearch = document.getElementById("social-marketplace-search");
  if (socialSearch) {
    socialSearch.addEventListener("input", () => {
      window.clearTimeout(socialMarketplaceFilterTimer);
      socialMarketplaceFilterTimer = window.setTimeout(() => {
        socialMarketplaceState.query = socialSearch.value || "";
        renderSocialTradingFromFilters();
      }, 160);
    });
  }
  [
    ["social-asset-filter", "asset"],
    ["social-risk-filter", "risk"],
    ["social-mode-filter", "mode"],
    ["social-sort-select", "sort"],
  ].forEach(([id, key]) => {
    const control = document.getElementById(id);
    if (control) {
      control.addEventListener("change", () => {
        socialMarketplaceState[key] = control.value || "all";
        renderSocialTradingFromFilters();
      });
    }
  });
  const socialReset = document.getElementById("social-reset-filters-button");
  if (socialReset) {
    socialReset.addEventListener("click", () => {
      socialMarketplaceState = {
        query: "",
        asset: "all",
        risk: "all",
        mode: "all",
        sort: "score",
      };
      renderSocialTradingFromFilters();
      setStatus("Social trader marketplace filters reset.");
    });
  }

  if (watchlistForm) {
    watchlistForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!requireEditable()) {
        return;
      }
      const assetInput = document.getElementById("watchlist-input");
      const asset = assetInput?.value?.trim()?.toUpperCase();
      if (!asset) {
        return;
      }
      try {
        await addWatchlist(asset);
        assetInput.value = "";
      } catch (error) {
        setStatus(error.message);
      }
    });
  }

  if (alertRuleForm) {
    alertRuleForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!requireEditable()) {
        return;
      }
      const assetInput = document.getElementById("alert-asset-input");
      const confidenceInput = document.getElementById("alert-confidence-input");
      const asset = assetInput?.value?.trim()?.toUpperCase();
      const confidence = confidenceInput?.value || "0.68";
      if (!asset) {
        return;
      }
      try {
        await addAlertRule(asset, confidence);
        assetInput.value = "";
      } catch (error) {
        setStatus(error.message);
      }
    });
  }

  if (loginForm) {
    loginForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const email = document.getElementById("login-email")?.value?.trim();
      const password = document.getElementById("login-password")?.value || "";
      const otpCode = document.getElementById("login-otp")?.value || "";
      if (!email || !password) {
        return;
      }
      try {
        await loginUser(email, password, otpCode);
        loginForm.reset();
      } catch (error) {
        setStatus(error.message);
      }
    });
  }

  if (registerForm) {
    registerForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const displayName = document.getElementById("register-name")?.value?.trim();
      const email = document.getElementById("register-email")?.value?.trim();
      const password = document.getElementById("register-password")?.value || "";
      if (!displayName || !email || !password) {
        return;
      }
      try {
        await registerUser(displayName, email, password);
        registerForm.reset();
      } catch (error) {
        setStatus(error.message);
      }
    });
  }

  if (forgotPasswordForm) {
    forgotPasswordForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const email = document.getElementById("forgot-email")?.value?.trim();
      if (!email) {
        return;
      }
      try {
        await forgotPassword(email);
      } catch (error) {
        setStatus(error.message);
      }
    });
  }

  if (resetPasswordForm) {
    resetPasswordForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const token = document.getElementById("reset-token")?.value?.trim();
      const newPassword = document.getElementById("reset-password")?.value || "";
      if (!token || !newPassword) {
        return;
      }
      try {
        await resetPassword(token, newPassword);
        resetPasswordForm.reset();
      } catch (error) {
        setStatus(error.message);
      }
    });
  }

  if (mfaStartButton) {
    mfaStartButton.addEventListener("click", async () => {
      try {
        if (!requireEditable()) {
          return;
        }
        await startMfaSetup();
      } catch (error) {
        setStatus(error.message);
      }
    });
  }

  if (mfaEnableForm) {
    mfaEnableForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!requireEditable()) {
        return;
      }
      const code = document.getElementById("mfa-enable-code")?.value?.trim();
      if (!code) {
        return;
      }
      try {
        await enableMfa(code);
        mfaEnableForm.reset();
      } catch (error) {
        setStatus(error.message);
      }
    });
  }

  if (mfaDisableForm) {
    mfaDisableForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!requireEditable()) {
        return;
      }
      const code = document.getElementById("mfa-disable-code")?.value?.trim();
      if (!code) {
        return;
      }
      try {
        await disableMfa(code);
        mfaDisableForm.reset();
      } catch (error) {
        setStatus(error.message);
      }
    });
  }

  if (onboardingForm) {
    onboardingForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!requireEditable()) {
        return;
      }
      const stage = document.getElementById("onboarding-stage")?.value || "identity";
      const acceptRiskDisclosure = Boolean(document.getElementById("onboarding-risk")?.checked);
      const suitabilityRaw = document.getElementById("onboarding-suitability-score")?.value;
      const suitabilityScore = suitabilityRaw === "" || suitabilityRaw === undefined ? null : Number(suitabilityRaw);
      const kycStatus = document.getElementById("onboarding-kyc-status")?.value || "not_started";
      const preferredLanguage = document.getElementById("onboarding-language")?.value || "en";
      const preferredTheme = document.getElementById("onboarding-theme")?.value || "day";
      const preferredWorkspaceMode = document.getElementById("onboarding-workspace-mode")?.value || "pro";
      const timezone = document.getElementById("onboarding-timezone")?.value?.trim() || "UTC";
      const completed = Boolean(document.getElementById("onboarding-complete")?.checked);

      const payload = {
        stage,
        accept_risk_disclosure: acceptRiskDisclosure,
        kyc_status: kycStatus,
        preferred_language: preferredLanguage,
        preferred_theme: preferredTheme,
        preferred_workspace_mode: preferredWorkspaceMode,
        timezone,
        completed,
      };
      if (suitabilityScore !== null && Number.isFinite(suitabilityScore)) {
        payload.suitability_score = suitabilityScore;
      }

      try {
        await saveOnboardingProfile(payload);
      } catch (error) {
        setStatus(error.message);
      }
    });
  }

  if (notificationChannelForm) {
    notificationChannelForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!requireEditable()) {
        return;
      }
      const channelType = document.getElementById("channel-type-input")?.value;
      const target = document.getElementById("channel-target-input")?.value?.trim();
      const secret = document.getElementById("channel-secret-input")?.value?.trim();
      if (!channelType || !target) {
        return;
      }
      try {
        await addNotificationChannel(channelType, target, secret);
        notificationChannelForm.reset();
        document.getElementById("channel-type-input").value = "webhook";
      } catch (error) {
        setStatus(error.message);
      }
    });
  }

  if (walletConnectForm) {
    walletConnectForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!requireEditable()) {
        return;
      }
      const chain = document.getElementById("wallet-chain-input")?.value || "ethereum";
      const provider = document.getElementById("wallet-provider-input")?.value || "walletconnect";
      const address = document.getElementById("wallet-address-input")?.value?.trim();
      const label = document.getElementById("wallet-label-input")?.value?.trim() || "";
      if (!address) {
        return;
      }
      try {
        setStatus(
          isEvmWalletChain(chain)
            ? "Open your wallet and approve the BITprivat signature challenge."
            : "Connecting wallet to workspace..."
        );
        await connectWallet(chain, provider, address, label);
        walletConnectForm.reset();
        const chainSelect = document.getElementById("wallet-chain-input");
        const providerSelect = document.getElementById("wallet-provider-input");
        if (chainSelect) {
          chainSelect.value = "ethereum";
        }
        if (providerSelect) {
          providerSelect.value = "walletconnect";
        }
        setStatus(
          isEvmWalletChain(chain)
            ? "Wallet connected and signature verified."
            : "Wallet connected."
        );
      } catch (error) {
        setStatus(error.message);
      }
    });
  }
}

function normalizeTradingAsset(symbol) {
  const normalized = String(symbol || "BTC").trim().toUpperCase();
  if (normalized.startsWith("POLY")) {
    return "POLY";
  }
  return normalized
    .replace(/^POLY:\s*/, "POLY-")
    .replace(/-USD$/, "")
    .replace(/-PERP$/, "")
    .split(/[\s:/]/)[0]
    .replace(/[^A-Z0-9]/g, "");
}

function normalizeOrderType(value) {
  const normalized = String(value || "market").trim().toLowerCase().replace(/[\s-]+/g, "_");
  if (["market", "limit", "stop", "stop_limit", "trailing"].includes(normalized)) {
    return normalized;
  }
  return "market";
}

function activeTradingSymbol() {
  return document.getElementById("trading-selected-symbol")?.textContent?.trim() || "BTC-USD";
}

function buildProfessionalOrderRequest() {
  const workspace = document.getElementById("trading-workspace-section");
  const symbol = activeTradingSymbol();
  const side = workspace?.querySelector("[data-order-side].active")?.dataset.orderSide || "buy";
  const orderType = normalizeOrderType(document.getElementById("ticket-order-type")?.value || "Market");
  const quantity = Number(document.getElementById("ticket-quantity")?.value || 0);
  const price = Number(document.getElementById("ticket-price")?.value || 0);
  const request = {
    venue: "paper",
    asset: normalizeTradingAsset(symbol),
    side,
    order_type: orderType,
    is_paper: true,
    client_order_id: `ui-${Date.now()}`,
  };
  if (quantity > 0) {
    request.quantity = quantity;
  }
  if (orderType === "limit" && price > 0) {
    request.price = price;
  }
  return request;
}

function buildSimpleOrderRequest(side) {
  const symbol = document.getElementById("simple-trade-symbol")?.value || "BTC-USD";
  const amount = Number(document.getElementById("simple-trade-amount")?.value || 0);
  return {
    venue: "paper",
    asset: normalizeTradingAsset(symbol),
    side,
    order_type: "market",
    is_paper: true,
    notional_usd: amount > 0 ? amount : 250,
    client_order_id: `simple-${Date.now()}`,
  };
}

function openOrderPreviewWindow() {
  const windowEl = document.getElementById("order-preview-window");
  if (!windowEl) {
    return;
  }
  windowEl.classList.remove("hidden");
  document.body.classList.add("order-preview-open");
  windowEl.querySelector("[data-order-preview-close]")?.focus({ preventScroll: true });
}

function closeOrderPreviewWindow() {
  const windowEl = document.getElementById("order-preview-window");
  if (!windowEl) {
    return;
  }
  windowEl.classList.add("hidden");
  document.body.classList.remove("order-preview-open");
}

function renderOrderPreviewLoading(request) {
  openOrderPreviewWindow();
  currentOrderPreview = null;
  currentOrderRequest = request;
  const title = document.getElementById("order-preview-title");
  const subtitle = document.getElementById("order-preview-subtitle");
  const summary = document.getElementById("order-preview-summary");
  const checks = document.getElementById("order-preview-checks");
  const mode = document.getElementById("order-preview-mode");
  const riskSummary = document.getElementById("order-preview-risk-summary");
  const submit = document.getElementById("order-preview-submit");
  const error = document.getElementById("order-preview-error");
  if (title) {
    title.textContent = `Preview ${request.side.toUpperCase()} ${request.asset}`;
  }
  if (subtitle) {
    subtitle.textContent = "Calculating estimated fill, fee, cash impact, and risk gates.";
  }
  if (summary) {
    summary.innerHTML = Array.from({ length: 6 }, (_, index) => `<div class="order-preview-skeleton" style="--delay:${index * 25}ms"></div>`).join("");
  }
  if (checks) {
    checks.innerHTML = '<li class="order-preview-check check-warn"><span>Checking risk engine...</span><strong>Pending</strong></li>';
  }
  if (mode) {
    mode.textContent = "Previewing";
    mode.className = "status-pill status-pill-delayed";
  }
  if (riskSummary) {
    riskSummary.textContent = "Running paper ledger checks...";
  }
  if (submit) {
    submit.disabled = true;
    submit.textContent = "Submit paper order";
  }
  if (error) {
    error.classList.add("hidden");
    error.textContent = "";
  }
}

function renderOrderPreview(preview) {
  currentOrderPreview = preview;
  const summary = document.getElementById("order-preview-summary");
  const checks = document.getElementById("order-preview-checks");
  const mode = document.getElementById("order-preview-mode");
  const riskSummary = document.getElementById("order-preview-risk-summary");
  const submit = document.getElementById("order-preview-submit");
  const subtitle = document.getElementById("order-preview-subtitle");
  const approved = Boolean(preview?.risk?.approved);
  const sideLabel = String(preview.side || "").toUpperCase();
  const checkTone = (status) => status === "pass" ? "pass" : (status === "warn" ? "warn" : "fail");

  if (summary) {
    summary.innerHTML = [
      ["Symbol", `${escapeHtml(preview.asset)} / ${escapeHtml(preview.venue)}`],
      ["Side", sideLabel],
      ["Est. fill", preview.estimated_fill_price ? `${fmtUsd(preview.estimated_fill_price, preview.estimated_fill_price > 10 ? 2 : 4)} / unit` : "--"],
      ["Quantity", Number(preview.quantity || 0).toLocaleString(currentLocale(), { maximumFractionDigits: 8 })],
      ["Notional", fmtUsd(preview.notional_usd, 2)],
      ["Fee", fmtUsd(preview.estimated_fee, 2)],
      ["Total cost", fmtUsd(preview.estimated_total_cost, 2)],
      ["Cash after", preview.cash_balance === null || preview.cash_balance === undefined ? "--" : fmtUsd(Number(preview.cash_balance) - Number(preview.estimated_total_cost || 0), 2)],
    ].map(([label, value]) => `
      <div class="order-preview-metric">
        <span>${label}</span>
        <strong class="finance-number">${value}</strong>
      </div>
    `).join("");
  }
  if (checks) {
    checks.innerHTML = (preview.risk?.checks || []).map((check) => `
      <li class="order-preview-check check-${checkTone(check.status)}">
        <span>${escapeHtml(check.label)}</span>
        <strong>${escapeHtml(check.status)}</strong>
        <small>${escapeHtml(check.detail)}</small>
      </li>
    `).join("");
  }
  if (mode) {
    mode.textContent = approved ? "Risk passed" : "Blocked";
    mode.className = approved ? "status-pill status-pill-connected" : "status-pill status-pill-disconnected";
  }
  if (riskSummary) {
    riskSummary.textContent = preview.message || (approved ? "Paper order can be submitted." : "Resolve risk blockers before submitting.");
  }
  if (subtitle) {
    subtitle.textContent = approved
      ? "This remains internal paper trading. No live venue receives the order."
      : "The submit button is locked until every blocker is resolved.";
  }
  if (submit) {
    submit.disabled = !approved;
    submit.textContent = approved ? "Submit paper order" : "Blocked by risk";
  }
}

function renderOrderPreviewError(message) {
  openOrderPreviewWindow();
  const summary = document.getElementById("order-preview-summary");
  const checks = document.getElementById("order-preview-checks");
  const mode = document.getElementById("order-preview-mode");
  const riskSummary = document.getElementById("order-preview-risk-summary");
  const submit = document.getElementById("order-preview-submit");
  const error = document.getElementById("order-preview-error");
  if (summary) {
    summary.innerHTML = "";
  }
  if (checks) {
    checks.innerHTML = "";
  }
  if (mode) {
    mode.textContent = "Unavailable";
    mode.className = "status-pill status-pill-disconnected";
  }
  if (riskSummary) {
    riskSummary.textContent = "Preview could not be generated.";
  }
  if (submit) {
    submit.disabled = true;
  }
  if (error) {
    error.textContent = message;
    error.classList.remove("hidden");
  }
}

async function previewTradingOrder(request) {
  if (!requireEditable()) {
    renderOrderPreviewError("Sign in or create an account to preview orders in a personal paper ledger.");
    return;
  }
  renderOrderPreviewLoading(request);
  try {
    const preview = await fetchJson("/api/v1/trading/preview", {
      method: "POST",
      body: JSON.stringify(request),
    });
    renderOrderPreview(preview);
    setStatus(preview.risk?.approved
      ? `Preview ready for ${request.side.toUpperCase()} ${request.asset}. Review and confirm in the order window.`
      : `Preview blocked for ${request.asset}: ${(preview.risk?.blockers || [preview.message])[0]}`);
  } catch (error) {
    renderOrderPreviewError(error.message);
    setStatus(`Order preview failed: ${error.message}`);
  }
}

async function submitPreviewedPaperOrder() {
  if (!currentOrderPreview?.risk?.approved || !currentOrderRequest) {
    setStatus("Order submit is locked until the preview risk checks pass.");
    return;
  }
  const submit = document.getElementById("order-preview-submit");
  if (submit) {
    submit.disabled = true;
    submit.textContent = "Submitting...";
  }
  try {
    const order = await fetchJson("/api/v1/trading/orders", {
      method: "POST",
      body: JSON.stringify(currentOrderRequest),
    });
    closeOrderPreviewWindow();
    await loadDashboard({ silent: true });
    setStatus(`Paper order filled: ${order.side.toUpperCase()} ${order.quantity} ${order.asset} at ${fmtUsd(order.avg_fill_price, 2)}. Fee ${fmtUsd(order.fee, 2)}.`);
  } catch (error) {
    renderOrderPreviewError(error.message);
    setStatus(`Paper order failed: ${error.message}`);
  } finally {
    if (submit) {
      submit.textContent = "Submit paper order";
    }
  }
}

function initProfessionalTradingWorkspace() {
  const workspace = document.getElementById("trading-workspace-section");
  if (!workspace) {
    return;
  }

  const livePrice = document.getElementById("trading-live-price");
  const liveChange = document.getElementById("trading-live-change");
  const selectedSymbol = document.getElementById("trading-selected-symbol");
  const selectedVenue = document.getElementById("trading-selected-venue");
  const ticketPrice = document.getElementById("ticket-price");
  const confirmation = document.getElementById("simple-confirmation");

  workspace.querySelectorAll("[data-trading-mode]").forEach((button) => {
    button.addEventListener("click", () => {
      const mode = button.dataset.tradingMode || "pro";
      workspace.dataset.mode = mode;
      workspace.querySelectorAll("[data-trading-mode]").forEach((modeButton) => {
        const isActive = modeButton === button;
        modeButton.classList.toggle("active", isActive);
        modeButton.setAttribute("aria-pressed", String(isActive));
      });
      setStatus(mode === "simple"
        ? "Mod Simplu activ: chart mare, suma fiat si confirmare in doi pasi."
        : "Mod Pro activ: watchlist, chart, order book, ticket si pozitii intr-un cockpit complet.");
    });
  });

  workspace.querySelectorAll("[data-trading-symbol]").forEach((row) => {
    row.addEventListener("click", () => {
      const symbol = row.dataset.tradingSymbol || "BTC-USD";
      const numericPrice = Number(row.dataset.tradingPrice || 0);
      const formattedPrice = numericPrice > 1 ? `$${numericPrice.toLocaleString(undefined, { maximumFractionDigits: 2 })}` : `$${numericPrice.toFixed(2)}`;
      workspace.querySelectorAll("[data-trading-symbol]").forEach((candidate) => candidate.classList.toggle("active", candidate === row));
      if (selectedSymbol) {
        selectedSymbol.textContent = symbol;
      }
      if (selectedVenue) {
        selectedVenue.textContent = symbol.startsWith("POLY") ? "Prediction market" : symbol.includes("PERP") ? "Crypto perpetual" : "Crypto spot";
      }
      if (livePrice) {
        livePrice.textContent = formattedPrice;
        livePrice.classList.remove("price-flash-down");
        livePrice.classList.add("price-flash-up");
      }
      if (liveChange) {
        const tone = row.querySelector(".profit-text, .loss-text");
        liveChange.textContent = tone?.textContent ? `${tone.textContent} / 24h` : "Live";
        liveChange.classList.toggle("profit-text", tone?.classList.contains("profit-text"));
        liveChange.classList.toggle("loss-text", tone?.classList.contains("loss-text"));
      }
      if (ticketPrice && numericPrice) {
        ticketPrice.value = numericPrice.toFixed(numericPrice > 10 ? 2 : 4);
      }
      setStatus(`Workspace switched to ${symbol}. Ticket price and chart context updated.`);
    });
  });

  workspace.querySelectorAll("[data-order-side]").forEach((button) => {
    button.addEventListener("click", () => {
      workspace.querySelectorAll("[data-order-side]").forEach((sideButton) => {
        const isActive = sideButton === button;
        sideButton.classList.toggle("active", isActive);
        sideButton.setAttribute("aria-pressed", String(isActive));
      });
      setStatus(button.dataset.orderSide === "sell"
        ? "Sell/Short selected. Destructive close actions still require confirmation."
        : "Buy/Long selected. Preview updates before any order submission.");
    });
  });

  workspace.querySelectorAll("[data-book-price]").forEach((row) => {
    row.addEventListener("click", () => {
      if (ticketPrice) {
        ticketPrice.value = Number(row.dataset.bookPrice || 0).toFixed(2);
        ticketPrice.focus({ preventScroll: true });
      }
      setStatus(`Order book price ${row.dataset.bookPrice} copied into the order ticket.`);
    });
  });

  workspace.querySelectorAll("[data-trade-tab]").forEach((button) => {
    button.addEventListener("click", () => {
      const tab = button.dataset.tradeTab;
      workspace.querySelectorAll("[data-trade-tab]").forEach((tabButton) => {
        const isActive = tabButton === button;
        tabButton.classList.toggle("active", isActive);
        tabButton.setAttribute("aria-selected", String(isActive));
      });
      workspace.querySelectorAll("[id^='trade-tab-']").forEach((panel) => {
        panel.classList.toggle("hidden", panel.id !== `trade-tab-${tab}`);
      });
    });
  });

  const search = document.getElementById("trading-symbol-search");
  let searchTimer = null;
  if (search) {
    search.addEventListener("input", () => {
      window.clearTimeout(searchTimer);
      searchTimer = window.setTimeout(() => {
        const query = search.value.trim().toLowerCase();
        workspace.querySelectorAll("[data-trading-symbol]").forEach((row) => {
          const text = row.textContent.toLowerCase();
          row.hidden = Boolean(query) && !text.includes(query);
        });
      }, 160);
    });
  }

  const previewButton = document.getElementById("ticket-preview-button");
  if (previewButton) {
    previewButton.addEventListener("click", () => {
      previewTradingOrder(buildProfessionalOrderRequest());
    });
  }

  document.querySelectorAll("[data-order-preview-close]").forEach((button) => {
    button.addEventListener("click", closeOrderPreviewWindow);
  });

  const submitPreviewButton = document.getElementById("order-preview-submit");
  if (submitPreviewButton) {
    submitPreviewButton.addEventListener("click", submitPreviewedPaperOrder);
  }

  const closeAllButton = document.getElementById("ticket-close-all-button");
  if (closeAllButton) {
    closeAllButton.addEventListener("click", () => {
      const confirmed = window.confirm("Esti pe cale sa inchizi toate pozitiile deschise. Actiunea necesita confirmare suplimentara in live trading.");
      setStatus(confirmed
        ? "Close-all confirmed in UI demo. Live execution remains disabled until legal, KYC and broker gates are active."
        : "Close-all cancelled. Positions remain unchanged.");
    });
  }

  workspace.querySelectorAll("[data-partial-close]").forEach((button) => {
    button.addEventListener("click", () => {
      const symbol = button.dataset.partialClose;
      const confirmed = window.confirm(`Inchidere partiala pentru ${symbol}. Confirma cantitatea in pasul urmator in live trading.`);
      setStatus(confirmed
        ? `Partial close modal accepted for ${symbol}. Demo does not submit live orders.`
        : `Partial close cancelled for ${symbol}.`);
    });
  });

  workspace.querySelectorAll("[data-simple-order]").forEach((button) => {
    button.addEventListener("click", () => {
      const side = button.dataset.simpleOrder === "sell" ? "sell" : "buy";
      if (confirmation) {
        confirmation.innerHTML = `<strong>${side.toUpperCase()} preview requested</strong><span>Step 2 opens in a compact risk window. Nothing is sent without explicit confirmation.</span>`;
      }
      previewTradingOrder(buildSimpleOrderRequest(side));
    });
  });
}

function bindInteractions() {
  document.querySelectorAll("[data-action='dashboard-window-close']").forEach((button) => {
    const closeWindow = (event) => {
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation?.();
      closeDashboardWindow();
    };
    button.addEventListener("pointerdown", closeWindow);
    button.addEventListener("click", closeWindow);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && selectedSocialTraderId) {
      closeSocialTraderDetail();
    }
    if (event.key === "Escape" && !document.getElementById("order-preview-window")?.classList.contains("hidden")) {
      closeOrderPreviewWindow();
    }
  });

  document.addEventListener("click", async (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }

    const dashboardWindowClose = target.closest("[data-action='dashboard-window-close']");
    if (dashboardWindowClose) {
      event.preventDefault();
      closeDashboardWindow();
      return;
    }

    const dashboardSectionLink = target.closest("a[href^='#']");
    if (
      dashboardSectionLink
      && document.body.classList.contains("dashboard-body")
      && !event.metaKey
      && !event.ctrlKey
      && !event.shiftKey
      && !event.altKey
    ) {
      if (Date.now() < suppressDashboardWindowOpenUntil) {
        event.preventDefault();
        return;
      }
      const hash = dashboardSectionLink.getAttribute("href");
      if (openDashboardWindow(hash, dashboardSectionLink)) {
        event.preventDefault();
        return;
      }
    }

    if (target.id === "run-cycle-button") {
      event.preventDefault();
      await runCycle();
      return;
    }

    if (target.id === "retry-notifications-button") {
      event.preventDefault();
      await retryNotifications();
      return;
    }

    if (target.id === "simulate-paper-trading-button") {
      event.preventDefault();
      await simulatePaperTrading();
      return;
    }

    if (target.id === "social-discovery-button") {
      event.preventDefault();
      await runSocialDiscovery(target);
      return;
    }

    if (target.id === "social-diversify-button") {
      event.preventDefault();
      if (!requireEditable()) {
        return;
      }
      await diversifySocialPortfolio(target);
      return;
    }

    if (target.id === "social-execute-button") {
      event.preventDefault();
      if (!requireEditable()) {
        return;
      }
      await executeSocialManagedPaper(target);
      return;
    }

    if (target.id === "generate-advanced-export-button") {
      event.preventDefault();
      await generateAdvancedExport();
      return;
    }

    if (target.id === "mark-all-alerts-button") {
      event.preventDefault();
      if (!requireEditable()) {
        return;
      }
      await markAllAlertsRead();
      return;
    }

    if (target.id === "auto-refresh-button") {
      event.preventDefault();
      autoRefreshEnabled = !autoRefreshEnabled;
      startAutoRefresh();
      setStatus(autoRefreshEnabled ? "Auto-refresh resumed." : "Auto-refresh paused. Manual refresh remains available.");
      return;
    }

    if (target.id === "run-all-connector-checks-button") {
      event.preventDefault();
      await runAllConnectorDiagnostics(target);
      return;
    }

    const actionTarget = target.closest("[data-action]");
    const action = actionTarget instanceof HTMLElement ? actionTarget.dataset.action : undefined;
    try {
      if (action === "run-connector-check") {
        event.preventDefault();
        await runConnectorDiagnostic(actionTarget.dataset.connectorId, actionTarget);
        return;
      }
      if (action === "select-landing-asset") {
        selectedLandingAsset = actionTarget.dataset.value;
        if (latestLandingSnapshot?.assets?.length) {
          await renderLandingMarketChart(latestLandingSnapshot.assets);
        } else {
          const landing = await fetchJson("/api/landing");
          renderLanding(landing);
        }
        return;
      }
      if (action === "select-dashboard-asset") {
        selectedDashboardAsset = actionTarget.dataset.value;
        if (latestSnapshot?.assets?.length) {
          await renderDashboardMarketChart(latestSnapshot.assets);
        }
        return;
      }
      if (action === "select-macro-series") {
        selectedMacroSeries = actionTarget.dataset.value;
        if (latestSnapshot?.macro_snapshot) {
          renderMacroChart(latestSnapshot.macro_snapshot);
        }
        return;
      }
      if (action === "follow") {
        if (!requireEditable()) {
          return;
        }
        await followBot(actionTarget.dataset.botSlug);
        return;
      }
      if (action === "social-open-detail") {
        event.preventDefault();
        openSocialTraderDetail(actionTarget.dataset.socialTraderId);
        return;
      }
      if (action === "social-close-detail") {
        event.preventDefault();
        closeSocialTraderDetail();
        return;
      }
      if (action === "social-follow-signal" || action === "social-follow-managed") {
        if (!requireEditable()) {
          return;
        }
        await configureSocialTrader(
          actionTarget.dataset.socialTraderId,
          action === "social-follow-managed" ? "managed_paper" : "signals",
        );
        return;
      }
      if (action === "trader-intelligence-open-add") {
        event.preventDefault();
        openTraderIntelligenceAddModal();
        return;
      }
      if (action === "trader-intelligence-close-add") {
        event.preventDefault();
        closeTraderIntelligenceAddModal();
        return;
      }
      if (action === "trader-intelligence-open-source") {
        event.preventDefault();
        openTraderIntelligenceSourceDrawer(actionTarget.dataset.sourceId);
        return;
      }
      if (action === "trader-intelligence-close-source") {
        event.preventDefault();
        closeTraderIntelligenceSourceDrawer();
        return;
      }
      if (action === "trader-intelligence-main-tab") {
        event.preventDefault();
        traderIntelligenceState.activeTab = actionTarget.dataset.tiTab || "library";
        renderTraderIntelligence(traderIntelligenceState.workspace);
        return;
      }
      if (action === "trader-intelligence-profile-tab") {
        event.preventDefault();
        traderIntelligenceState.profileTab = actionTarget.dataset.tiProfileTab || "overview";
        renderTraderIntelligence(traderIntelligenceState.workspace);
        return;
      }
      if (action === "trader-intelligence-select") {
        event.preventDefault();
        traderIntelligenceState.selectedProfileId = Number(actionTarget.dataset.profileId);
        traderIntelligenceState.activeTab = "profile";
        renderTraderIntelligence(traderIntelligenceState.workspace);
        setStatus("Expert model selected.");
        return;
      }
      if (action === "trader-intelligence-toggle-compare") {
        const profileId = Number(actionTarget.dataset.profileId);
        if (actionTarget.checked) {
          traderIntelligenceState.selectedCompareIds.add(profileId);
        } else {
          traderIntelligenceState.selectedCompareIds.delete(profileId);
        }
        renderTraderIntelligence(traderIntelligenceState.workspace);
        return;
      }
      if (action === "trader-intelligence-rerun") {
        event.preventDefault();
        await rerunTraderIntelligence(actionTarget.dataset.profileId);
        return;
      }
      if (action === "trader-intelligence-delete") {
        event.preventDefault();
        await deleteTraderIntelligenceProfile(actionTarget.dataset.profileId);
        return;
      }
      if (action === "unfollow") {
        if (!requireEditable()) {
          return;
        }
        await unfollowBot(actionTarget.dataset.botSlug);
        return;
      }
      if (action === "add-watch") {
        if (!requireEditable()) {
          return;
        }
        await addWatchlist(actionTarget.dataset.asset);
        return;
      }
      if (action === "remove-watch") {
        if (!requireEditable()) {
          return;
        }
        await removeWatchlist(actionTarget.dataset.asset);
        return;
      }
      if (action === "add-alert-rule") {
        if (!requireEditable()) {
          return;
        }
        await addAlertRule(actionTarget.dataset.asset, actionTarget.dataset.confidence || 0.68);
        return;
      }
      if (action === "delete-alert-rule") {
        if (!requireEditable()) {
          return;
        }
        await deleteAlertRule(actionTarget.dataset.ruleId);
        return;
      }
      if (action === "mark-alert-read") {
        if (!requireEditable()) {
          return;
        }
        await markAlertRead(actionTarget.dataset.alertId);
        return;
      }
      if (action === "delete-channel") {
        if (!requireEditable()) {
          return;
        }
        await deleteNotificationChannel(actionTarget.dataset.channelId);
        return;
      }
      if (action === "delete-wallet") {
        if (!requireEditable()) {
          return;
        }
        await disconnectWallet(actionTarget.dataset.walletId);
        return;
      }
      if (action === "logout") {
        await logoutUser();
        return;
      }
      if (action === "start-checkout") {
        if (!requireEditable()) {
          return;
        }
        await startBillingCheckout(actionTarget.dataset.planKey || "basic");
        return;
      }
      if (action === "open-billing-portal") {
        if (!requireEditable()) {
          return;
        }
        await openBillingPortal();
        return;
      }
    } catch (error) {
      setStatus(error.message);
      return;
    }

    const botSlug = target.dataset.botSlug || target.closest("[data-bot-slug]")?.dataset.botSlug;
    if (botSlug) {
      event.preventDefault();
      await renderBotDetail(botSlug);
    }
  });
}

async function boot() {
  loadPreferences();
  applyPreferences();
  bindInteractions();
  bindForms();
  bindPreferenceControls();
  initProfessionalTradingWorkspace();
  initDashboardSectionObserver();
  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && document.body.classList.contains("dashboard-window-open")) {
      closeDashboardWindow();
    }
  });
  window.addEventListener("hashchange", handleDashboardHashChange);
  window.addEventListener("beforeunload", clearRefreshTimers);
  window.addEventListener("resize", () => {
    if (chartResizeFrame) {
      window.cancelAnimationFrame(chartResizeFrame);
    }
    chartResizeFrame = window.requestAnimationFrame(() => {
      chartResizeFrame = null;
      resizeVisibleCharts();
    });
  });
  try {
    if (document.getElementById("summary-stats")) {
      const landing = await fetchJson("/api/landing");
      renderLanding(landing);
    }

    if (document.getElementById("dashboard-metrics")) {
      const openedDashboardWorkspace = openDashboardWindowFromHash();
      await loadDashboard();
      if (!openedDashboardWorkspace) {
        openDashboardWindowFromHash();
      }
    }

    if (document.getElementById("simulation-form")) {
      await loadSimulationPage();
    }

    if (document.getElementById("status-page")) {
      await loadStatusPage();
      statusPageTimer = window.setInterval(() => {
        loadStatusPage().catch((error) => console.error(error));
      }, AUTO_REFRESH_MS);
    }
  } catch (error) {
    console.error(error);
    setStatus(`Unable to load dashboard data right now: ${error.message}`);
  }
}

boot();
