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
- [cli-deploy.sh](C:\Users\ionut\OneDrive\Documents\New project\deploy\akash\cli-deploy.sh): GitHub Actions helper for crypto-wallet Akash CLI deploys
- [trigger-github-cli-deploy.ps1](C:\Users\ionut\OneDrive\Documents\New project\deploy\akash\trigger-github-cli-deploy.ps1): triggers the Akash CLI deploy workflow
- [setup-github-cli-secrets.ps1](C:\Users\ionut\OneDrive\Documents\New project\deploy\akash\setup-github-cli-secrets.ps1): stores wallet deploy secrets in GitHub Actions
- [Akash CLI Wallet Deploy](C:\Users\ionut\OneDrive\Documents\New project\docs\28-akash-cli-wallet-deploy.md): crypto-native Akash deployment guide
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

To get the current production candidate from this local repository:

```powershell
git fetch origin main
$shortSha = git rev-parse --short=7 origin/main
"ghcr.io/ursugit/bot-society-markets:sha-$shortSha"
```

Use that tag in Akash Console to make the live dashboard pick up the latest
merged app code without relying on cached `latest` pulls.

The Akash templates also include the social-trader discovery defaults:

```text
BSM_SOCIAL_DISCOVERY_PROVIDER=demo
BSM_YOUTUBE_API_KEY=
BSM_YOUTUBE_DISCOVERY_QUERIES=crypto market analysis,polymarket trading,prediction market analysis,macro trading
BSM_YOUTUBE_VIDEO_LIMIT=12
```

Use `demo` until you add a YouTube Data API key. The GitHub Akash Deploy
workflow now defaults `social_discovery_provider` to `auto`: if the
`BSM_YOUTUBE_API_KEY` repository secret exists, it renders the deployment with
`BSM_SOCIAL_DISCOVERY_PROVIDER=youtube`; otherwise it keeps deterministic demo
discovery. You can still force `demo` or `youtube` from workflow dispatch.

After changing the Akash environment, verify the connector state from the
running image:

```powershell
python -m api.app.jobs provider-status
python -m api.app.jobs social-discovery
```

Expected production posture after the key is present:

```text
social_discovery_provider_mode=youtube
social_discovery_provider_source=youtube-data-api
social_discovery_configured=True
social_discovery_live_capable=True
social_discovery_ready=True
```

If `social_discovery_ready=False`, keep the deployment in demo discovery mode or
add the missing `BSM_YOUTUBE_API_KEY`, `BSM_YOUTUBE_DISCOVERY_QUERIES`, or
`BSM_YOUTUBE_CHANNEL_IDS` value before promoting the redeploy.

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

## Cloudflare HTTPS Note

When `bitprivat.com` is proxied through Cloudflare, leave the Akash app setting
as:

```text
BSM_CANONICAL_HOST=
BSM_CANONICAL_REDIRECT_HOSTS=
BSM_FORCE_HTTPS=false
BSM_SECURE_SESSION_COOKIE=true
```

Cloudflare should own browser HTTPS redirects and hostname routing at the edge.
If the app also forces HTTPS or canonicalizes `api.bitprivat.com` /
`status.bitprivat.com` to the root host inside Akash, Cloudflare can receive
same-URL or cross-host `308` redirects from the origin and the dashboard will
appear down because of a redirect loop.

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

## Automated Production Redeploy

The preferred production path is now the one-command wrapper:

```powershell
$env:AKASH_API_KEY = "your-akash-console-api-key"
$env:AKASH_DSEQ = "your-existing-deployment-dseq"
$env:BSM_DATABASE_URL = "postgresql+psycopg://USER:PASSWORD@HOST/DBNAME?sslmode=require"
.\deploy\akash\deploy-production.ps1
```

What it does:

- derives the immutable GHCR image tag from the current Git commit
- checks that the matching `Container Image` workflow has published the image
- generates a secret-bearing SDL locally in `deploy/akash/*.generated.yaml`
- keeps Cloudflare-safe app settings by default:
  - `BSM_CANONICAL_HOST=`
  - `BSM_CANONICAL_REDIRECT_HOSTS=`
  - `BSM_FORCE_HTTPS=false`
  - `BSM_SECURE_SESSION_COOKIE=true`
