param(
    [string]$Repo = "URSUgit/bot-society-markets",
    [string]$Ref = "main",
    [string]$ImageRef,
    [string]$Dseq,
    [ValidateSet("demo", "youtube")]
    [string]$SocialDiscoveryProvider = "demo",
    [int]$WaitSeconds = 90,
    [switch]$List,
    [switch]$CreateNew,
    [switch]$WithWorker,
    [switch]$NoVerify,
    [switch]$SkipImageCheck,
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
$skipImageCheckValue = if ($SkipImageCheck) { "true" } else { "false" }
$modeValue = if ($List) {
    "list"
} elseif ($CreateNew) {
    "create_new"
} else {
    "deploy"
}

$workflowArgs = @(
    "workflow", "run", "Akash Deploy",
    "--repo", $Repo,
    "--ref", $Ref,
    "-f", "mode=$modeValue",
    "-f", "image_ref=$resolvedImageRef",
    "-f", "wait_seconds=$WaitSeconds",
    "-f", "verify=$verifyValue",
    "-f", "with_worker=$withWorkerValue",
    "-f", "skip_image_check=$skipImageCheckValue",
    "-f", "social_discovery_provider=$SocialDiscoveryProvider"
)

if ($Dseq) {
    $workflowArgs += @("-f", "dseq=$Dseq")
}

gh @workflowArgs
if ($LASTEXITCODE -ne 0) {
    throw "Failed to trigger Akash Deploy workflow."
}

Write-Output "Triggered Akash Deploy for $resolvedImageRef."

if ($NoWatch) {
    Write-Output "Watch skipped. Open GitHub Actions to follow the deployment."
    return
}

Start-Sleep -Seconds 5
$runsJson = gh run list --repo $Repo --workflow "Akash Deploy" --limit 5 --json databaseId,headSha,status,conclusion,createdAt,url
$runs = $runsJson | ConvertFrom-Json
$run = @($runs | Sort-Object createdAt -Descending | Select-Object -First 1)
if (-not $run) {
    throw "Akash Deploy workflow was triggered, but no run was returned by GitHub."
}

Write-Output "Watching Akash Deploy run: $($run.url)"
gh run watch $run.databaseId --repo $Repo --exit-status

