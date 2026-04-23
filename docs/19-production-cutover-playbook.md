# Production Cutover Playbook

## Goal

Promote the live `app.bitprivat.com` deployment from preview SQLite storage to managed Postgres while keeping Cloudflare and Akash routing stable.

## Recommended Production Shape

- Cloudflare stays in front of the app
- Akash runs the `web` service, and optionally the `worker`
- managed Postgres stores durable application data
- `app.bitprivat.com` remains the canonical product host
- `bitprivat.com` and `www.bitprivat.com` can redirect to the app host

## Current Hosted Truth

The production app host is:

```text
https://app.bitprivat.com
```

Cloudflare should keep the `app` record proxied so the browser receives a trusted certificate.

## Phase 1 - Create Managed Postgres

Recommended first choice: Neon.

What you need from the database provider:

- one production database
- one pooled Postgres connection string
- `sslmode=require`

Example format:

```text
postgresql+psycopg://USER:PASSWORD@HOST/DBNAME?sslmode=require
```

## Phase 2 - Generate the Production Akash Manifest

For the web-only deployment:

```powershell
.\deploy\akash\prepare-bitprivat-neon.ps1 `
  -DatabaseUrl "postgresql+psycopg://USER:PASSWORD@HOST/DBNAME?sslmode=require" `
  -CanonicalHost "app.bitprivat.com" `
  -RootDomain "bitprivat.com"
```

For web + worker:

```powershell
.\deploy\akash\prepare-bitprivat-neon.ps1 `
  -DatabaseUrl "postgresql+psycopg://USER:PASSWORD@HOST/DBNAME?sslmode=require" `
  -CanonicalHost "app.bitprivat.com" `
  -RootDomain "bitprivat.com" `
  -WithWorker
```

This writes a generated YAML manifest into `deploy/akash/`.

## Phase 3 - Redeploy Akash

1. Wait for the latest GitHub Actions container image workflow to complete successfully.
2. Open Akash Console.
3. Close the previous deployment.
4. Create a new SDL deployment using the generated manifest.
5. Wait for:
   - image pulled
   - container created
   - container started
6. Record the new Akash ingress hostname for the deployment.

Important:

- each fresh Akash deployment may produce a different ingress hostname
- the custom app domain must point at the current hostname

## Phase 4 - Update Cloudflare

After each Akash redeploy, update the `app` record target if the ingress hostname changed.

Cloudflare `app` record:

```text
Type: CNAME
Name: app
Target: <current-akash-ingress-hostname>
Proxy status: Proxied
TTL: Auto
```

If the root domain should also route into the same Akash app so the application can redirect it to the canonical host, point `@` and `www` to the same deployment target in Cloudflare.

## Phase 5 - Verify

Primary checks:

- `https://app.bitprivat.com`
- `/health`
- `/dashboard`
- `/simulation`

Expected production behavior:

- `app.bitprivat.com` loads over HTTPS
- cookies are marked secure
- public security headers are present
- `bitprivat.com` and `www.bitprivat.com` redirect to `https://app.bitprivat.com` once their DNS points to the same Akash app

## Data Migration Notes

The preview Akash deployment currently uses SQLite inside the container. That is useful for validation, but it is not durable production storage.

The repo already includes a database copy operation:

```powershell
python -m api.app.jobs db-copy `
  --source-path path\\to\\source.db `
  --target-url "postgresql+psycopg://USER:PASSWORD@HOST/DBNAME?sslmode=require"
```

This is ideal for local-to-Postgres promotion or controlled exports. For Akash preview SQLite running inside a live container, treat the preview data as disposable unless you have a deliberate export path from the provider environment.

## Operational Recommendation

For Bot Society Markets, the safest order is:

1. keep preview SQLite only long enough to validate public hosting
2. move to managed Postgres
3. then enable the worker
4. then start enabling live providers and secrets
