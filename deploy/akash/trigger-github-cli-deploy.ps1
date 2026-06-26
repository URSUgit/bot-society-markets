param(
    [string]$Repo = "URSUgit/bot-society-markets",
    [string]$Ref = "main",
    [ValidateSet("status", "manifest", "update", "create", "close")]
    [string]$Mode = "update",
    [string]$ImageRef,
    [string]$Dseq,
    [string]$Provider,
    [ValidateSet("postgres", "sqlite")]
    [string]$DatabaseMode = "postgres",
    [ValidateSet("uact", "uakt")]
    [string]$PricingDenom = "uact",
    [ValidateSet("auto", "demo", "youtube")]
    [string]$SocialDiscoveryProvider = "auto",
    [int]$WaitSeconds = 90,
    [switch]$WithWorker,
    [switch]$ConfirmSpend,
    [switch]$NoVerify,
    [switch]$NoWatch
)

$ErrorActionPreference = "Stop"

function Assert-GitHubCliReady {
    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
        throw "GitHub CLI is required. Install gh and run gh auth login first."
    }

    gh auth status 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "GitHub CLI is not authenticated. Run gh auth login, then retry."
    }
}

function Get-DefaultImageRef {
    $repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
    $shortSha = (git -C $repoRoot rev-parse --short=7 $Ref 2>$null | Out-String).Trim()
    if (-not $shortSha) {
        $shortSha = (git -C $repoRoot rev-parse --short=7 HEAD | Out-String).Trim()
    }
    if (-not $shortSha) {
        throw "Could not derive a Git commit SHA for the image ref. Pass -ImageRef explicitly."
    }
    return "ghcr.io/ursugit/bot-society-markets:sha-$shortSha"
}

Assert-GitHubCliReady

$resolvedImageRef = if ($ImageRef) { $ImageRef.Trim() } else { Get-DefaultImageRef }
$verifyValue = if ($NoVerify) { "false" } else { "true" }
$withWorkerValue = if ($WithWorker) { "true" } else { "false" }
$confirmSpendValue = if ($ConfirmSpend) { "true" } else { "false" }

if ($DatabaseMode -eq "sqlite" -and $WithWorker) {
    Write-Warning "SQLite + worker is for Akash service-group compatibility only. Web and worker containers do not share the SQLite file, so use DatabaseMode postgres for real worker-fed social discovery."
}

$workflowArgs = @(
    "workflow", "run", "akash-cli-deploy.yml",
    "--repo", $Repo,
    "--ref", $Ref,
    "-f", "mode=$Mode",
    "-f", "image_ref=$resolvedImageRef",
    "-f", "wait_seconds=$WaitSeconds",
    "-f", "verify=$verifyValue",
    "-f", "with_worker=$withWorkerValue",
    "-f", "database_mode=$DatabaseMode",
    "-f", "pricing_denom=$PricingDenom",
    "-f", "confirm_spend=$confirmSpendValue",
    "-f", "social_discovery_provider=$SocialDiscoveryProvider"
)

if ($Dseq) {
    $workflowArgs += @("-f", "dseq=$Dseq")
}
if ($Provider) {
    $workflowArgs += @("-f", "provider=$Provider")
}

gh @workflowArgs
if ($LASTEXITCODE -ne 0) {
    throw "Failed to trigger Akash CLI Deploy workflow."
}

Write-Output "Triggered Akash CLI Deploy for $resolvedImageRef in $Mode mode using $DatabaseMode database mode and $PricingDenom pricing."
if (($Mode -eq "update" -or $Mode -eq "create" -or $Mode -eq "close") -and -not $ConfirmSpend) {
    Write-Warning "The workflow will skip $Mode until confirm_spend=true is supplied. Re-run with -ConfirmSpend when the deploy wallet is funded."
}

if ($NoWatch) {
    Write-Output "Watch skipped. Open GitHub Actions to follow the deployment."
    return
}

Start-Sleep -Seconds 5
$runsJson = gh run list --repo $Repo --workflow "Akash CLI Deploy" --limit 5 --json databaseId,headSha,status,conclusion,createdAt,url
$runs = $runsJson | ConvertFrom-Json
$run = @($runs | Sort-Object createdAt -Descending | Select-Object -First 1)
if (-not $run) {
    throw "Akash CLI Deploy workflow was triggered, but no run was returned by GitHub."
}

Write-Output "Watching Akash CLI Deploy run: $($run.url)"
gh run watch $run.databaseId --repo $Repo --exit-status
