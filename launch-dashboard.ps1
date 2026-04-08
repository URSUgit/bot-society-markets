param(
    [ValidateSet('docker', 'local')]
    [string]$Mode = 'docker',
    [int]$Port = 8010
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

function Start-LocalDashboard {
    param([int]$LocalPort)

    $requirementsPath = Join-Path $root 'requirements.txt'
    $readyMarker = Join-Path $root '.venv\.bsm-ready'

    function Test-BsmHealth {
        param([int]$HealthPort)
        try {
            $response = Invoke-WebRequest -Uri "http://127.0.0.1:$HealthPort/health" -UseBasicParsing -TimeoutSec 2
            return $response.StatusCode -eq 200
        }
        catch {
            return $false
        }
    }

    $venvPython = Join-Path $root '.venv\Scripts\python.exe'
    if (-not (Test-Path $venvPython)) {
        Write-Host 'Creating virtual environment...'
        python -m venv .venv
    }

    $venvPython = Join-Path $root '.venv\Scripts\python.exe'
    $needsInstall = -not (Test-Path $readyMarker)
    if (-not $needsInstall) {
        $needsInstall = (Get-Item $requirementsPath).LastWriteTimeUtc -gt (Get-Item $readyMarker).LastWriteTimeUtc
    }

    if ($needsInstall) {
        Write-Host 'Installing dependencies... this may take a minute on first launch.'
        & $venvPython -m pip install --upgrade pip | Out-Null
        & $venvPython -m pip install -r $requirementsPath | Out-Null
        Set-Content -Path $readyMarker -Value (Get-Date).ToString('o')
    }
    else {
        Write-Host 'Using existing virtual environment and installed dependencies.'
    }

    if (-not (Test-BsmHealth -HealthPort $LocalPort)) {
        Write-Host 'Starting local Bot Society Markets server...'
        Start-Process powershell.exe -WorkingDirectory $root -ArgumentList @(
            '-NoExit',
            '-ExecutionPolicy', 'Bypass',
            '-File', (Join-Path $root 'run-dev.ps1'),
            '-Port', "$LocalPort"
        ) | Out-Null

        for ($attempt = 0; $attempt -lt 45; $attempt++) {
            Start-Sleep -Seconds 1
            if (Test-BsmHealth -HealthPort $LocalPort) {
                break
            }
        }
    }

    if (-not (Test-BsmHealth -HealthPort $LocalPort)) {
        throw "The Bot Society Markets server did not become healthy on port $LocalPort."
    }

    $dashboardUrl = "http://127.0.0.1:$LocalPort/dashboard"
    Write-Host "Opening $dashboardUrl"
    Start-Process $dashboardUrl | Out-Null
}

if ($Mode -eq 'docker') {
    try {
        & (Join-Path $root 'run-docker.ps1') -Port $Port
        exit 0
    }
    catch {
        Write-Warning "Docker launch failed: $($_.Exception.Message). Falling back to local mode."
    }
}

Start-LocalDashboard -LocalPort $Port
