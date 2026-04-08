param(
    [int]$Port = 8000,
    [switch]$Reload = $true
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$venvPython = Join-Path $root '.venv\Scripts\python.exe'
$python = if (Test-Path $venvPython) { $venvPython } else { 'python' }
$reloadArgs = if ($Reload) { @('--reload') } else { @() }

& $python -m uvicorn api.app.main:app --host 127.0.0.1 --port $Port @reloadArgs
