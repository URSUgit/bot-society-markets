import {
  APP_JS,
  HYPERLIQUID_TOKENS_CSS,
  INDEX_HTML,
  LIGHTWEIGHT_CHARTS_JS,
  PLATFORM_CSS,
  PLATFORM_HTML,
  PLATFORM_JS,
  PRIVACY_HTML,
  RISK_HTML,
  SIMULATION_HTML,
  STATUS_HTML,
  STYLES_CSS,
  TERMS_HTML,
} from "./public-assets.js";
import { CONNECTOR_DIAGNOSTICS, DASHBOARD_SNAPSHOT, LANDING_SNAPSHOT, SYSTEM_PULSE } from "./public-snapshots.js";

const RESERVED_ROOT_REWRITES = {
  "bitprivat.com": "/landing",
  "www.bitprivat.com": "/landing",
  "app.bitprivat.com": "/dashboard",
  "api.bitprivat.com": "/health",
  "status.bitprivat.com": "/status",
};
const APP_DASHBOARD_PATHS = new Set([
  "/dashboard",
  "/dashboard/",
  "/home",
  "/home/",
  "/app",
  "/markets",
  "/markets/",
  "/data",
  "/data/",
  "/ideas",
  "/ideas/",
  "/strategies",
  "/strategies/",
  "/results",
  "/results/",
  "/trade",
  "/trade/",
  "/paper",
  "/paper/",
  "/signals",
  "/signals/",
  "/social-traders",
  "/social-traders/",
  "/portfolio",
  "/portfolio/",
  "/connections",
  "/connections/",
  "/learn",
  "/learn/",
  "/settings",
  "/settings/",
]);

function normalizeOrigin(originBaseUrl) {
  const origin = new URL(originBaseUrl);
  origin.pathname = "/";
  origin.search = "";
  origin.hash = "";
  return origin;
}

function rewritePath(hostname, pathname) {
  const normalizedPath = pathname || "/";
  if (normalizedPath !== "/" && normalizedPath !== "") {
    return normalizedPath;
  }
  return RESERVED_ROOT_REWRITES[hostname] || "/";
}

function cacheControl(hostname, pathname, contentType) {
  const type = (contentType || "").toLowerCase();
  if (
    hostname === "api.bitprivat.com"
    || pathname.startsWith("/api/")
    || pathname === "/health"
    || pathname === "/status"
    || type.includes("text/html")
    || type.includes("application/json")
  ) {
    return "no-store";
  }
  return "public, max-age=120";
}

function headerSafe(value) {
  return String(value ?? "")
    .replace(/[\r\n]/g, " ")
    .slice(0, 180);
}

function jsonResponse(payload, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
      "X-Robots-Tag": "noindex, nofollow",
      ...extraHeaders,
    },
  });
}

function assetResponse(body, contentType) {
  return new Response(body, {
    headers: {
      "Content-Type": contentType,
      "Cache-Control": contentType.includes("html") ? "no-store" : "public, max-age=120",
    },
  });
}

function appAssetFallback(pathname) {
  if (APP_DASHBOARD_PATHS.has(pathname)) {
    return assetResponse(PLATFORM_HTML, "text/html; charset=utf-8");
  }
  if (pathname === "/legacy-dashboard" || pathname === "/legacy-dashboard/") {
    return assetResponse(PLATFORM_HTML, "text/html; charset=utf-8");
  }
  if (pathname === "/simulation" || pathname === "/simulation/" || pathname === "/lab") {
    return assetResponse(SIMULATION_HTML, "text/html; charset=utf-8");
  }
  if (pathname === "/static/styles.css") {
    return assetResponse(STYLES_CSS, "text/css; charset=utf-8");
  }
  if (pathname === "/static/hyperliquid-tokens.css") {
    return assetResponse(HYPERLIQUID_TOKENS_CSS, "text/css; charset=utf-8");
  }
  if (pathname === "/static/app.js") {
    return assetResponse(APP_JS, "application/javascript; charset=utf-8");
  }
  if (pathname === "/static/platform.css") {
    return assetResponse(PLATFORM_CSS, "text/css; charset=utf-8");
  }
  if (pathname === "/static/platform.js") {
    return assetResponse(PLATFORM_JS, "application/javascript; charset=utf-8");
  }
  if (pathname === "/static/vendor/lightweight-charts.standalone.production.js") {
    return assetResponse(LIGHTWEIGHT_CHARTS_JS, "application/javascript; charset=utf-8");
  }
  return null;
}