- updates the existing Akash deployment through the Akash Console API
- waits for rollout and runs production verification

Useful commands:

```powershell
.\deploy\akash\deploy-production.ps1 -List
.\deploy\akash\deploy-production.ps1 -ImageRef "ghcr.io/ursugit/bot-society-markets:sha-5684e60"
.\deploy\akash\deploy-production.ps1 -NoVerify
.\deploy\akash\deploy-production.ps1 -WithWorker
```

Operator setup helpers:

```powershell
.\deploy\akash\check-deploy-readiness.ps1
.\deploy\akash\setup-github-secrets.ps1
.\deploy\akash\trigger-github-deploy.ps1 -ImageRef "ghcr.io/ursugit/bot-society-markets:sha-6499e5a"
```

`setup-github-secrets.ps1` reads values from the current environment when they
are already present. If they are not present, it prompts locally and writes them
to GitHub Actions secrets through `gh secret set`. It does not write secrets to
the repository.

For YouTube social discovery activation:

```powershell
$env:BSM_YOUTUBE_API_KEY = "your-youtube-data-api-key"
.\deploy\akash\setup-github-secrets.ps1 -IncludeYouTube
.\deploy\akash\trigger-github-deploy.ps1
```

Do not commit generated manifests. They can contain production database and API
credentials and are intentionally ignored by Git.

## GitHub Actions Automation

This repo includes `.github/workflows/akash-deploy.yml`.

Add these repository secrets:

```text
AKASH_API_KEY
AKASH_DSEQ
BSM_DATABASE_URL
```

Optional:

```text
BSM_YOUTUBE_API_KEY
```

After the secrets are configured, the workflow can redeploy Akash from GitHub
Actions. Manual dispatch is always available. Automatic redeploy after a
successful `Container Image` run is opt-in through this repository variable:

```text
AKASH_CONSOLE_AUTO_DEPLOY=true
```

Keep it off when the Console API key has no active deployments or the saved
`AKASH_DSEQ` points to a closed deployment. The social discovery provider defaults to `auto`: the
workflow promotes to YouTube when `BSM_YOUTUBE_API_KEY` is set, and keeps demo
mode when it is not. If any required secret is missing, the workflow skips the
deploy with a notice instead of failing the whole project pipeline.

To trigger it manually from PowerShell:

```powershell
.\deploy\akash\trigger-github-deploy.ps1
```

## Crypto Wallet CLI Deploy

If the Akash Console API works only for the credit-card / managed-wallet path,
use the separate Akash CLI lane. It runs `provider-services` in GitHub Actions
with a dedicated funded wallet mnemonic and does not replace the Console API
workflow.

Configure the wallet deploy secrets:

```powershell
.\deploy\akash\setup-github-cli-secrets.ps1 -IncludeDseq
```

Run a no-spend status check:

```powershell
.\deploy\akash\trigger-github-cli-deploy.ps1 -Mode status
```

Update the existing deployment through the crypto wallet CLI path:

```powershell
.\deploy\akash\trigger-github-cli-deploy.ps1 -Mode update -ConfirmSpend
```

Full operating guide:

- [Akash CLI Wallet Deploy](C:\Users\ionut\OneDrive\Documents\New project\docs\28-akash-cli-wallet-deploy.md)

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

After every Akash redeploy, run this from the repository root:

```powershell
.\deploy\verify-production.ps1 -ExpectOperatorStrip
```

If the operator strip check fails but the dashboard shell passes, the Akash
deployment is still on an older image.

## Windows Note

Akash's current docs still describe a native Windows CLI download path from GitHub Releases, but the current `provider-services` release does not include a Windows binary. On this machine, the professional path is:

- Akash Console first
- GitHub Actions Akash CLI deploy for the crypto-wallet path
- or WSL2 with a Linux install if you want to run `provider-services` directly on this workstation

## Important Risk Note

[full-stack-postgres.yaml](C:\Users\ionut\OneDrive\Documents\New project\deploy\akash\full-stack-postgres.yaml) is included for completeness, but it is not the safest production choice.

Akash's own docs note that persistent storage only survives during the lease lifetime and may be lost on migration or lease closure. Use the full-stack version only if you accept that operational risk.
