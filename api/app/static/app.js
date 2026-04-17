const fmtPercent = (value, digits = 0) => `${(Number(value) * 100).toFixed(digits)}%`;
const fmtScore = (value) => Number(value).toFixed(1);
const fmtPrice = (value) => Intl.NumberFormat("en-US", { maximumFractionDigits: Number(value) > 1000 ? 0 : 2 }).format(Number(value));
const fmtCompactNumber = (value) => Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(Number(value));
const fmtSignedPercent = (value) => `${Number(value) >= 0 ? "+" : ""}${(Number(value) * 100).toFixed(1)}%`;
const fmtBps = (value) => `${Number(value) >= 0 ? "+" : ""}${Number(value).toFixed(0)} bps`;
const fmtDateTime = (value) => value ? new Date(value).toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short" }) : "n/a";
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

function providerState(providerStatus) {
  const healthy = providerStatus?.market_provider_ready
    && providerStatus?.signal_provider_ready
    && providerStatus?.macro_provider_ready
    && providerStatus?.wallet_provider_ready;
  const fallback = providerStatus?.market_fallback_active
    || providerStatus?.signal_fallback_active
    || providerStatus?.macro_fallback_active
    || providerStatus?.wallet_fallback_active;
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
  const forms = ["watchlist-form", "alert-rule-form", "notification-channel-form"];

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
  const response = await fetch(path, {
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

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

function setStatus(message) {
  const status = document.getElementById("cycle-status");
  if (status) {
    status.textContent = message;
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
    && snapshot.provider_status.wallet_provider_ready;
  const fallbackActive = snapshot.provider_status.market_fallback_active
    || snapshot.provider_status.signal_fallback_active
    || snapshot.provider_status.macro_fallback_active
    || snapshot.provider_status.wallet_fallback_active;
  if (providerValue) {
    providerValue.textContent = fallbackActive ? "Fallback active" : (providersHealthy ? "Primary providers stable" : "Needs attention");
  }
  if (providerSubtitle) {
    providerSubtitle.textContent = `${snapshot.system_pulse?.live_provider_count ?? 0} live-capable · ${snapshot.provider_status.market_provider_source} + ${snapshot.provider_status.signal_provider_source} + ${snapshot.provider_status.macro_provider_source} + ${snapshot.provider_status.wallet_provider_source}`;
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
  await Promise.all([loadSimulationExports(), runSimulation()]);
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
    <p><strong>Tracked coins:</strong> ${providerStatus.tracked_coin_ids.join(", ")}</p>
    <p><strong>Macro series:</strong> ${providerStatus.fred_series_ids.join(", ")}</p>
    <p><strong>Market fallback:</strong> ${providerStatus.market_fallback_active ? "yes" : "no"}</p>
    <p><strong>Signal fallback:</strong> ${providerStatus.signal_fallback_active ? "yes" : "no"}</p>
    <p><strong>Macro fallback:</strong> ${providerStatus.macro_fallback_active ? "yes" : "no"}</p>
    <p><strong>Wallet fallback:</strong> ${providerStatus.wallet_fallback_active ? "yes" : "no"}</p>
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
  if (!body) {
    return;
  }
  const scoreSnapshot = new Map();
  body.innerHTML = leaderboard.map((bot, index) => `
    <tr class="clickable-row ${leaderboardDeltaClass(bot)}" data-bot-slug="${bot.slug}">
      <td>
        <button class="text-button leaderboard-button" type="button" data-bot-slug="${bot.slug}">
          <span class="leaderboard-rank">${index + 1}</span>
          <span>${bot.name}${bot.is_followed ? " · Following" : ""}</span>
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
    <li>
      <div>
        <strong>${prediction.bot_name} · ${prediction.asset} · ${prediction.direction}</strong>
        <p>${prediction.thesis}</p>
        <p class="panel-note">${fmtRelativeTime(prediction.published_at)} · ${fmtPercent(prediction.confidence)} confidence</p>
      </div>
      <span>${prediction.horizon_label} · ${prediction.status}${prediction.score !== null ? ` · ${fmtScore(prediction.score)}` : ""}</span>
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
    badge.textContent = "Signed in";
    note.textContent = `You are working in the ${authSession.user.display_name} workspace.`;
    sessionCard.innerHTML = `
      <dl class="detail-stats compact-detail-stats">
        <div><dt>Name</dt><dd>${authSession.user.display_name}</dd></div>
        <div><dt>Email</dt><dd>${authSession.user.email}</dd></div>
        <div><dt>Tier</dt><dd>${authSession.user.tier}</dd></div>
        <div><dt>Workspace</dt><dd>${profile.slug}</dd></div>
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
    </dl>
  `;
  actions.innerHTML = "";
  loginCard.hidden = false;
  registerCard.hidden = false;
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

  renderNotificationChannels(profile, notificationHealth);
  renderAlertInbox(profile);
}

async function renderBotDetail(slug) {
  const detail = document.getElementById("bot-detail-card");
  if (!detail || !slug) {
    return;
  }
  const bot = await fetchJson(`/api/bots/${slug}`);
  const canEdit = workspaceEditable();
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
  `;
  renderPredictions(bot.recent_predictions, "bot-detail-predictions");
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
    renderHeroMeta(snapshot);
    renderRibbon(snapshot);
    renderMetrics(snapshot.summary);
    renderAssets(snapshot.assets);
    renderMarketTape(snapshot.assets);
    renderDashboardPulse(snapshot);
    renderMacroCards(snapshot.macro_snapshot, "dashboard-macro-grid", null, "dashboard-macro-summary");
    renderMacroChart(snapshot.macro_snapshot);
    renderWalletIntelligence(snapshot.wallet_intelligence);
    renderEdgeSnapshot(snapshot.edge_snapshot);
    renderPaperTrading(snapshot.paper_trading);
    renderPaperVenues(snapshot.paper_venues);
    await renderDashboardMarketChart(snapshot.assets);
    renderActivityFeed(snapshot);
    renderOperation(snapshot.latest_operation);
    renderProviderStatus(snapshot.provider_status);
    renderLeaderboard(snapshot.leaderboard, snapshot.user_profile);
    renderPredictions(snapshot.recent_predictions);
    renderSignals(snapshot.recent_signals);
    renderAuthPanel(snapshot.auth_session, snapshot.user_profile);
    renderNotificationHealth(snapshot.notification_health);
    renderUserProfile(snapshot.user_profile, snapshot.notification_health, snapshot.auth_session);
    applyWorkspaceMode(snapshot);
    updateRefreshCountdown();
    if (document.getElementById("dashboard-metrics")) {
      startAutoRefresh();
    }

    const preferredSlug = selectedBotSlug || snapshot.leaderboard[0]?.slug;
    if (preferredSlug) {
      await renderBotDetail(preferredSlug);
    }
    if (!options.silent) {
      setStatus(`Dashboard synced ${fmtRelativeTime(lastDashboardRefreshAt)}. ${snapshot.summary.pending_predictions} predictions are still waiting for score windows.`);
    }
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
    setStatus(`Pipeline cycle completed. ${result.alert_inbox.unread_count} unread alerts currently in inbox.`);
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

async function loginUser(email, password) {
  await fetchJson("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
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

function bindForms() {
  const simulationForm = document.getElementById("simulation-form");
  const watchlistForm = document.getElementById("watchlist-form");
  const alertRuleForm = document.getElementById("alert-rule-form");
  const loginForm = document.getElementById("login-form");
  const registerForm = document.getElementById("register-form");
  const notificationChannelForm = document.getElementById("notification-channel-form");

  if (simulationForm) {
    simulationForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      await runSimulation();
    });
  }
  const simulationStrategyInput = document.getElementById("simulation-strategy-input");
  if (simulationStrategyInput) {
    simulationStrategyInput.addEventListener("change", syncStrategyCreatorPanel);
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
      if (!email || !password) {
        return;
      }
      try {
        await loginUser(email, password);
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
}

function bindInteractions() {
  document.addEventListener("click", async (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) {
      return;
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

    const action = target.dataset.action;
    try {
      if (action === "select-landing-asset") {
        selectedLandingAsset = target.dataset.value;
        if (latestLandingSnapshot?.assets?.length) {
          await renderLandingMarketChart(latestLandingSnapshot.assets);
        } else {
          const landing = await fetchJson("/api/landing");
          renderLanding(landing);
        }
        return;
      }
      if (action === "select-dashboard-asset") {
        selectedDashboardAsset = target.dataset.value;
        if (latestSnapshot?.assets?.length) {
          await renderDashboardMarketChart(latestSnapshot.assets);
        }
        return;
      }
      if (action === "select-macro-series") {
        selectedMacroSeries = target.dataset.value;
        if (latestSnapshot?.macro_snapshot) {
          renderMacroChart(latestSnapshot.macro_snapshot);
        }
        return;
      }
      if (action === "follow") {
        if (!requireEditable()) {
          return;
        }
        await followBot(target.dataset.botSlug);
        return;
      }
      if (action === "unfollow") {
        if (!requireEditable()) {
          return;
        }
        await unfollowBot(target.dataset.botSlug);
        return;
      }
      if (action === "add-watch") {
        if (!requireEditable()) {
          return;
        }
        await addWatchlist(target.dataset.asset);
        return;
      }
      if (action === "remove-watch") {
        if (!requireEditable()) {
          return;
        }
        await removeWatchlist(target.dataset.asset);
        return;
      }
      if (action === "add-alert-rule") {
        if (!requireEditable()) {
          return;
        }
        await addAlertRule(target.dataset.asset, target.dataset.confidence || 0.68);
        return;
      }
      if (action === "delete-alert-rule") {
        if (!requireEditable()) {
          return;
        }
        await deleteAlertRule(target.dataset.ruleId);
        return;
      }
      if (action === "mark-alert-read") {
        if (!requireEditable()) {
          return;
        }
        await markAlertRead(target.dataset.alertId);
        return;
      }
      if (action === "delete-channel") {
        if (!requireEditable()) {
          return;
        }
        await deleteNotificationChannel(target.dataset.channelId);
        return;
      }
      if (action === "logout") {
        await logoutUser();
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
  bindInteractions();
  bindForms();
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
      await loadDashboard();
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