function publicSnapshotResponse(payload) {
  return jsonResponse({
    ...payload,
    edge_generated_at: new Date().toISOString(),
    edge_source: "cloudflare-public-snapshot",
  });
}

function connectorDiagnosticFromSnapshot(connectorId) {
  const diagnostics = CONNECTOR_DIAGNOSTICS?.connector_diagnostics || [];
  return diagnostics.find((item) => item.connector_id === connectorId) || null;
}

function publicApiSnapshot(pathname) {
  if (pathname === "/api/landing" || pathname === "/api/v1/landing/stats") {
    return publicSnapshotResponse(LANDING_SNAPSHOT);
  }
  if (pathname === "/api/dashboard" || pathname === "/api/v1/dashboard/summary") {
    return publicSnapshotResponse(DASHBOARD_SNAPSHOT);
  }
  if (pathname === "/api/social-trading" || pathname === "/api/v1/social-trading") {
    return publicSnapshotResponse({ social_trading: DASHBOARD_SNAPSHOT.social_trading });
  }
  if (pathname === "/api/social-traders" || pathname === "/api/v1/social-traders") {
    return jsonResponse(DASHBOARD_SNAPSHOT.social_trading?.top_traders || []);
  }
  if (pathname === "/api/system/pulse" || pathname === "/api/v1/system/pulse") {
    return publicSnapshotResponse(SYSTEM_PULSE);
  }
  if (pathname === "/api/system/providers" || pathname === "/api/v1/system/providers") {
    return publicSnapshotResponse({ provider_status: DASHBOARD_SNAPSHOT.provider_status });
  }
  if (pathname === "/api/system/operations-infrastructure" || pathname === "/api/v1/system/operations-infrastructure") {
    return publicSnapshotResponse({ operations_infrastructure: DASHBOARD_SNAPSHOT.operations_infrastructure });
  }
  if (pathname === "/api/system/feature-readiness" || pathname === "/api/v1/system/feature-readiness") {
    return publicSnapshotResponse({ feature_readiness: DASHBOARD_SNAPSHOT.feature_readiness });
  }
  if (pathname === "/api/assets" || pathname === "/api/v1/assets") {
    return jsonResponse(DASHBOARD_SNAPSHOT.assets);
  }
  if (pathname === "/api/paper-venues" || pathname === "/api/v1/paper-venues" || pathname === "/api/v1/trading/venues") {
    return publicSnapshotResponse({ paper_venues: DASHBOARD_SNAPSHOT.paper_venues, ...DASHBOARD_SNAPSHOT.paper_venues });
  }
  if (pathname === "/api/system/connectors" || pathname === "/api/v1/system/connectors") {
    return publicSnapshotResponse({ connector_control: DASHBOARD_SNAPSHOT.connector_control });
  }
  if (pathname === "/api/system/connectors/diagnostics" || pathname === "/api/v1/system/connectors/diagnostics") {
    return publicSnapshotResponse(CONNECTOR_DIAGNOSTICS);
  }
  const connectorDiagnosticMatch = pathname.match(/^\/api(?:\/v1)?\/system\/connectors\/([^/]+)\/diagnostics$/);
  if (!connectorDiagnosticMatch) {
    return null;
  }
  const connectorDiagnostic = connectorDiagnosticFromSnapshot(decodeURIComponent(connectorDiagnosticMatch[1]));
  return connectorDiagnostic
    ? publicSnapshotResponse({ connector_diagnostic: connectorDiagnostic })
    : jsonResponse({ detail: "Connector not found" }, 404);
}

function withDeliveryMode(response, mode, metadata = {}) {
  const deliveredResponse = new Response(response.body, response);
  deliveredResponse.headers.set("Cache-Control", "no-store");
  deliveredResponse.headers.set("X-BITprivat-Data-Mode", mode);
  if (metadata.reason) {
    deliveredResponse.headers.set("X-BITprivat-Fallback-Reason", headerSafe(metadata.reason));
  }
  if (metadata.originStatus) {
    deliveredResponse.headers.set("X-BITprivat-Origin-Status", headerSafe(metadata.originStatus));
  }
  if (metadata.originError) {
    deliveredResponse.headers.set("X-BITprivat-Origin-Error", headerSafe(metadata.originError));
  }
  if (mode === "edge-fallback" || mode === "edge-snapshot") {
    deliveredResponse.headers.set("Warning", '199 bitprivat "Serving labeled standby data; verify origin before trading-critical use."');
  }
  return deliveredResponse;
}

