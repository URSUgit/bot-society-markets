# Akash Hosting Guide

## Recommended Architecture

Recommended for production:

- Akash hosts the Bot Society Markets web app
- optionally Akash hosts the worker
- managed Postgres lives outside Akash

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
- [Web + Worker Akash Manifest](C:\Users\ionut\OneDrive\Documents\New project\deploy\akash\web-worker-external-postgres.yaml)
- [Experimental Full Stack Manifest](C:\Users\ionut\OneDrive\Documents\New project\deploy\akash\full-stack-postgres.yaml)
- [GHCR Publish Workflow](C:\Users\ionut\OneDrive\Documents\New project\.github\workflows\container-image.yml)

## Recommended Launch Flow

1. Push the repo to GitHub and let the GHCR image workflow publish the image.
2. Open Akash Console and use SDL deployment.
3. Start with [web-external-postgres.yaml](C:\Users\ionut\OneDrive\Documents\New project\deploy\akash\web-external-postgres.yaml).
4. Replace the placeholder `BSM_DATABASE_URL` with your managed Postgres connection string.
5. Replace `app.bitprivat.com` with your final app hostname if it changes.
6. Deploy the manifest.
7. Add the custom domain in Akash Console.
8. Create the corresponding DNS record in Yandex.

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
