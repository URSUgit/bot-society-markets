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
    const origin = normalizeOrigin(env.ORIGIN_BASE_URL || "https://app.bitprivat.com");
    if (incomingUrl.hostname === "api.bitprivat.com" && (incomingUrl.pathname === "/" || incomingUrl.pathname === "/health")) {
      return jsonResponse({
        status: "ok",
        service: "bitprivat-edge-router",
        origin: origin.origin,
        generated_at: new Date().toISOString(),
      });
    }
    if (incomingUrl.hostname === "status.bitprivat.com" && (incomingUrl.pathname === "/" || incomingUrl.pathname === "/status")) {
      return statusPage(origin.origin);
    }

    const upstreamPath = rewritePath(incomingUrl.hostname, incomingUrl.pathname);
    const upstreamUrl = new URL(upstreamPath + incomingUrl.search, origin);

    const headers = new Headers(request.headers);
    // Akash ingress validates the Host header against the SDL accept list.
    // Without this, Cloudflare fetches the origin using the random ingress host
    // and the provider returns 502 before the app receives the request.
    headers.set("Host", "app.bitprivat.com");
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
