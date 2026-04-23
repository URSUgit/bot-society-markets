# Akash Deployment Bundle

This folder contains Akash-ready deployment assets for Bot Society Markets.

## Recommended Path

Use [web-external-postgres.yaml](C:\Users\ionut\OneDrive\Documents\New project\deploy\akash\web-external-postgres.yaml) first for production.

Why this is the recommended path:

- Akash is a good fit for the web app container.
- The project already supports external Postgres through `BSM_DATABASE_URL`.
- Managed Postgres is safer than provider-bound persistent volumes for production data.
- This gives you the fastest route to a public dashboard on `app.bitprivat.com`.

## Files

- [web-external-postgres.yaml](C:\Users\ionut\OneDrive\Documents\New project\deploy\akash\web-external-postgres.yaml): recommended single-service Akash deployment with external Postgres
- [web-demo-sqlite.yaml](C:\Users\ionut\OneDrive\Documents\New project\deploy\akash\web-demo-sqlite.yaml): fastest path to a public preview when you do not want to provision Postgres yet
- [web-worker-external-postgres.yaml](C:\Users\ionut\OneDrive\Documents\New project\deploy\akash\web-worker-external-postgres.yaml): adds the background worker on Akash while still using external Postgres
- [full-stack-postgres.yaml](C:\Users\ionut\OneDrive\Documents\New project\deploy\akash\full-stack-postgres.yaml): experimental all-in-Akash stack with Postgres persistent volume
- [run-worker-with-health.sh](C:\Users\ionut\OneDrive\Documents\New project\deploy\akash\run-worker-with-health.sh): helper used by the worker manifest
- [prepare-bitprivat-neon.ps1](C:\Users\ionut\OneDrive\Documents\New project\deploy\akash\prepare-bitprivat-neon.ps1): generates a final Akash manifest for `app.bitprivat.com` from your Neon connection string
- [Production Cutover Playbook](C:\Users\ionut\OneDrive\Documents\New project\docs\19-production-cutover-playbook.md): step-by-step move from preview SQLite hosting to managed Postgres on Akash

## Container Image

Akash deploys containers, so the app image needs to exist in a registry.

This repo now includes [container-image.yml](C:\Users\ionut\OneDrive\Documents\New project\.github\workflows\container-image.yml), which publishes the Docker image to GHCR on pushes to `main`.

Expected image path:

```text
ghcr.io/ursugit/bot-society-markets:latest
```

For Akash redeploys, prefer the immutable commit tag form:

```text
ghcr.io/ursugit/bot-society-markets:sha-<commit>
```

This avoids stale-node behavior where `latest` can resolve to an older cached image during a redeploy.

If the GHCR package remains private:

- either make the package public in GitHub package settings
- or add registry credentials in the Akash service definition before deploying

## External Postgres Recommendation

Good managed Postgres choices:

- Neon
- Supabase
- Railway
- Render Postgres

Use the provider connection string for:

```text
BSM_DATABASE_URL
```

For Neon specifically:

- use the connection string from the Neon `Connect` modal
- keep `sslmode=require`
- prefer the pooled host if you want lower connection pressure from web + worker services

The app already supports this runtime path and runs Alembic upgrades on startup.

## Fast Preview Path

If you want the dashboard public before setting up Neon, deploy [web-demo-sqlite.yaml](C:\Users\ionut\OneDrive\Documents\New project\deploy\akash\web-demo-sqlite.yaml).

Why it helps:

- no external database is required
- the app boots with local SQLite inside the container
- demo data is seeded automatically
- the dashboard can go live faster on `app.bitprivat.com`

Tradeoffs:

- this is a preview environment, not durable production storage
- if the deployment is recreated, local SQLite data can be lost
- use external Postgres before you rely on it for real operations

## Akash Console Steps

1. Open [Akash Console](https://console.akash.network/).
2. Create a new deployment.
3. Use the SDL option rather than simple framework auto-detect.
4. Paste the contents of the selected manifest.
5. Replace placeholder values:
   - domain
   - database URL
   - optional provider credentials
6. Deploy.
7. After the deployment is live, note the Akash hostname or endpoint.
8. Add the custom domain in Akash Console.
9. Point Yandex DNS to the Akash deployment target.

## bitprivat.com DNS Shape

Recommended:

```text
app.bitprivat.com -> Akash dashboard
bitprivat.com -> keep free for a landing page later
```

For Yandex DNS:

- create a `CNAME` for `app`
- point it to the hostname Akash assigns or requests for the deployment
- wait for propagation
- let Akash issue HTTPS for the custom domain

## Fastest Path For bitprivat.com

1. create a Neon project
2. copy the Neon pooled connection string
3. run:

```powershell
.\deploy\akash\prepare-bitprivat-neon.ps1 -DatabaseUrl "postgresql+psycopg://USER:PASSWORD@HOST/DBNAME?sslmode=require"
```

By default the script now pins the manifest to the current Git commit image tag when it can read the local repository SHA. You can also override it manually:

```powershell
.\deploy\akash\prepare-bitprivat-neon.ps1 `
  -DatabaseUrl "postgresql+psycopg://USER:PASSWORD@HOST/DBNAME?sslmode=require" `
  -ImageRef "ghcr.io/ursugit/bot-society-markets:sha-abcdef1"
```

4. paste the generated manifest into Akash Console
5. deploy it
6. add `app.bitprivat.com` as the Akash custom domain
7. create the matching `CNAME` in Yandex DNS

Generated manifests are intentionally ignored by Git because they can contain real database connection strings.

## Redeploy Reminder

Akash redeploys may create a new ingress hostname. When that happens, update the Cloudflare `app` CNAME target to the current deployment hostname so `app.bitprivat.com` continues routing to the live deployment.

## Windows Note

Akash's current docs still describe a native Windows CLI download path from GitHub Releases, but the current `provider-services` release does not include a Windows binary. On this machine, the professional path is:

- Akash Console first
- or WSL2 with a Linux install later if you want full CLI automation

## Important Risk Note

[full-stack-postgres.yaml](C:\Users\ionut\OneDrive\Documents\New project\deploy\akash\full-stack-postgres.yaml) is included for completeness, but it is not the safest production choice.

Akash's own docs note that persistent storage only survives during the lease lifetime and may be lost on migration or lease closure. Use the full-stack version only if you accept that operational risk.
