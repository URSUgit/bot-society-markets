$ErrorActionPreference = 'Stop'
$dockerInstallBin = 'C:\Program Files\Docker\Docker\resources\bin'
$dockerPluginBin = 'C:\Program Files\Docker\cli-plugins'
$dockerCandidates = @(
    'docker',
    (Join-Path $dockerInstallBin 'docker.exe')
)

if ((Test-Path $dockerInstallBin) -and -not (($env:PATH -split ';') -contains $dockerInstallBin)) {
    $env:PATH = "$env:PATH;$dockerInstallBin"
}
if ((Test-Path $dockerPluginBin) -and -not (($env:PATH -split ';') -contains $dockerPluginBin)) {
    $env:PATH = "$env:PATH;$dockerPluginBin"
}

$docker = $null
foreach ($candidate in $dockerCandidates) {
    try {
        if ($candidate -eq 'docker') {
            $null = Get-Command docker -ErrorAction Stop
            $docker = 'docker'
            break
        }
        if (Test-Path $candidate) {
            $docker = $candidate
            break
        }
    }
    catch {
    }
}

if (-not $docker) {
    throw 'Docker CLI was not found.'
}

& $docker compose down
