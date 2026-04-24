param(
    [Parameter(Mandatory = $true)]
    [string]$DatabaseUrl,

    [string]$CanonicalHost = "bitprivat.com",

    [string]$RootDomain = "bitprivat.com",

    [string]$ImageRef,

    [switch]$WithWorker,

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
$rendered = $template.Replace(
    "ghcr.io/ursugit/bot-society-markets:latest",
    $resolvedImageRef
).Replace(
    "postgresql+psycopg://USER:PASSWORD@HOST/DBNAME?sslmode=require",
    $databaseUrlEscaped
)
$rendered = $rendered -replace "BSM_CANONICAL_HOST=[^`r`n]*", "BSM_CANONICAL_HOST=$canonicalHostEscaped"
$rendered = $rendered -replace "BSM_CANONICAL_REDIRECT_HOSTS=[^`r`n]*", "BSM_CANONICAL_REDIRECT_HOSTS=$wwwHostEscaped,$appHostEscaped"
$rendered = $rendered.Replace("status.bitprivat.com", $statusHostEscaped)
$rendered = $rendered.Replace("api.bitprivat.com", $apiHostEscaped)
$rendered = $rendered.Replace("app.bitprivat.com", $appHostEscaped)
$rendered = $rendered.Replace("www.bitprivat.com", $wwwHostEscaped)
$rendered = $rendered.Replace("bitprivat.com", $rootDomainEscaped)

$outputDirectory = Split-Path -Parent $resolvedOutputPath
if ($outputDirectory -and -not (Test-Path -LiteralPath $outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}

Set-Content -LiteralPath $resolvedOutputPath -Value $rendered -Encoding UTF8
Write-Output "Generated Akash manifest: $resolvedOutputPath"
Write-Output "Pinned image: $resolvedImageRef"
