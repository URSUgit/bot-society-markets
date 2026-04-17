# Custom Domain Dashboard Launch Plan

This plan is for putting the Bot Society Markets dashboard on a real domain, such as `app.example.com` or `example.com`.

## Recommended Domain Shape

Use a dashboard-first subdomain first:

- `app.yourdomain.com` for the Bot Society Markets dashboard
- `www.yourdomain.com` or `yourdomain.com/landing` for marketing later

This keeps the product app clean, avoids conflict with future landing pages, and makes DNS changes easier to reason about.

## What The App Now Supports

The application supports `BSM_SITE_HOME_PAGE`.

- `BSM_SITE_HOME_PAGE=landing` keeps `/` as the landing page.
- `BSM_SITE_HOME_PAGE=dashboard` makes `/` serve the dashboard directly.
- `/landing` always serves the landing page.
- `/dashboard` always serves the dashboard.
- `/simulation` always serves Strategy Lab.

The Render blueprint sets `BSM_SITE_HOME_PAGE=dashboard` for hosted environments, so a production custom domain opens the dashboard at the root URL.

## Render Setup

1. Deploy the repo using `render.yaml`.
2. In Render, open the web service: `bot-society-markets-web`.
3. Open `Settings`.
4. Find `Custom Domains`.
5. Add the chosen domain, for example `app.yourdomain.com`.
6. Render will show the DNS target, usually the service's `onrender.com` hostname.
7. Add the DNS record at your domain provider.
8. Return to Render and click `Verify`.
9. Wait for Render to issue the TLS certificate.
10. Open the domain in a browser.

## DNS Records

For a subdomain such as `app.yourdomain.com`:

```text
Type: CNAME
Name: app
Target: your-render-service.onrender.com
TTL: Auto or 300
```

For Cloudflare:

- Set the record to `DNS only` while Render verifies the domain.
- After the Render certificate is valid, Cloudflare proxying can be enabled if needed.
- Remove conflicting `AAAA` records while configuring Render domains.

For a root domain such as `yourdomain.com`:

- Add the root domain in Render.
- Use the DNS record type your provider supports for apex/root domains.
- Cloudflare can use a flattened CNAME at `@`.
- Other providers may use `ALIAS` or `ANAME`.
- Also configure `www` if you want both `yourdomain.com` and `www.yourdomain.com`.

## Launch Checklist

- Domain chosen.
- Render service deployed and healthy.
- Custom domain added to Render.
- DNS record added at the domain provider.
- Render verification succeeds.
- HTTPS certificate is issued.
- `https://yourdomain.com` or `https://app.yourdomain.com` opens the dashboard.
- `https://yourdomain.com/landing` opens the landing page.
- `https://yourdomain.com/simulation` opens Strategy Lab.

## Recommended Next Move

Send the exact domain name and where it is managed, for example:

```text
Domain: app.example.com
DNS provider: Cloudflare
```

Then the DNS record can be made exact instead of generic.
