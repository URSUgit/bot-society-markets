param(
    [Parameter(Mandatory = $true)]
    [string]$DatabaseUrl,

    [string]$CanonicalHost = "bitprivat.com",

    [string]$RootDomain = "bitprivat.com",

    [string]$ImageRef,

    [switch]$WithWorker,

    [switch]$EnableAppCanonicalRedirects,

    [string]$SocialDiscoveryProvider = $env:BSM_SOCIAL_DISCOVERY_PROVIDER,

    [string]$YouTubeApiKey = $env:BSM_YOUTUBE_API_KEY,

    [string]$YouTubeDiscoveryQueries = $env:BSM_YOUTUBE_DISCOVERY_QUERIES,

    [string]$YouTubeChannelIds = $env:BSM_YOUTUBE_CHANNEL_IDS,

    [string]$YouTubeVideoLimit = $env:BSM_YOUTUBE_VIDEO_LIMIT,

    [string]$OutputPath
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$templatePath = if ($WithWorker) {
    Join-Path $PSScriptRoot "web-worker-external-postgres.yaml"
} else {
    Join-Path $PSScriptRoot "web-external-postgres.yaml"
}

if (-not (Test-Path -LiteralPath $templatePath)) {
    throw "Template not found: $templatePath"
}

$defaultOutputName = if ($WithWorker) {
    "web-worker-external-postgres.bitprivat.generated.yaml"
} else {
    "web-external-postgres.bitprivat.generated.yaml"
}

$resolvedOutputPath = if ($OutputPath) {
    if ([System.IO.Path]::IsPathRooted($OutputPath)) {
        $OutputPath
    } else {
        Join-Path $repoRoot $OutputPath
    }
} else {
    Join-Path $PSScriptRoot $defaultOutputName
}

$resolvedImageRef = if ($ImageRef) {
    $ImageRef.Trim()
} else {
    $gitShortSha = ""
    try {
        $gitShortSha = (git -C $repoRoot rev-parse --short=7 HEAD 2>$null | Out-String).Trim()
    } catch {
        $gitShortSha = ""
    }

    if ($gitShortSha) {
        "ghcr.io/ursugit/bot-society-markets:sha-$gitShortSha"
    } else {
        "ghcr.io/ursugit/bot-society-markets:latest"
    }
}

$template = Get-Content -LiteralPath $templatePath -Raw
$databaseUrlEscaped = $DatabaseUrl.Replace("`r", "").Replace("`n", "")
$canonicalHostEscaped = $CanonicalHost.Trim()
$rootDomainEscaped = $RootDomain.Trim()
$wwwHostEscaped = "www.$rootDomainEscaped"
$appHostEscaped = "app.$rootDomainEscaped"
$apiHostEscaped = "api.$rootDomainEscaped"
$statusHostEscaped = "status.$rootDomainEscaped"
$socialProviderEscaped = if ($SocialDiscoveryProvider) { $SocialDiscoveryProvider.Trim() } else { "demo" }
$youtubeApiKeyEscaped = if ($YouTubeApiKey) { $YouTubeApiKey.Replace("`r", "").Replace("`n", "") } else { "" }
$youtubeQueriesEscaped = if ($YouTubeDiscoveryQueries) { $YouTubeDiscoveryQueries.Replace("`r", "").Replace("`n", "") } else { "crypto market analysis,polymarket trading,prediction market analysis,macro trading" }
$youtubeChannelIdsEscaped = if ($YouTubeChannelIds) { $YouTubeChannelIds.Replace("`r", "").Replace("`n", "") } else { "" }
$youtubeVideoLimitEscaped = if ($YouTubeVideoLimit) { $YouTubeVideoLimit.Trim() } else { "12" }
$rendered = $template.Replace(
    "ghcr.io/ursugit/bot-society-markets:latest",
    $resolvedImageRef
).Replace(
    "postgresql+psycopg://USER:PASSWORD@HOST/DBNAME?sslmode=require",
    $databaseUrlEscaped
)
$rendered = $rendered.Replace("status.bitprivat.com", $statusHostEscaped)
$rendered = $rendered.Replace("api.bitprivat.com", $apiHostEscaped)
$rendered = $rendered.Replace("app.bitprivat.com", $appHostEscaped)
$rendered = $rendered.Replace("www.bitprivat.com", $wwwHostEscaped)
$rendered = $rendered.Replace("bitprivat.com", $rootDomainEscaped)

if ($EnableAppCanonicalRedirects) {
    $rendered = $rendered -replace "BSM_CANONICAL_HOST=[^`r`n]*", "BSM_CANONICAL_HOST=$canonicalHostEscaped"
    $rendered = $rendered -replace "BSM_CANONICAL_REDIRECT_HOSTS=[^`r`n]*", "BSM_CANONICAL_REDIRECT_HOSTS=$wwwHostEscaped,$appHostEscaped"
    $rendered = $rendered -replace "BSM_FORCE_HTTPS=[^`r`n]*", "BSM_FORCE_HTTPS=true"
    $rendered = $rendered -replace "BSM_SECURE_SESSION_COOKIE=[^`r`n]*", "BSM_SECURE_SESSION_COOKIE=true"
} else {
    $rendered = $rendered -replace "BSM_CANONICAL_HOST=[^`r`n]*", "BSM_CANONICAL_HOST="
    $rendered = $rendered -replace "BSM_CANONICAL_REDIRECT_HOSTS=[^`r`n]*", "BSM_CANONICAL_REDIRECT_HOSTS="
    $rendered = $rendered -replace "BSM_FORCE_HTTPS=[^`r`n]*", "BSM_FORCE_HTTPS=false"
    $rendered = $rendered -replace "BSM_SECURE_SESSION_COOKIE=[^`r`n]*", "BSM_SECURE_SESSION_COOKIE=true"
}

$rendered = $rendered -replace "BSM_SOCIAL_DISCOVERY_PROVIDER=[^`r`n]*", "BSM_SOCIAL_DISCOVERY_PROVIDER=$socialProviderEscaped"
$rendered = $rendered -replace "BSM_YOUTUBE_API_KEY=[^`r`n]*", "BSM_YOUTUBE_API_KEY=$youtubeApiKeyEscaped"
$rendered = $rendered -replace "BSM_YOUTUBE_DISCOVERY_QUERIES=[^`r`n]*", "BSM_YOUTUBE_DISCOVERY_QUERIES=$youtubeQueriesEscaped"
$rendered = $rendered -replace "BSM_YOUTUBE_CHANNEL_IDS=[^`r`n]*", "BSM_YOUTUBE_CHANNEL_IDS=$youtubeChannelIdsEscaped"
$rendered = $rendered -replace "BSM_YOUTUBE_VIDEO_LIMIT=[^`r`n]*", "BSM_YOUTUBE_VIDEO_LIMIT=$youtubeVideoLimitEscaped"

$outputDirectory = Split-Path -Parent $resolvedOutputPath
if ($outputDirectory -and -not (Test-Path -LiteralPath $outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}

Set-Content -LiteralPath $resolvedOutputPath -Value $rendered -Encoding UTF8
Write-Output "Generated Akash manifest: $resolvedOutputPath"
Write-Output "Pinned image: $resolvedImageRef"
