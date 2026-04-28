const RESERVED_ROOT_REWRITES = {
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

export default {
  async fetch(request, env) {
    const incomingUrl = new URL(request.url);
    const origin = normalizeOrigin(env.ORIGIN_BASE_URL || "https://app.bitprivat.com");
    const upstreamPath = rewritePath(incomingUrl.hostname, incomingUrl.pathname);
    const upstreamUrl = new URL(upstreamPath + incomingUrl.search, origin);

    const headers = new Headers(request.headers);
    headers.set("x-forwarded-host", incomingUrl.host);
    headers.set("x-forwarded-proto", incomingUrl.protocol.replace(":", "") || "https");

    const upstreamResponse = await fetch(upstreamUrl, {
      method: request.method,
      headers,
      body: request.method === "GET" || request.method === "HEAD" ? undefined : request.body,
      redirect: "manual",
    });

    const response = new Response(upstreamResponse.body, {
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
