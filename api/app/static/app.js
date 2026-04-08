const fmtPercent = (value) => `${Math.round(value * 100)}%`;
const fmtScore = (value) => Number(value).toFixed(1);

async function fetchJson(path) {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`Failed to load ${path}`);
  }
  return response.json();
}

function renderLanding(leaderboard, summary) {
  const mini = document.getElementById("leaderboard-mini");
  const stats = document.getElementById("summary-stats");
  const botGrid = document.getElementById("launch-bots");

  if (mini) {
    mini.innerHTML = leaderboard.slice(0, 4).map((bot) => `
      <div><span>${bot.name}</span><strong>${fmtScore(bot.score)}</strong></div>
    `).join("");
  }

  if (stats && summary) {
    stats.innerHTML = `
      <li><strong>${summary.active_bots}</strong><span>active bots</span></li>
      <li><strong>${summary.scored_predictions.toLocaleString()}</strong><span>scored predictions</span></li>
      <li><strong>${fmtPercent(summary.alert_ctr)}</strong><span>alert click-through</span></li>
    `;
  }

  if (botGrid) {
    const accents = ["accent-copper", "accent-teal", "accent-gold", "accent-ink"];
    botGrid.innerHTML = leaderboard.slice(0, 4).map((bot, index) => `
      <article class="bot-card ${accents[index % accents.length]}">
        <h4>${bot.name}</h4>
        <p>${bot.thesis}</p>
        <span>Focus: ${bot.focus} | Horizon: ${bot.horizon}</span>
      </article>
    `).join("");
  }
}

function renderDashboard(leaderboard, alerts, summary) {
  const metrics = document.getElementById("dashboard-metrics");
  const body = document.getElementById("leaderboard-body");
  const alertList = document.getElementById("alert-list");
  const bots = document.getElementById("dashboard-bots");

  if (metrics && summary) {
    metrics.innerHTML = `
      <article class="metric-card"><span>Active bots</span><strong>${summary.active_bots}</strong></article>
      <article class="metric-card"><span>Scored predictions</span><strong>${summary.scored_predictions.toLocaleString()}</strong></article>
      <article class="metric-card"><span>Median calibration</span><strong>${summary.median_calibration.toFixed(2)}</strong></article>
      <article class="metric-card"><span>Alert CTR</span><strong>${fmtPercent(summary.alert_ctr)}</strong></article>
    `;
  }

  if (body) {
    body.innerHTML = leaderboard.map((bot) => `
      <tr>
        <td>${bot.name}</td>
        <td>${fmtScore(bot.score)}</td>
        <td>${fmtPercent(bot.hit_rate)}</td>
        <td>${bot.calibration.toFixed(2)}</td>
        <td>${bot.focus}</td>
        <td>${bot.predictions}</td>
      </tr>
    `).join("");
  }

  if (alertList) {
    alertList.innerHTML = alerts.map((alert) => `
      <li><strong>${alert.asset}</strong><span>${alert.bot_name} | ${alert.direction} | ${fmtPercent(alert.confidence)}</span></li>
    `).join("");
  }

  if (bots) {
    const accents = ["accent-copper", "accent-teal", "accent-gold", "accent-ink"];
    bots.innerHTML = leaderboard.slice(0, 4).map((bot, index) => `
      <article class="bot-card ${accents[index % accents.length]}">
        <h4>${bot.name}</h4>
        <p>${bot.thesis}</p>
        <span>Focus: ${bot.focus}</span>
      </article>
    `).join("");
  }
}

async function boot() {
  try {
    const [leaderboard, alerts, summary] = await Promise.all([
      fetchJson("/api/leaderboard"),
      fetchJson("/api/alerts"),
      fetchJson("/api/summary"),
    ]);

    renderLanding(leaderboard, summary);
    renderDashboard(leaderboard, alerts, summary);
  } catch (error) {
    console.error(error);
  }
}

boot();
