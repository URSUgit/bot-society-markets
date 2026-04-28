# Cloudflare Edge Router

This deployment updates the existing `bot-society-markets` Worker and bridges the public BITprivat domains to the live app origin at `https://app.bitprivat.com`.

## What it fixes

- `bitprivat.com` serves the premium landing page from `/landing`
- `www.bitprivat.com` mirrors the public website from `/landing`
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
[cloudflare-worker.yml](C:\Users\ionut\OneDrive\Documents\New project\.github\workflows\cloudflare-worker.yml).
Add these repository secrets to enable it:

- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_API_TOKEN`

The workflow intentionally skips deployment instead of failing CI when those
secrets are not present.

## Verify

After deploy, confirm:

```powershell
curl.exe https://bitprivat.com/
curl.exe https://bitprivat.com/dashboard
curl.exe https://api.bitprivat.com/api/v1/system/pulse
curl.exe https://status.bitprivat.com/
```

## Notes

- The Worker preserves `x-forwarded-host`, so the FastAPI app can render the correct landing or status surface.
- API and HTML responses are marked `no-store` to avoid Cloudflare serving stale control-plane pages.
- Static assets are allowed a short cache window to keep the public site fast without pinning old HTML.
- The Worker name intentionally matches the route owner already configured in Cloudflare.
- The root `wrangler.jsonc` is intentional, so Cloudflare's Git build deploys the same Worker as manual Wrangler deploys.
