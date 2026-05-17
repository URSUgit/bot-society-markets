import {
  APP_JS,
  DASHBOARD_HTML,
  INDEX_HTML,
  LIGHTWEIGHT_CHARTS_JS,
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
  "api.bitprivat.com": "/health",
  "status.bitprivat.com": "/status",
};

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

function jsonResponse(payload, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
      "X-Robots-Tag": "noindex, nofollow",
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
  async fetch(request, env) {
    const incomingUrl = new URL(request.url);
    const originBaseUrl = env.ORIGIN_RESOLVE_OVERRIDE
      ? `https://${env.ORIGIN_RESOLVE_OVERRIDE}`
      : (env.ORIGIN_BASE_URL || "https://app.bitprivat.com");
    const origin = normalizeOrigin(originBaseUrl);
    if (incomingUrl.hostname === "api.bitprivat.com" && (incomingUrl.pathname === "/" || incomingUrl.pathname === "/health")) {
      return jsonResponse({
        status: "ok",
        service: "bitprivat-edge-router",
        origin: origin.origin,
        generated_at: new Date().toISOString(),
      });
    }
    if (incomingUrl.hostname === "status.bitprivat.com" && (incomingUrl.pathname === "/" || incomingUrl.pathname === "/status")) {
      return assetResponse(STATUS_HTML, "text/html; charset=utf-8");
    }
    if (
      (incomingUrl.hostname === "bitprivat.com" || incomingUrl.hostname === "www.bitprivat.com")
      && (incomingUrl.pathname === "/" || incomingUrl.pathname === "/landing" || incomingUrl.pathname === "/portfolio")
    ) {
      return assetResponse(INDEX_HTML, "text/html; charset=utf-8");
    }
    if (incomingUrl.pathname === "/dashboard" || incomingUrl.pathname === "/dashboard/" || incomingUrl.pathname === "/app") {
      return assetResponse(DASHBOARD_HTML, "text/html; charset=utf-8");
    }
    if (incomingUrl.pathname === "/simulation" || incomingUrl.pathname === "/simulation/" || incomingUrl.pathname === "/lab") {
      return assetResponse(SIMULATION_HTML, "text/html; charset=utf-8");
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
    if (incomingUrl.pathname === "/static/styles.css") {
      return assetResponse(STYLES_CSS, "text/css; charset=utf-8");
    }
    if (incomingUrl.pathname === "/static/app.js") {
      return assetResponse(APP_JS, "application/javascript; charset=utf-8");
    }
    if (incomingUrl.pathname === "/static/vendor/lightweight-charts.standalone.production.js") {
      return assetResponse(LIGHTWEIGHT_CHARTS_JS, "application/javascript; charset=utf-8");
    }
    if (incomingUrl.pathname === "/api/landing" || incomingUrl.pathname === "/api/v1/landing/stats") {
      return publicSnapshotResponse(LANDING_SNAPSHOT);
    }
    if (incomingUrl.pathname === "/api/dashboard" || incomingUrl.pathname === "/api/v1/dashboard/summary") {
      return publicSnapshotResponse(DASHBOARD_SNAPSHOT);
    }
    if (incomingUrl.pathname === "/api/social-trading" || incomingUrl.pathname === "/api/v1/social-trading") {
      return publicSnapshotResponse({ social_trading: DASHBOARD_SNAPSHOT.social_trading });
    }
    if (incomingUrl.pathname === "/api/social-traders" || incomingUrl.pathname === "/api/v1/social-traders") {
      return jsonResponse(DASHBOARD_SNAPSHOT.social_trading?.top_traders || []);
    }
    if (incomingUrl.pathname === "/api/system/pulse" || incomingUrl.pathname === "/api/v1/system/pulse") {
      return publicSnapshotResponse(SYSTEM_PULSE);
    }
    if (incomingUrl.pathname === "/api/system/providers" || incomingUrl.pathname === "/api/v1/system/providers") {
      return publicSnapshotResponse({ provider_status: DASHBOARD_SNAPSHOT.provider_status });
    }
    if (incomingUrl.pathname === "/api/assets" || incomingUrl.pathname === "/api/v1/assets") {
      return jsonResponse(DASHBOARD_SNAPSHOT.assets);
    }
    if (incomingUrl.pathname === "/api/paper-venues" || incomingUrl.pathname === "/api/v1/paper-venues" || incomingUrl.pathname === "/api/v1/trading/venues") {
      return publicSnapshotResponse({ paper_venues: DASHBOARD_SNAPSHOT.paper_venues, ...DASHBOARD_SNAPSHOT.paper_venues });
    }
    if (incomingUrl.pathname === "/api/system/connectors" || incomingUrl.pathname === "/api/v1/system/connectors") {
      return publicSnapshotResponse({ connector_control: DASHBOARD_SNAPSHOT.connector_control });
    }
    if (incomingUrl.pathname === "/api/system/connectors/diagnostics" || incomingUrl.pathname === "/api/v1/system/connectors/diagnostics") {
      return publicSnapshotResponse(CONNECTOR_DIAGNOSTICS);
    }
    const connectorDiagnosticMatch = incomingUrl.pathname.match(/^\/api(?:\/v1)?\/system\/connectors\/([^/]+)\/diagnostics$/);
    if (connectorDiagnosticMatch) {
      const connectorDiagnostic = connectorDiagnosticFromSnapshot(decodeURIComponent(connectorDiagnosticMatch[1]));
      if (!connectorDiagnostic) {
        return jsonResponse({ detail: "Connector not found" }, 404);
      }
      return publicSnapshotResponse({ connector_diagnostic: connectorDiagnostic });
    }

    const upstreamPath = rewritePath(incomingUrl.hostname, incomingUrl.pathname);
    const upstreamUrl = new URL(upstreamPath + incomingUrl.search, origin);

    const headers = new Headers(request.headers);
    // Akash ingress validates the Host header against the SDL accept list.
    // Without this, Cloudflare fetches the origin using the random ingress host
    // and the provider returns 502 before the app receives the request.
    // Prefer the unique Akash ingress host when resolveOverride is active.
    // Multiple active deployments may accept app.bitprivat.com, so using that
    // Host header can route Cloudflare to an older lease.
    headers.set("Host", env.ORIGIN_RESOLVE_OVERRIDE || origin.hostname);
    headers.set("x-forwarded-host", incomingUrl.host);
    headers.set("x-forwarded-proto", incomingUrl.protocol.replace(":", "") || "https");

    const upstreamMethod = request.method === "HEAD" ? "GET" : request.method;
    const upstreamRequest = new Request(upstreamUrl, {
      method: upstreamMethod,
      headers,
      body: upstreamMethod === "GET" ? undefined : request.body,
      redirect: "manual",
    });
    const upstreamResponse = await fetch(
      upstreamRequest,
      env.ORIGIN_RESOLVE_OVERRIDE ? { cf: { resolveOverride: env.ORIGIN_RESOLVE_OVERRIDE } } : undefined,
    );

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
    return response;
  },
};