function isAnonymousPublicRead(request, fallbackResponse) {
  return Boolean(fallbackResponse)
    && request.method === "GET"
    && !request.headers.has("Authorization")
    && !request.headers.has("Cookie");
}

function requestRequiresLiveOrigin(request, incomingUrl) {
  return incomingUrl.searchParams.get("edge_require_live") === "1"
    || request.headers.get("X-BITprivat-Require-Live-Origin") === "1";
}

function buildOriginHeaders(request, incomingUrl, origin, env) {
  const headers = new Headers(request.headers);
  // Akash ingress validates the Host header against the SDL accept list.
  // Pin Cloudflare to the exact Akash lease instead of any shared app host.
  headers.set("Host", env.ORIGIN_RESOLVE_OVERRIDE || origin.hostname);
  headers.set("x-forwarded-host", incomingUrl.host);
  headers.set("x-forwarded-proto", incomingUrl.protocol.replace(":", "") || "https");
  return headers;
}

function originUnavailableResponse(origin, incomingUrl, reason, status = 503) {
  return jsonResponse(
    {
      detail: "Live origin was required but the Cloudflare edge could not return a live origin response.",
      origin: origin.origin,
      path: incomingUrl.pathname,
      reason: headerSafe(reason),
      generated_at: new Date().toISOString(),
    },
    status,
    {
      "X-BITprivat-Data-Mode": "origin-unavailable",
      "X-BITprivat-Fallback-Reason": headerSafe(reason),
    },
  );
}

async function fetchWithinDeadline(request, timeoutMilliseconds) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMilliseconds);
  try {
    return await fetch(new Request(request, { signal: controller.signal }));
  } finally {
    clearTimeout(timer);
  }
}

async function originHealthResponse(request, env, incomingUrl, origin) {
  const startedAt = Date.now();
  const upstreamUrl = new URL("/api/v1/system/pulse?edge_health=1", origin);
  const upstreamRequest = new Request(upstreamUrl, {
    method: "GET",
    headers: buildOriginHeaders(request, incomingUrl, origin, env),
    redirect: "manual",
  });
  try {
    const upstreamResponse = await fetchWithinDeadline(upstreamRequest, 20000);
    return jsonResponse(
      {
        status: upstreamResponse.ok ? "ok" : "degraded",
        service: "bitprivat-edge-router",
        origin: origin.origin,
        origin_reachable: upstreamResponse.ok,
        origin_status: upstreamResponse.status,
        elapsed_ms: Date.now() - startedAt,
        generated_at: new Date().toISOString(),
      },
      upstreamResponse.ok ? 200 : 502,
      {
        "X-BITprivat-Data-Mode": upstreamResponse.ok ? "live-origin-probe" : "origin-probe-failed",
        "X-BITprivat-Origin-Status": String(upstreamResponse.status),
      },
    );
  } catch (error) {
    return jsonResponse(
      {
        status: "degraded",
        service: "bitprivat-edge-router",
        origin: origin.origin,
        origin_reachable: false,
        origin_error: headerSafe(error?.message || error?.name || "origin fetch failed"),
        elapsed_ms: Date.now() - startedAt,
        generated_at: new Date().toISOString(),
      },
      503,
      {
        "X-BITprivat-Data-Mode": "origin-probe-failed",
        "X-BITprivat-Origin-Error": headerSafe(error?.message || error?.name || "origin fetch failed"),
      },
    );
  }
}

