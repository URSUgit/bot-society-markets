const fmtPercent = (value, digits = 0) => `${(Number(value) * 100).toFixed(digits)}%`;
const fmtScore = (value) => Number(value).toFixed(1);
const fmtPrice = (value) => Intl.NumberFormat("en-US", { maximumFractionDigits: value > 1000 ? 0 : 2 }).format(Number(value));
const fmtSignedPercent = (value) => `${Number(value) >= 0 ? "+" : ""}${(Number(value) * 100).toFixed(1)}%`;

let selectedBotSlug = null;

async function fetchJson(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) {
    throw new Error(`Failed to load ${path}`);
  }
  return response.json();
}

function renderLanding(snapshot) {
  const stats = document.getElementById("summary-stats");
  const mini = document.getElementById("leaderboard-mini");
  const botGrid = document.getElementById("launch-bots");
  const assets = document.getElementById("asset-grid");
  const signals = document.getElementById("landing-signals");

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
        </div>
        <span>${signal.source} · ${fmtPercent(signal.relevance)}</span>
      </li>
    `).join("");
  }
}

function renderMetrics(summary) {
  const metrics = document.getElementById("dashboard-metrics");
  if (!metrics || !summary) {
    return;
  }
  metrics.innerHTML = `
    <article class="metric-card"><span>Active bots</span><strong>${summary.active_bots}</strong></article>
    <article class="metric-card"><span>Tracked assets</span><strong>${summary.tracked_assets}</strong></article>
    <article class="metric-card"><span>Scored predictions</span><strong>${summary.scored_predictions}</strong></article>
    <article class="metric-card"><span>Pending predictions</span><strong>${summary.pending_predictions}</strong></article>
  `;
}

function renderAssets(assets) {
  const container = document.getElementById("dashboard-assets");
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
      </dl>
    </article>
  `).join("");
}

function renderOperation(operation) {
  const card = document.getElementById("operation-card");
  if (!card) {
    return;
  }
  if (!operation) {
    card.innerHTML = "<p>No pipeline runs recorded yet.</p>";
    return;
  }
  card.innerHTML = `
    <p><strong>Status:</strong> ${operation.status}</p>
    <p><strong>Type:</strong> ${operation.cycle_type}</p>
    <p><strong>Signals ingested:</strong> ${operation.ingested_signals}</p>
    <p><strong>Predictions created:</strong> ${operation.generated_predictions}</p>
    <p><strong>Predictions scored:</strong> ${operation.scored_predictions}</p>
    <p>${operation.message}</p>
  `;
}

function renderLeaderboard(leaderboard) {
  const body = document.getElementById("leaderboard-body");
  const spotlight = document.getElementById("bot-spotlight");
  if (!body) {
    return;
  }
  body.innerHTML = leaderboard.map((bot) => `
    <tr class="clickable-row" data-bot-slug="${bot.slug}">
      <td><button class="text-button" type="button" data-bot-slug="${bot.slug}">${bot.name}</button></td>
      <td>${fmtScore(bot.score)}</td>
      <td>${fmtPercent(bot.hit_rate)}</td>
      <td>${bot.calibration.toFixed(2)}</td>
      <td>${fmtSignedPercent(bot.average_strategy_return)}</td>
      <td>${bot.predictions}</td>
    </tr>
  `).join("");

  if (spotlight && leaderboard.length) {
    const top = leaderboard[0];
    spotlight.innerHTML = `
      <p class="eyebrow">Current leader</p>
      <h4>${top.name}</h4>
      <p>${top.thesis}</p>
      <ul class="checklist compact">
        <li>${top.archetype}</li>
        <li>Focus: ${top.focus}</li>
        <li>Calibration: ${top.calibration.toFixed(2)}</li>
        <li>Pending calls: ${top.pending_predictions}</li>
      </ul>
    `;
  }
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
      </div>
      <span>${signal.source} · ${fmtPercent(signal.relevance)}</span>
    </li>
  `).join("");
}

async function renderBotDetail(slug) {
  const detail = document.getElementById("bot-detail-card");
  if (!detail || !slug) {
    return;
  }
  const bot = await fetchJson(`/api/bots/${slug}`);
  selectedBotSlug = slug;
  detail.innerHTML = `
    <p class="eyebrow">${bot.archetype}</p>
    <h3>${bot.name}</h3>
    <p>${bot.thesis}</p>
    <dl class="detail-stats">
      <div><dt>Composite</dt><dd>${fmtScore(bot.score)}</dd></div>
      <div><dt>Hit rate</dt><dd>${fmtPercent(bot.hit_rate)}</dd></div>
      <div><dt>Calibration</dt><dd>${bot.calibration.toFixed(2)}</dd></div>
      <div><dt>Focus</dt><dd>${bot.focus}</dd></div>
      <div><dt>Risk style</dt><dd>${bot.risk_style}</dd></div>
      <div><dt>Universe</dt><dd>${bot.asset_universe.join(", ")}</dd></div>
    </dl>
  `;
  renderPredictions(bot.recent_predictions, "bot-detail-predictions");
}

async function loadDashboard() {
  const snapshot = await fetchJson("/api/dashboard");
  renderMetrics(snapshot.summary);
  renderAssets(snapshot.assets);
  renderOperation(snapshot.latest_operation);
  renderLeaderboard(snapshot.leaderboard);
  renderPredictions(snapshot.recent_predictions);
  renderSignals(snapshot.recent_signals);

  const preferredSlug = selectedBotSlug || snapshot.leaderboard[0]?.slug;
  if (preferredSlug) {
    await renderBotDetail(preferredSlug);
  }
}

async function runCycle() {
  const status = document.getElementById("cycle-status");
  const button = document.getElementById("run-cycle-button");
  if (status) {
    status.textContent = "Running demo ingestion, orchestration, and scoring cycle...";
  }
  if (button) {
    button.disabled = true;
  }
  try {
    await fetchJson("/api/admin/run-cycle", { method: "POST" });
    await loadDashboard();
    if (status) {
      status.textContent = "Pipeline cycle completed and the dashboard was refreshed.";
    }
  } catch (error) {
    if (status) {
      status.textContent = `Pipeline cycle failed: ${error.message}`;
    }
  } finally {
    if (button) {
      button.disabled = false;
    }
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

    const botSlug = target.dataset.botSlug || target.closest("[data-bot-slug]")?.dataset.botSlug;
    if (botSlug) {
      event.preventDefault();
      await renderBotDetail(botSlug);
    }
  });
}

async function boot() {
  bindInteractions();
  try {
    if (document.getElementById("summary-stats")) {
      const landing = await fetchJson("/api/landing");
      renderLanding(landing);
    }

    if (document.getElementById("dashboard-metrics")) {
      await loadDashboard();
    }
  } catch (error) {
    console.error(error);
    const status = document.getElementById("cycle-status");
    if (status) {
      status.textContent = "Unable to load dashboard data right now.";
    }
  }
}

boot();
