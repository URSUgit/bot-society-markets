param(
    [string]$ApiKey = $env:AKASH_API_KEY,
    [string]$Dseq = $env:AKASH_DSEQ,
    [string]$DatabaseUrl = $env:BSM_DATABASE_URL,
    [string]$ImageRef,
    [string]$SdlPath,
    [string]$RootDomain = "bitprivat.com",
    [string]$CanonicalHost = "bitprivat.com",
    [switch]$WithWorker,
    [switch]$CreateNew,
    [switch]$List,
    [switch]$NoVerify,
    [switch]$SkipImageWorkflowCheck,
    [switch]$EnableAppCanonicalRedirects,
    [decimal]$DepositUsd = 5,
    [int]$WaitSeconds = 90,
    [string]$SocialDiscoveryProvider = $env:BSM_SOCIAL_DISCOVERY_PROVIDER,
    [string]$YouTubeApiKey = $env:BSM_YOUTUBE_API_KEY,
    [string]$YouTubeDiscoveryQueries = $env:BSM_YOUTUBE_DISCOVERY_QUERIES,
    [string]$YouTubeChannelIds = $env:BSM_YOUTUBE_CHANNEL_IDS,
    [string]$YouTubeVideoLimit = $env:BSM_YOUTUBE_VIDEO_LIMIT
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$prepareScript = Join-Path $PSScriptRoot "prepare-bitprivat-neon.ps1"
$updateScript = Join-Path $PSScriptRoot "update-console-deployment.ps1"

function Resolve-RepoPath {
    param([Parameter(Mandatory = $true)][string]$Path)

    if ([System.IO.Path]::IsPathRooted($Path)) {
        return $Path
    }
    return Join-Path $repoRoot $Path
}

function Get-CurrentImageRef {
    $shortSha = (git -C $repoRoot rev-parse --short=7 HEAD | Out-String).Trim()
    if (-not $shortSha) {
        throw "Could not derive the current Git commit SHA for the image tag."
    }
    return "ghcr.io/ursugit/bot-society-markets:sha-$shortSha"
}

function Assert-ContainerImagePublished {
    param([Parameter(Mandatory = $true)][string]$ActiveImageRef)

    if ($ActiveImageRef -notmatch ":sha-(?<ShortSha>[0-9a-f]{7,})$") {
        Write-Output "Image workflow check skipped because image is not an immutable sha tag: $ActiveImageRef"
        return
    }

    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
        throw "GitHub CLI is required for image workflow verification. Re-run with -SkipImageWorkflowCheck to bypass."
    }

    $shortSha = $Matches.ShortSha
    $runJson = gh run list --workflow "Container Image" --branch main --limit 20 --json headSha,status,conclusion,url 2>$null
    if (-not $runJson) {
        throw "Could not read GitHub Container Image workflow runs. Re-run with -SkipImageWorkflowCheck to bypass."
    }

    $runs = $runJson | ConvertFrom-Json
    $matchingRun = @($runs | Where-Object { $_.headSha -like "$shortSha*" } | Select-Object -First 1)
    if (-not $matchingRun) {
        throw "No Container Image workflow run found for sha-$shortSha. Wait for GHCR publish or re-run with -SkipImageWorkflowCheck."
    }
    if ($matchingRun.status -ne "completed" -or $matchingRun.conclusion -ne "success") {
        throw "Container Image workflow for sha-$shortSha is not green yet: status=$($matchingRun.status) conclusion=$($matchingRun.conclusion) url=$($matchingRun.url)"
    }

    Write-Output "Container image workflow verified for sha-$shortSha."
}

if (-not (Test-Path -LiteralPath $prepareScript)) {
    throw "Manifest generator not found: $prepareScript"
}
if (-not (Test-Path -LiteralPath $updateScript)) {
    throw "Akash Console updater not found: $updateScript"
}

if ($List) {
    & $updateScript -ApiKey $ApiKey -List
    return
}

if (-not $ApiKey) {
    throw "AKASH_API_KEY is not configured. Set it in the shell or GitHub repository secrets before deploying."
}
if (-not $CreateNew -and -not $Dseq) {
    throw "AKASH_DSEQ is not configured. Set it to the existing Akash deployment DSEQ, or run with -CreateNew."
}

$activeImageRef = if ($ImageRef) { $ImageRef.Trim() } else { Get-CurrentImageRef }
if (-not $SkipImageWorkflowCheck) {
    Assert-ContainerImagePublished -ActiveImageRef $activeImageRef
}

$activeSdlPath = $null
if ($SdlPath) {
    $activeSdlPath = Resolve-RepoPath -Path $SdlPath
    if (-not (Test-Path -LiteralPath $activeSdlPath)) {
        throw "SDL file not found: $activeSdlPath"
    }
} else {
    if (-not $DatabaseUrl) {
        throw "BSM_DATABASE_URL is not configured. Pass -DatabaseUrl or set the environment variable before generating the SDL."
    }

    $shortTag = if ($activeImageRef -match ":sha-(?<ShortSha>[0-9a-f]{7,})$") { $Matches.ShortSha } else { "custom" }
    $outputName = if ($WithWorker) {
        "web-worker-external-postgres.bitprivat.sha-$shortTag.generated.yaml"
    } else {
        "web-external-postgres.bitprivat.sha-$shortTag.generated.yaml"
    }
    $activeSdlPath = Join-Path $PSScriptRoot $outputName

    $prepareArgs = @{
        DatabaseUrl = $DatabaseUrl
        CanonicalHost = $CanonicalHost
        RootDomain = $RootDomain
        ImageRef = $activeImageRef
        OutputPath = $activeSdlPath
        SocialDiscoveryProvider = if ($SocialDiscoveryProvider) { $SocialDiscoveryProvider } else { "demo" }
        YouTubeApiKey = if ($YouTubeApiKey) { $YouTubeApiKey } else { "" }
        YouTubeDiscoveryQueries = if ($YouTubeDiscoveryQueries) { $YouTubeDiscoveryQueries } else { "crypto market analysis,polymarket trading,prediction market analysis,macro trading" }
        YouTubeChannelIds = if ($YouTubeChannelIds) { $YouTubeChannelIds } else { "" }
        YouTubeVideoLimit = if ($YouTubeVideoLimit) { $YouTubeVideoLimit } else { "12" }
    }
    if ($WithWorker) {
        $prepareArgs.WithWorker = $true
    }
    if ($EnableAppCanonicalRedirects) {
        $prepareArgs.EnableAppCanonicalRedirects = $true
    }

    & $prepareScript @prepareArgs
}

Write-Output "Deploying Akash SDL: $activeSdlPath"
Write-Output "Deploying image: $activeImageRef"

$updateArgs = @{
    ApiKey = $ApiKey
    SdlPath = $activeSdlPath
    WaitSeconds = $WaitSeconds
    ExpectOperatorStrip = $true
    ExpectSocialTrading = $true
}
if ($CreateNew) {
    $updateArgs.CreateNew = $true
    $updateArgs.DepositUsd = $DepositUsd
} else {
    $updateArgs.Dseq = $Dseq
}
if (-not $NoVerify) {
    $updateArgs.Verify = $true
}

& $updateScript @updateArgs

Write-Output "Akash production deployment command completed."
