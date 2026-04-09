const fmtPercent = (value, digits = 0) => `${(Number(value) * 100).toFixed(digits)}%`;
const fmtScore = (value) => Number(value).toFixed(1);
const fmtPrice = (value) => Intl.NumberFormat("en-US", { maximumFractionDigits: Number(value) > 1000 ? 0 : 2 }).format(Number(value));
const fmtSignedPercent = (value) => `${Number(value) >= 0 ? "+" : ""}${(Number(value) * 100).toFixed(1)}%`;
const fmtDateTime = (value) => value ? new Date(value).toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short" }) : "n/a";

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

let selectedBotSlug = null;
let latestSnapshot = null;

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

function renderLanding(snapshot) {
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
    providerNote.textContent = `${snapshot.provider_status.environment_name} environment · market provider ${snapshot.provider_status.market_provider_source} · signal provider ${snapshot.provider_status.signal_provider_source}.`;
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
    <p><strong>Completed:</strong> ${fmtDateTime(operation.completed_at || operation.started_at)}</p>
    <p>${operation.message}</p>
  `;
}

function renderProviderStatus(providerStatus) {
  const card = document.getElementById("provider-card");
  if (!card || !providerStatus) {
    return;
  }
  const rssFeeds = providerStatus.rss_feed_urls?.length
    ? providerStatus.rss_feed_urls.map((feed) => `<li>${feed}</li>`).join("")
    : "<li>No RSS feeds configured</li>";
  const redditFeeds = providerStatus.reddit_subreddits?.length
    ? providerStatus.reddit_subreddits.map((subreddit) => `<li>r/${subreddit}</li>`).join("")
    : "<li>No subreddits configured</li>";
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
    <p><strong>Tracked coins:</strong> ${providerStatus.tracked_coin_ids.join(", ")}</p>
    <p><strong>Market fallback:</strong> ${providerStatus.market_fallback_active ? "yes" : "no"}</p>
    <p><strong>Signal fallback:</strong> ${providerStatus.signal_fallback_active ? "yes" : "no"}</p>
    <div class="provider-feed-list">
      <strong>RSS feeds</strong>
      <ul>${rssFeeds}</ul>
    </div>
    <div class="provider-feed-list">
      <strong>Reddit subreddits</strong>
      <ul>${redditFeeds}</ul>
    </div>
  `;
}

function renderLeaderboard(leaderboard, profile) {
  const body = document.getElementById("leaderboard-body");
  const spotlight = document.getElementById("alert-spotlight");
  if (!body) {
    return;
  }
  body.innerHTML = leaderboard.map((bot) => `
    <tr class="clickable-row" data-bot-slug="${bot.slug}">
      <td><button class="text-button" type="button" data-bot-slug="${bot.slug}">${bot.name}${bot.is_followed ? " · Following" : ""}</button></td>
      <td>${fmtScore(bot.score)}</td>
      <td>${fmtPercent(bot.hit_rate)}</td>
      <td>${bot.calibration.toFixed(2)}</td>
      <td>${fmtPercent(bot.provenance_score)}</td>
      <td>${fmtSignedPercent(bot.average_strategy_return)}</td>
      <td>${bot.predictions}</td>
    </tr>
  `).join("");

  if (spotlight) {
    const unreadCount = profile?.unread_alert_count || 0;
    const latestAlert = profile?.recent_alerts?.[0];
    spotlight.innerHTML = `
      <p><strong>Unread alerts:</strong> ${unreadCount}</p>
      <p><strong>Inbox coverage:</strong> ${profile?.recent_alerts?.length || 0} recent events</p>
      ${latestAlert ? `<p><strong>Latest:</strong> ${latestAlert.title}</p><p>${latestAlert.message}</p>` : "<p>No alert deliveries yet.</p>"}
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
        <p class="panel-note">${signal.provider_name}${signal.author_handle ? ` · ${signal.author_handle}` : ""}</p>
        <p class="panel-note">${qualityLabel(signal.source_quality_score)} · trust ${fmtPercent(signal.provider_trust_score)} · freshness ${fmtPercent(signal.freshness_score)}</p>
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
      <div><dt>Focus</dt><dd>${bot.focus}</dd></div>
      <div><dt>Risk style</dt><dd>${bot.risk_style}</dd></div>
      <div><dt>Universe</dt><dd>${bot.asset_universe.join(", ")}</dd></div>
    </dl>
  `;
  renderPredictions(bot.recent_predictions, "bot-detail-predictions");
}

async function loadDashboard() {
  const snapshot = await fetchJson("/api/dashboard");
  latestSnapshot = snapshot;
  renderMetrics(snapshot.summary);
  renderAssets(snapshot.assets);
  renderOperation(snapshot.latest_operation);
  renderProviderStatus(snapshot.provider_status);
  renderLeaderboard(snapshot.leaderboard, snapshot.user_profile);
  renderPredictions(snapshot.recent_predictions);
  renderSignals(snapshot.recent_signals);
  renderAuthPanel(snapshot.auth_session, snapshot.user_profile);
  renderNotificationHealth(snapshot.notification_health);
  renderUserProfile(snapshot.user_profile, snapshot.notification_health, snapshot.auth_session);
  applyWorkspaceMode(snapshot);

  const preferredSlug = selectedBotSlug || snapshot.leaderboard[0]?.slug;
  if (preferredSlug) {
    await renderBotDetail(preferredSlug);
  }
}

async function runCycle() {
  const button = document.getElementById("run-cycle-button");
  setStatus("Running ingestion, orchestration, scoring, and alert delivery cycle...");
  if (button) {
    button.disabled = true;
  }
  try {
    const result = await fetchJson("/api/admin/run-cycle", { method: "POST" });
    await loadDashboard();
    setStatus(`Pipeline cycle completed. ${result.alert_inbox.unread_count} unread alerts currently in inbox.`);
  } catch (error) {
    setStatus(`Pipeline cycle failed: ${error.message}`);
  } finally {
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
    await loadDashboard();
    setStatus(`Retry pass finished. Scanned ${result.scanned_events}, delivered ${result.delivered}, rescheduled ${result.rescheduled}, exhausted ${result.exhausted}.`);
  } catch (error) {
    setStatus(`Retry pass failed: ${error.message}`);
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
  const watchlistForm = document.getElementById("watchlist-form");
  const alertRuleForm = document.getElementById("alert-rule-form");
  const loginForm = document.getElementById("login-form");
  const registerForm = document.getElementById("register-form");
  const notificationChannelForm = document.getElementById("notification-channel-form");

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

    if (target.id === "mark-all-alerts-button") {
      event.preventDefault();
      if (!requireEditable()) {
        return;
      }
      await markAllAlertsRead();
      return;
    }

    const action = target.dataset.action;
    try {
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
    setStatus(`Unable to load dashboard data right now: ${error.message}`);
  }
}

boot();
