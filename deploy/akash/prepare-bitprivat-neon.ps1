param(
    [Parameter(Mandatory = $true)]
    [string]$DatabaseUrl,

    [string]$Domain = "app.bitprivat.com",

    [switch]$WithWorker,

    [string]$OutputPath
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
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
        Join-Path $projectRoot $OutputPath
    }
} else {
    Join-Path $PSScriptRoot $defaultOutputName
}

$template = Get-Content -LiteralPath $templatePath -Raw
$databaseUrlEscaped = $DatabaseUrl.Replace("`r", "").Replace("`n", "")
$rendered = $template.Replace(
    "postgresql+psycopg://USER:PASSWORD@HOST/DBNAME?sslmode=require",
    $databaseUrlEscaped
).Replace(
    "app.bitprivat.com",
    $Domain
)

$outputDirectory = Split-Path -Parent $resolvedOutputPath
if ($outputDirectory -and -not (Test-Path -LiteralPath $outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}

Set-Content -LiteralPath $resolvedOutputPath -Value $rendered -Encoding UTF8
Write-Output "Generated Akash manifest: $resolvedOutputPath"
