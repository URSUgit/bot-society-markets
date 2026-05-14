# Akash CLI Wallet Deploy

BITprivat has two Akash deployment lanes:

- **Console API lane**: uses `AKASH_API_KEY`; good for the Akash Console managed-wallet / credit-card flow.
- **CLI wallet lane**: uses `provider-services` and a funded Akash wallet mnemonic; this is the crypto-native path.

Use this CLI lane when the Console API key cannot deploy crypto-funded workloads.

## What This Ships

- `.github/workflows/akash-cli-deploy.yml`
- `deploy/akash/cli-deploy.sh`
- `deploy/akash/setup-github-cli-secrets.ps1`
- `deploy/akash/trigger-github-cli-deploy.ps1`
- `prepare-bitprivat-neon.ps1 -PricingDenom uact`

The CLI lane is intentionally separate from the current production Console API lane.

## Required GitHub Secrets

```text
AKASH_CLI_MNEMONIC
BSM_DATABASE_URL
```

For update mode:

```text
AKASH_CLI_DSEQ
```

Optional:

```text
AKASH_CLI_PROVIDER
BSM_YOUTUBE_API_KEY
```

Use a dedicated Akash deploy wallet with limited AKT. Do not use your main wallet mnemonic.

## Configure Secrets From Windows

From the repository root:

```powershell
.\deploy\akash\setup-github-cli-secrets.ps1 -IncludeDseq
```

If you know the current provider address and want to avoid active-lease lookup:

```powershell
.\deploy\akash\setup-github-cli-secrets.ps1 -IncludeDseq -IncludeProvider
```

## Run A Safe Status Check

This imports the wallet into the temporary GitHub runner keyring and queries Akash. It does not spend AKT.

```powershell
.\deploy\akash\trigger-github-cli-deploy.ps1 -Mode status
```

## Update Existing Deployment

This signs an Akash transaction and can spend gas. The `-ConfirmSpend` switch is required.

```powershell
.\deploy\akash\trigger-github-cli-deploy.ps1 -Mode update -ConfirmSpend
```

## Send Manifest Only

Use this when the chain deployment update succeeded but manifest upload failed.
It sends the rendered SDL to the active provider without signing another chain transaction.

```powershell
.\deploy\akash\trigger-github-cli-deploy.ps1 -Mode manifest
```

With an explicit immutable image:

```powershell
.\deploy\akash\trigger-github-cli-deploy.ps1 `
  -Mode update `
  -ImageRef "ghcr.io/ursugit/bot-society-markets:sha-abcdef1" `
  -ConfirmSpend
```

## Create A New Deployment

This creates a new deployment, waits for bids, accepts the first bid unless a provider is supplied, and sends the manifest.

```powershell
.\deploy\akash\trigger-github-cli-deploy.ps1 -Mode create -ConfirmSpend
```

To force a provider:

```powershell
.\deploy\akash\trigger-github-cli-deploy.ps1 `
  -Mode create `
  -Provider "akash1..." `
  -ConfirmSpend
```

After a create, copy the DSEQ printed in the GitHub workflow summary and store it:

```powershell
$env:AKASH_CLI_DSEQ = "new-dseq"
.\deploy\akash\setup-github-cli-secrets.ps1 -IncludeDseq
```

## Autonomous CLI Redeploys

The workflow listens for successful `Container Image` runs on `main`, but it only auto-deploys when repository variables explicitly allow it:

```text
AKASH_CLI_AUTO_DEPLOY=true
AKASH_CLI_AUTO_CONFIRM_SPEND=true
```

Keep these off until the wallet is funded and the status check succeeds.

## Notes

- CLI-generated SDL uses `uact` pricing because official Akash SDL docs use ACT (`uact`) for deployment pricing and escrow.
- CLI gas still uses `uakt`, so the deploy script keeps `AKASH_GAS_PRICES=0.025uakt`.
- The existing Console API workflow is untouched and remains the safe production fallback.
- Generated SDL files stay ignored because they can contain database URLs and API keys.
