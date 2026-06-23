param(
    [string]$DatabaseUrl,

    [ValidateSet("postgres", "sqlite")]
    [string]$DatabaseMode = "postgres",

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

    [string]$SocialDiscoveryIntervalSeconds = $env:BSM_SOCIAL_DISCOVERY_INTERVAL_SECONDS,

    [string]$ExtraAcceptHosts = $env:AKASH_EXTRA_ACCEPT_HOSTS,

    [ValidateSet("uact", "uakt")]
    [string]$PricingDenom = "uact",

    [string]$OutputPath
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$templatePath = if ($DatabaseMode -eq "sqlite") {
    Join-Path $PSScriptRoot "web-demo-sqlite.yaml"
} elseif ($WithWorker) {
    Join-Path $PSScriptRoot "web-worker-external-postgres.yaml"
} else {
    Join-Path $PSScriptRoot "web-external-postgres.yaml"
}

if (-not (Test-Path -LiteralPath $templatePath)) {
    throw "Template not found: $templatePath"
}

$defaultOutputName = if ($DatabaseMode -eq "sqlite") {
    "web-demo-sqlite.bitprivat.generated.yaml"
} elseif ($WithWorker) {
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
if ($DatabaseMode -eq "postgres" -and -not $DatabaseUrl) {
    throw "DatabaseUrl is required when DatabaseMode is postgres. Use -DatabaseMode sqlite for the emergency no-Postgres SDL."
}

$databaseUrlEscaped = if ($DatabaseUrl) { $DatabaseUrl.Replace("`r", "").Replace("`n", "") } else { "" }
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
$socialDiscoveryIntervalEscaped = if ($SocialDiscoveryIntervalSeconds) { $SocialDiscoveryIntervalSeconds.Trim() } else { "1800" }
$rendered = $template.Replace(
    "ghcr.io/ursugit/bot-society-markets:latest",
    $resolvedImageRef
)
if ($DatabaseMode -eq "postgres") {
    $rendered = $rendered.Replace(
        "postgresql+psycopg://USER:PASSWORD@HOST/DBNAME?sslmode=require",
        $databaseUrlEscaped
    )
}
$rendered = $rendered.Replace("status.bitprivat.com", $statusHostEscaped)
$rendered = $rendered.Replace("api.bitprivat.com", $apiHostEscaped)
$rendered = $rendered.Replace("app.bitprivat.com", $appHostEscaped)
$rendered = $rendered.Replace("www.bitprivat.com", $wwwHostEscaped)
$rendered = $rendered.Replace("bitprivat.com", $rootDomainEscaped)

if ($ExtraAcceptHosts) {
    $extraAcceptLines = @(
        $ExtraAcceptHosts -split "," |
            ForEach-Object { $_.Trim() } |
            Where-Object { $_ } |
            Select-Object -Unique |
            ForEach-Object { "          - $_" }
    )
    if ($extraAcceptLines.Count -gt 0) {
        $statusAcceptLine = "          - $statusHostEscaped"
        $rendered = $rendered.Replace($statusAcceptLine, "$statusAcceptLine`n$($extraAcceptLines -join "`n")")
    }
}

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
$rendered = $rendered -replace "BSM_SOCIAL_DISCOVERY_INTERVAL_SECONDS=[^`r`n]*", "BSM_SOCIAL_DISCOVERY_INTERVAL_SECONDS=$socialDiscoveryIntervalEscaped"
$rendered = $rendered -replace "denom:\s+ua[ck]t", "denom: $PricingDenom"

$outputDirectory = Split-Path -Parent $resolvedOutputPath
if ($outputDirectory -and -not (Test-Path -LiteralPath $outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}

Set-Content -LiteralPath $resolvedOutputPath -Value $rendered -Encoding UTF8
Write-Output "Generated Akash manifest: $resolvedOutputPath"
Write-Output "Pinned image: $resolvedImageRef"
Write-Output "Database mode: $DatabaseMode"
Write-Output "Pricing denom: $PricingDenom"