function statusPage(originBaseUrl) {
  const escapedOrigin = String(originBaseUrl || "app.bitprivat.com").replace(/[<>&"]/g, "");
  return new Response(
    `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>BITprivat Status</title>
  <style>
    body{margin:0;font-family:ui-sans-serif,system-ui;background:#f5f1e8;color:#17130d}
    main{max-width:760px;margin:0 auto;padding:72px 24px}
    .card{border:1px solid #d8cab2;border-radius:28px;background:#fffaf0;padding:32px;box-shadow:0 24px 80px rgba(56,42,21,.12)}
    .pill{display:inline-flex;gap:8px;align-items:center;border:1px solid #a8d5a2;background:#effbea;color:#234c22;border-radius:999px;padding:8px 12px;font-weight:700}
    h1{font-size:clamp(36px,6vw,68px);line-height:.92;margin:22px 0 14px;letter-spacing:-.06em}
    p{font-size:18px;line-height:1.65;color:#544936}
    code{background:#eee2ce;border-radius:10px;padding:3px 7px}
  </style>
</head>
<body>
  <main>
    <section class="card">
      <span class="pill">Operational</span>
      <h1>BITprivat edge is online.</h1>
      <p>The Cloudflare router is serving traffic and forwarding application requests to <code>${escapedOrigin}</code>.</p>
      <p>Dashboard: <a href="https://bitprivat.com/dashboard">bitprivat.com/dashboard</a></p>
    </section>
  </main>
</body>
</html>`,
    {
      headers: {
        "Content-Type": "text/html; charset=utf-8",
        "Cache-Control": "no-store",
      },
    },
  );
}

export default {
  async fetch(request, env, ctx) {
    const incomingUrl = new URL(request.url);
    const configuredOrigin = normalizeOrigin(env.ORIGIN_BASE_URL || "https://app.bitprivat.com");
    const originBaseUrl = env.ORIGIN_RESOLVE_OVERRIDE
      ? `${configuredOrigin.protocol}//${env.ORIGIN_RESOLVE_OVERRIDE}`
      : configuredOrigin.href;
    const origin = normalizeOrigin(originBaseUrl);
    const requireLiveOrigin = requestRequiresLiveOrigin(request, incomingUrl);
    if (incomingUrl.hostname === "api.bitprivat.com" && (incomingUrl.pathname === "/" || incomingUrl.pathname === "/health")) {
      return jsonResponse({
        status: "ok",
        service: "bitprivat-edge-router",
        origin: origin.origin,
        generated_at: new Date().toISOString(),
      });
    }
    if (request.method === "GET" && incomingUrl.pathname === "/api/runtime/edge-health") {
      return originHealthResponse(request, env, incomingUrl, origin);
    }
    if (request.method === "GET" && incomingUrl.pathname === "/api/runtime/public-origin") {
      return jsonResponse({
        social_read_origin: origin.origin,
        strict_live_query: "edge_require_live=1",
        edge_health_path: "/api/runtime/edge-health",
        generated_at: new Date().toISOString(),
      });
    }
    if (incomingUrl.hostname === "status.bitprivat.com" && (incomingUrl.pathname === "/" || incomingUrl.pathname === "/status")) {
      return assetResponse(STATUS_HTML, "text/html; charset=utf-8");
    }
    if (incomingUrl.pathname === "/legacy-dashboard" || incomingUrl.pathname === "/legacy-dashboard/") {
      return assetResponse(PLATFORM_HTML, "text/html; charset=utf-8");
    }
    if (
      (incomingUrl.hostname === "bitprivat.com" || incomingUrl.hostname === "www.bitprivat.com")
      && (incomingUrl.pathname === "/" || incomingUrl.pathname === "/landing")
    ) {
      return assetResponse(INDEX_HTML, "text/html; charset=utf-8");
    }
    if (incomingUrl.pathname === "/terms" || incomingUrl.pathname === "/terms-of-service" || incomingUrl.pathname === "/legal/terms") {
      return assetResponse(TERMS_HTML, "text/html; charset=utf-8");
    }
    if (incomingUrl.pathname === "/privacy" || incomingUrl.pathname === "/privacy-policy" || incomingUrl.pathname === "/legal/privacy") {
      return assetResponse(PRIVACY_HTML, "text/html; charset=utf-8");
    }
    if (incomingUrl.pathname === "/risk" || incomingUrl.pathname === "/risk-disclosure" || incomingUrl.pathname === "/legal/risk") {
      return assetResponse(RISK_HTML, "text/html; charset=utf-8");
    }
    if (incomingUrl.pathname === "/status" || incomingUrl.pathname === "/status/" || incomingUrl.pathname === "/ops") {
      return assetResponse(STATUS_HTML, "text/html; charset=utf-8");
    }
    const allowPublicSnapshots = env.BSM_ALLOW_EDGE_PUBLIC_SNAPSHOTS === "true";
    const publicFallback = allowPublicSnapshots ? publicApiSnapshot(incomingUrl.pathname) : null;
    if (!env.ORIGIN_RESOLVE_OVERRIDE && publicFallback && !requireLiveOrigin) {
      return withDeliveryMode(publicFallback, "edge-snapshot", { reason: "origin override not configured" });
    }
    const canCachePublicRead = isAnonymousPublicRead(request, publicFallback);
    const bypassPublicCache = incomingUrl.searchParams.get("fresh") === "1";
    const isSocialRead = incomingUrl.pathname.includes("/social-trad");
    const originDeadlineMilliseconds = requireLiveOrigin
      ? (isSocialRead ? 25000 : 20000)
      : (isSocialRead ? 9000 : 4500);
    const publicCacheSeconds = isSocialRead ? 60 : 20;
    const cacheUrl = new URL(request.url);
    cacheUrl.search = "";
    const cacheKey = new Request(cacheUrl.toString(), { method: "GET" });
    if (canCachePublicRead && !bypassPublicCache) {
      const cachedResponse = await caches.default.match(cacheKey);
      if (cachedResponse) {
        return withDeliveryMode(cachedResponse, "edge-live-cache");
      }
    }

    const upstreamPath = rewritePath(incomingUrl.hostname, incomingUrl.pathname);
    const assetFallback = appAssetFallback(upstreamPath);
    const upstreamUrl = new URL(upstreamPath + incomingUrl.search, origin);

    const headers = buildOriginHeaders(request, incomingUrl, origin, env);

    const upstreamMethod = request.method === "HEAD" ? "GET" : request.method;
    const upstreamRequest = new Request(upstreamUrl, {
      method: upstreamMethod,
      headers,
      body: upstreamMethod === "GET" ? undefined : request.body,
      redirect: "manual",
    });
    let upstreamResponse;
    try {
      // Anonymous dashboard reads degrade gracefully instead of waiting for
      // an intermittent Akash ingress timeout. Writes and personal reads do not.
      upstreamResponse = canCachePublicRead
        ? await fetchWithinDeadline(upstreamRequest, originDeadlineMilliseconds)
        : await fetch(upstreamRequest);
    } catch (error) {
      if (requireLiveOrigin) {
        return originUnavailableResponse(origin, incomingUrl, error?.message || error?.name || "origin fetch failed");
      }
      if (canCachePublicRead && publicFallback) {
        return withDeliveryMode(publicFallback, "edge-fallback", {
          reason: "origin fetch failed before deadline",
          originError: error?.message || error?.name || "origin fetch failed",
        });
      }
      if (assetFallback) {
        return withDeliveryMode(assetFallback, "edge-asset-fallback", {
          reason: "origin fetch failed",
          originError: error?.message || error?.name || "origin fetch failed",
        });
      }
      throw error;
    }
    if (canCachePublicRead && publicFallback && upstreamResponse.status >= 500 && !requireLiveOrigin) {
      return withDeliveryMode(publicFallback, "edge-fallback", {
        reason: "origin returned server error",
        originStatus: upstreamResponse.status,
      });
    }
    if (assetFallback && upstreamResponse.status >= 500 && !requireLiveOrigin) {
      return withDeliveryMode(assetFallback, "edge-asset-fallback", {
        reason: "origin returned server error",
        originStatus: upstreamResponse.status,
      });
    }

    const response = new Response(request.method === "HEAD" ? null : upstreamResponse.body, {
      status: upstreamResponse.status,
      statusText: upstreamResponse.statusText,
      headers: upstreamResponse.headers,
    });
    response.headers.set(
      "Cache-Control",
      cacheControl(incomingUrl.hostname, upstreamPath, upstreamResponse.headers.get("content-type")),
    );
    if (incomingUrl.hostname === "api.bitprivat.com") {
      response.headers.set("X-Robots-Tag", "noindex, nofollow");
    }
    if (assetFallback && response.ok) {
      response.headers.set("X-BITprivat-Data-Mode", "live-origin");
    }
    if (canCachePublicRead && response.ok) {
      response.headers.set("X-BITprivat-Data-Mode", "live-origin");
      const cachedResponse = response.clone();
      cachedResponse.headers.set("Cache-Control", `public, max-age=${publicCacheSeconds}`);
      ctx.waitUntil(caches.default.put(cacheKey, cachedResponse));
    }
    return response;
  },
};
