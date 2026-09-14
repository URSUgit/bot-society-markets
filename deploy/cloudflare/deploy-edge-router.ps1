param(
    [string]$ConfigPath = $null
)

$ErrorActionPreference = "Stop"

if (-not $ConfigPath) {
    $ConfigPath = Join-Path $PSScriptRoot "edge-router\wrangler.jsonc"
}

npx wrangler@latest deploy --config $ConfigPath
