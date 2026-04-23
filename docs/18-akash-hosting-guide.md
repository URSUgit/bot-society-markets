# Akash Hosting Guide

## Recommended Architecture

Recommended for production:

- Akash hosts the Bot Society Markets web app
- optionally Akash hosts the worker
- managed Postgres lives outside Akash
- Neon is the recommended database choice for the first launch

Why this is the preferred path:

- the app already supports `BSM_DATABASE_URL`
- Akash is a strong fit for containerized app services
- managed Postgres is safer for production durability than provider-bound lease storage

Akash docs currently support:

- repository and container-based deployment in Console
- custom domains and SSL handling in the Console flow
- multi-service internal networking via service names
- persistent storage, with important lease-lifetime limitations

Sources:

- [Akash Console](https://akash.network/docs/developers/deployment/akash-console/)
- [GitHub Deploy Feature](https://akash.network/docs/getting-started/github-deploy-feature/)
- [SDL Syntax Reference](https://akash.network/docs/developers/deployment/akash-sdl/syntax-reference/)
- [SDL Advanced Features](https://akash.network/docs/developers/deployment/akash-sdl/advanced-features/)
- [Persistent Storage](https://akash.network/docs/network-features/persistent-storage/)
- [IP Leases](https://akash.network/docs/learn/core-concepts/ip-leases/)

## Deployment Assets In This Repo

- [Akash Bundle README](C:\Users\ionut\OneDrive\Documents\New project\deploy\akash\README.md)
- [Recommended Akash Manifest](C:\Users\ionut\OneDrive\Documents\New project\deploy\akash\web-external-postgres.yaml)
- [Fast Preview Manifest](C:\Users\ionut\OneDrive\Documents\New project\deploy\akash\web-demo-sqlite.yaml)
- [Web + Worker Akash Manifest](C:\Users\ionut\OneDrive\Documents\New project\deploy\akash\web-worker-external-postgres.yaml)
- [Experimental Full Stack Manifest](C:\Users\ionut\OneDrive\Documents\New project\deploy\akash\full-stack-postgres.yaml)
- [GHCR Publish Workflow](C:\Users\ionut\OneDrive\Documents\New project\.github\workflows\container-image.yml)
- [Production Cutover Playbook](C:\Users\ionut\OneDrive\Documents\New project\docs\19-production-cutover-playbook.md)

## Recommended Launch Flow

1. Push the repo to GitHub and let the GHCR image workflow publish the image.
2. Open Akash Console and use SDL deployment.
3. Start with [web-external-postgres.yaml](C:\Users\ionut\OneDrive\Documents\New project\deploy\akash\web-external-postgres.yaml).
4. Replace the placeholder `BSM_DATABASE_URL` with your managed Postgres connection string.
5. Replace `app.bitprivat.com` with your final app hostname if it changes.
6. Deploy the manifest.
7. Add the custom domain in Akash Console.
8. Create the corresponding DNS record in Yandex.

## Fast Preview Flow

If you want a public preview before setting up Neon:

1. Open Akash Console and use SDL deployment.
2. Start with [web-demo-sqlite.yaml](C:\Users\ionut\OneDrive\Documents\New project\deploy\akash\web-demo-sqlite.yaml).
3. Deploy it as a single web service.
4. Add `app.bitprivat.com` in Akash Console.
5. Create the matching `CNAME` in Yandex DNS.
6. Upgrade to the Neon-backed manifest once you are ready for durable production data.

## Yandex DNS Plan For bitprivat.com

Recommended structure:

- `app.bitprivat.com` -> Akash-hosted dashboard
- `bitprivat.com` -> reserved for a landing page or marketing site later

Once Akash provides the deployment hostname for the live service:

```text
Type: CNAME
Host: app
Value: <your-akash-deployment-hostname>
TTL: 21600
```

If you later choose Akash IP Lease instead of hostname-based ingress:

```text
Type: A
Host: app
Value: <your-akash-static-ip>
TTL: 21600
```

## Managed Postgres Suggestions

Good external database options:

- Neon
- Supabase
- Railway
- Render Postgres

Use a dedicated production database, not the local development SQLite path.

## Windows Deployment Note

Akash's official CLI docs currently mention a native Windows download from GitHub Releases, but the current `provider-services` release does not include a Windows binary. That makes the best path on this machine:

- Akash Console for deployment now
- WSL2 plus the Linux CLI install later if you want command-line deployment automation

## Neon Setup For This Repo

Recommended Neon flow:

1. create a Neon project
2. open the `Connect` dialog in the Neon dashboard
3. copy the connection string
4. keep `sslmode=require`
5. prefer the pooled hostname if you plan to run both web and worker

Akash-ready manifest generation:

```powershell
.\deploy\akash\prepare-bitprivat-neon.ps1 -DatabaseUrl "postgresql+psycopg://USER:PASSWORD@HOST/DBNAME?sslmode=require"
```

Or, if you want web + worker on Akash:

```powershell
.\deploy\akash\prepare-bitprivat-neon.ps1 -DatabaseUrl "postgresql+psycopg://USER:PASSWORD@HOST/DBNAME?sslmode=require" -WithWorker
```

This writes a generated manifest into `deploy/akash/` that is ready to paste into Akash Console.

Generated manifest files are ignored by Git on purpose because they may contain production database credentials.

Current helper usage with explicit host settings:

```powershell
.\deploy\akash\prepare-bitprivat-neon.ps1 `
  -DatabaseUrl "postgresql+psycopg://USER:PASSWORD@HOST/DBNAME?sslmode=require" `
  -CanonicalHost "app.bitprivat.com" `
  -RootDomain "bitprivat.com"
```

## Cloudflare After Akash Redeploys

Each fresh Akash deployment may receive a new ingress hostname. If Cloudflare continues pointing to an older Akash hostname, the app domain may return a default ingress `404`.

When that happens:

1. copy the current Akash ingress hostname from the live deployment
2. update the Cloudflare `app` CNAME target
3. keep the record proxied if you want Cloudflare-managed HTTPS

## Why Full Akash Postgres Is Not The Default

Akash persistent storage is useful, but Akash's own docs note:

- storage persists only during the lease lifetime
- storage can be lost if the deployment is migrated
- storage is lost if the lease is closed
- only a single persistent volume is supported per service

That makes full in-network Postgres more operationally fragile than managed Postgres for this project.

## Current Domain-Friendly App Behavior

This repo already supports dashboard-first domains:

- `/` can open the dashboard when `BSM_SITE_HOME_PAGE=dashboard`
- `/landing` always opens the landing page
- `/dashboard` always opens the dashboard
- `/simulation` always opens Strategy Lab

That makes `app.bitprivat.com` a clean fit for the hosted product shell.
