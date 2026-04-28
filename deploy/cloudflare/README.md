# Cloudflare Edge Router

This deployment bridges the public BITprivat domains to the live app origin at `https://app.bitprivat.com`.

## What it fixes

- `bitprivat.com` serves the premium landing page
- `www.bitprivat.com` mirrors the public website
- `api.bitprivat.com` proxies API traffic to the app origin
- `status.bitprivat.com` resolves to the hosted status page

## Files

- `edge-router/wrangler.jsonc`: Wrangler configuration with the production routes
- `edge-router/src/index.js`: Worker that forwards each public hostname to the correct app route

## Deploy

```powershell
npx wrangler@latest login
npx wrangler@latest deploy --config deploy/cloudflare/edge-router/wrangler.jsonc
```

Or use the helper script:

```powershell
.\deploy\cloudflare\deploy-edge-router.ps1
```

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
