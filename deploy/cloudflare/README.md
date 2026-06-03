# Cloudflare Edge Router

This deployment updates the existing `bot-society-markets` Worker and bridges the public BITprivat domains to the live app origin at `https://app.bitprivat.com`.

## What it fixes

- `bitprivat.com` serves the premium landing page from `/landing`
- `www.bitprivat.com` mirrors the public website from `/landing`
- `app.bitprivat.com` serves the dashboard through the edge router instead of depending on a direct Akash CNAME
- `api.bitprivat.com` proxies API traffic to the app origin
- `status.bitprivat.com` resolves to the hosted status page

## Files

- `../../wrangler.jsonc`: root Wrangler configuration used by Cloudflare Git builds
- `edge-router/wrangler.jsonc`: equivalent nested configuration for manual deploys from this folder
- `edge-router/src/index.js`: Worker that forwards each public hostname to the correct app route

## Deploy

```powershell
npx wrangler@latest login
npx wrangler@latest deploy --config wrangler.jsonc
```

Or use the helper script:

```powershell
.\deploy\cloudflare\deploy-edge-router.ps1
```

GitHub Actions can also deploy the router automatically from
[cloudflare-worker.yml](C:\Users\ionut\Documents\New project\.github\workflows\cloudflare-worker.yml).
Add these repository secrets to enable it:

- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_API_TOKEN`

The workflow intentionally skips deployment instead of failing CI when those
secrets are not present.

### Enable GitHub automatic Cloudflare deploy

Create a Cloudflare API token from the dashboard, then run:

```powershell
.\deploy\cloudflare\setup-github-secrets.ps1 -TriggerWorkflow
```

Use a custom API token scoped to the `bitprivat.com` zone and the account that
owns the `bot-society-markets` Worker. Required capabilities:

- Account: `Cloudflare Workers Scripts:Edit`
- Zone: `Workers Routes:Edit`
- Zone: `Zone:Read`

The helper sets `CLOUDFLARE_ACCOUNT_ID`, prompts for `CLOUDFLARE_API_TOKEN`
without echoing it, stores both through `gh secret set`, and can trigger the
Cloudflare Worker workflow to prove GitHub deployment works.

## Verify

After deploy, confirm:

```powershell
curl.exe https://bitprivat.com/
curl.exe https://bitprivat.com/dashboard
curl.exe https://app.bitprivat.com/
curl.exe https://api.bitprivat.com/api/v1/system/pulse
curl.exe https://status.bitprivat.com/
```

For strict origin verification, use:

```powershell
.\deploy\verify-production.ps1 -ExpectOperatorStrip -ExpectSocialTrading -RequireLiveOrigin -CheckDirectOrigin
```

This adds `edge_require_live=1` to trading-critical public API checks. The
verification fails if Cloudflare serves `edge-fallback`, `edge-snapshot`, or an
origin-unavailable response where live origin data is expected.

For a direct Cloudflare-to-origin probe:

```powershell
curl.exe https://bitprivat.com/api/runtime/edge-health
```

## Notes

- The Worker preserves `x-forwarded-host`, so the FastAPI app can render the correct landing or status surface.
- HTML and client-facing API responses are marked `no-store` to avoid browser-stale control-plane pages.
- Anonymous read-only public API payloads use a short edge cache after a successful live response and fall back to bundled public snapshots if Akash does not respond before the origin deadline. The `X-BITprivat-Data-Mode` header exposes `live-origin`, `edge-live-cache`, or `edge-fallback` delivery.
- Fallback responses also expose `Warning`, `X-BITprivat-Fallback-Reason`, and when available origin status/error headers so standby data is never silent.
- `/api/runtime/public-origin` exposes the active Akash read origin so the anonymous Social Traders panel can hydrate live public creator evidence directly when the Worker-to-ingress hop is degraded.
- `/api/runtime/edge-health` performs a bounded origin probe from inside the Worker and returns origin reachability without exposing secrets.
- Authenticated reads and all state-changing API requests always reach the FastAPI origin; they are never served from the public fallback cache.
- Static assets are allowed a short cache window to keep the public site fast without pinning old HTML.
- The Worker name intentionally matches the route owner already configured in Cloudflare.
- The root `wrangler.jsonc` is intentional, so Cloudflare's Git build deploys the same Worker as manual Wrangler deploys.
